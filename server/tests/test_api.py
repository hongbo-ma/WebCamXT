"""
TCAD 后端 API 集成测试
覆盖: 认证/邀请码、管理端、文件上传隔离、曲线数据、自动拟合、仿真、并发隔离
运行: cd server && python -m pytest tests -v
"""
import io
import math
import uuid
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import pytest
from werkzeug.security import generate_password_hash

from models import db, User

W, L = 100.0, 10.0
PASSWORD = 'pass-123456'

SIM_DATA_PARAMS = {
    't_tail': 350.0, 't_deep': 400.0, 'g_tail': 1.0, 'g_deep': 1.0,
    'T': 300.0, 'mu_free': 0.8, 'Vfb': -0.8, 'phi_F0': 0.40, 'CoxArea': 0.03,
}


def make_sample_dataframe():
    """构造同时包含输出特性 (TO=0) 和转移特性 (TO=1) 的最小合法数据集"""
    rows = []
    for vg in [0.0, 5.0, 10.0]:
        for vd in np.arange(0, 10.0001, 0.25):
            rows.append({'W': W, 'L': L, 'TO': 0, 'M_Num': 1, 'D_Num': 1,
                         'GateV': float(vg), 'DrainV': float(vd),
                         'DrainI': 1e-9 * math.exp(0.3 * vg) * math.tanh(vd) + 1e-12})
    for vd in [0.1, 5.0]:
        for vg in np.arange(-5, 15.0001, 0.5):
            rows.append({'W': W, 'L': L, 'TO': 1, 'M_Num': 1, 'D_Num': 1,
                         'GateV': float(vg), 'DrainV': float(vd),
                         'DrainI': 1e-10 * (10 ** (0.35 * (vg - 0.5))) * vd + 1e-12})
    return pd.DataFrame(rows)


@pytest.fixture(scope='session')
def sample_xlsx(tmp_path_factory):
    path = tmp_path_factory.mktemp('data') / 'sample.xlsx'
    make_sample_dataframe().to_excel(path, sheet_name='Sheet1', index=False)
    return str(path)


@pytest.fixture(scope='session')
def admin_headers(app):
    from flask_jwt_extended import create_access_token
    with app.app_context():
        user = User(
            username=f'admin_{uuid.uuid4().hex[:8]}',
            password_hash=generate_password_hash(PASSWORD),
            role='admin',
        )
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))
    return {'Authorization': f'Bearer {token}'}


def create_invited_user(client, admin_headers):
    resp = client.post('/api/admin/invites', headers=admin_headers, json={})
    assert resp.status_code == 200
    code = resp.get_json()['code']
    username = f'user_{uuid.uuid4().hex[:8]}'
    resp = client.post('/api/auth/register', json={
        'username': username, 'password': PASSWORD, 'invite_code': code})
    assert resp.status_code == 200
    return {'Authorization': f"Bearer {resp.get_json()['token']}"}, username


def upload_sample(client, headers, sample_xlsx):
    with open(sample_xlsx, 'rb') as f:
        resp = client.post('/api/upload', headers=headers,
                           data={'file': (f, 'sample.xlsx')})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    return body['file_id'], body['combinations']


@pytest.fixture()
def user_headers(client, admin_headers):
    headers, _ = create_invited_user(client, admin_headers)
    return headers


@pytest.fixture()
def uploaded_file(client, user_headers, sample_xlsx):
    file_id, combinations = upload_sample(client, user_headers, sample_xlsx)
    return file_id, combinations, user_headers


# ---------- 基础 ----------

def test_health(client):
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert resp.get_json() == {'status': 'healthy'}


# ---------- 认证与邀请码 ----------

def test_register_requires_invite(client):
    resp = client.post('/api/auth/register', json={
        'username': 'x', 'password': 'y', 'invite_code': 'BADCODE'})
    assert resp.status_code == 400


def test_invite_full_flow(client, admin_headers):
    resp = client.post('/api/admin/invites', headers=admin_headers, json={})
    assert resp.status_code == 200
    code = resp.get_json()['code']

    username = f'user_{uuid.uuid4().hex[:8]}'
    resp = client.post('/api/auth/register', json={
        'username': username, 'password': PASSWORD, 'invite_code': code})
    assert resp.status_code == 200
    assert resp.get_json()['user']['role'] == 'user'

    # 邀请码只能用一次
    resp = client.post('/api/auth/register', json={
        'username': f'user_{uuid.uuid4().hex[:8]}', 'password': PASSWORD, 'invite_code': code})
    assert resp.status_code == 400

    # 用户名重复
    resp = client.post('/api/auth/register', json={
        'username': username, 'password': PASSWORD, 'invite_code': 'WHATEVER'})
    assert resp.status_code in (400, 409)


def test_login_success_and_wrong_password(client, user_headers):
    # user_headers 是通过注册拿到的 token, 这里直接校验 /me
    resp = client.get('/api/auth/me', headers=user_headers)
    assert resp.status_code == 200
    assert resp.get_json()['user']['role'] == 'user'

    resp = client.post('/api/auth/login', json={'username': 'nobody', 'password': 'wrong'})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get('/api/auth/me').status_code == 401


def test_revoked_invite_cannot_register(client, admin_headers):
    resp = client.post('/api/admin/invites', headers=admin_headers, json={})
    invite_id = resp.get_json()['id']
    code = resp.get_json()['code']

    resp = client.delete(f'/api/admin/invites/{invite_id}', headers=admin_headers)
    assert resp.status_code == 200

    resp = client.post('/api/auth/register', json={
        'username': f'user_{uuid.uuid4().hex[:8]}', 'password': PASSWORD, 'invite_code': code})
    assert resp.status_code == 400


# ---------- 管理端 ----------

def test_admin_endpoints_require_admin(client, user_headers):
    assert client.get('/api/admin/users', headers=user_headers).status_code == 403
    assert client.get('/api/admin/users').status_code == 401


def test_admin_list_update_delete_user(client, admin_headers, sample_xlsx):
    victim_headers, victim_name = create_invited_user(client, admin_headers)
    upload_sample(client, victim_headers, sample_xlsx)

    resp = client.get('/api/admin/users', headers=admin_headers)
    assert resp.status_code == 200
    victim = next(u for u in resp.get_json()['users'] if u['username'] == victim_name)
    assert victim['file_count'] == 1

    # 提升为 admin 再降回
    resp = client.patch(f"/api/admin/users/{victim['id']}",
                        headers=admin_headers, json={'role': 'admin'})
    assert resp.status_code == 200
    assert resp.get_json()['user']['role'] == 'admin'
    resp = client.patch(f"/api/admin/users/{victim['id']}",
                        headers=admin_headers, json={'role': 'user'})
    assert resp.status_code == 200

    # 不能删除自己
    resp = client.get('/api/auth/me', headers=admin_headers)
    my_id = resp.get_json()['user']['id']
    assert client.delete(f'/api/admin/users/{my_id}', headers=admin_headers).status_code == 400

    # 删除用户后其 token 失效
    assert client.delete(f"/api/admin/users/{victim['id']}", headers=admin_headers).status_code == 200
    assert client.get('/api/auth/me', headers=victim_headers).status_code == 401


# ---------- 文件上传与隔离 ----------

def test_upload_requires_auth_and_valid_type(client, user_headers, sample_xlsx):
    assert client.post('/api/upload').status_code == 401

    resp = client.post('/api/upload', headers=user_headers,
                       data={'file': (io.BytesIO(b'not excel'), 'bad.txt')})
    assert resp.status_code == 400


def test_upload_returns_combinations(uploaded_file):
    file_id, combinations, _ = uploaded_file
    assert combinations['w_l_pairs'] == [{'w': W, 'l': L}]
    assert combinations['vgs_vds_map']['100_10']['vgs'] == [0.0, 5.0, 10.0]


def test_files_list_get_delete(client, uploaded_file):
    file_id, _, headers = uploaded_file

    resp = client.get('/api/files', headers=headers)
    assert resp.status_code == 200
    assert len(resp.get_json()['files']) == 1

    resp = client.get(f'/api/files/{file_id}', headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()['combinations'] is not None

    assert client.delete(f'/api/files/{file_id}', headers=headers).status_code == 200
    assert client.get(f'/api/files/{file_id}', headers=headers).status_code == 404


def test_file_ownership_isolation(client, admin_headers, sample_xlsx):
    owner_headers, _ = create_invited_user(client, admin_headers)
    other_headers, _ = create_invited_user(client, admin_headers)
    file_id, _ = upload_sample(client, owner_headers, sample_xlsx)

    assert client.get(f'/api/files/{file_id}', headers=other_headers).status_code == 403
    assert client.delete(f'/api/files/{file_id}', headers=other_headers).status_code == 403
    assert client.get(f'/api/files/{file_id}', headers=owner_headers).status_code == 200


# ---------- 曲线数据 / 拟合 / 仿真 ----------

def test_plot_data_output_and_transfer(client, uploaded_file):
    file_id, _, headers = uploaded_file

    resp = client.post('/api/plot-data', headers=headers, json={
        'file_id': file_id, 'w': W, 'l': L, 'type': 'output', 'v_value': 5.0})
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body['x']) == len(body['y']) > 0

    resp = client.post('/api/plot-data', headers=headers, json={
        'file_id': file_id, 'w': W, 'l': L, 'type': 'transfer', 'v_value': 0.1})
    assert resp.status_code == 200
    assert len(resp.get_json()['x']) > 0

    # 不存在的 W
    resp = client.post('/api/plot-data', headers=headers, json={
        'file_id': file_id, 'w': 999.0, 'l': L, 'type': 'output', 'v_value': 5.0})
    assert resp.status_code == 400


def test_auto_fitting(client, uploaded_file):
    file_id, _, headers = uploaded_file
    resp = client.post('/api/auto_fitting', headers=headers, json={
        'file_id': file_id, 'w': W, 'l': L, 'data_params': SIM_DATA_PARAMS})
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert len(body['U_FE_1']) > 0
    assert 'V_th' in body


def _sim_payload(file_id, **overrides):
    payload = {
        'file_id': file_id, 'w': W, 'l': L, 'type_sel': 0,
        'vgs_min': 10.0, 'vgs_max': 10.0,
        'vds_min': 0.0, 'vds_max': 10.0, 'step': 0.5,
        'enable_rc': False,
        'data_params': dict(SIM_DATA_PARAMS),
    }
    params = overrides.pop('data_params', None)
    if params:
        payload['data_params'].update(params)
    payload.update(overrides)
    return payload


def test_simulation_output_no_rc(client, uploaded_file):
    file_id, _, headers = uploaded_file
    resp = client.post('/api/simulation', headers=headers,
                       json=_sim_payload(file_id))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert len(body['x']) == len(body['y']) == 21
    assert body['rc_array'] is None
    assert 0 <= body['fitting_error_rate'] <= 1


def test_simulation_transfer_no_rc(client, uploaded_file):
    file_id, _, headers = uploaded_file
    resp = client.post('/api/simulation', headers=headers, json=_sim_payload(
        file_id, type_sel=1, vgs_min=-5.0, vgs_max=15.0, vds_min=0.1, vds_max=0.1))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert len(body['y']) == 41


def test_simulation_with_rc(client, uploaded_file):
    file_id, _, headers = uploaded_file
    resp = client.post('/api/simulation', headers=headers, json=_sim_payload(
        file_id, enable_rc=True, max_iterations=3))
    assert resp.status_code == 200, resp.get_json()
    body = resp.get_json()
    assert body['enable_rc'] is True
    assert isinstance(body['rc_array'], list) and len(body['rc_array']) > 0


def test_simulation_rejects_bad_params(client, uploaded_file):
    file_id, _, headers = uploaded_file
    # t_tail == T
    resp = client.post('/api/simulation', headers=headers, json=_sim_payload(
        file_id, data_params={'t_tail': SIM_DATA_PARAMS['T']}))
    assert resp.status_code == 400
    # step <= 0
    resp = client.post('/api/simulation', headers=headers, json=_sim_payload(file_id, step=0))
    assert resp.status_code == 400


def test_concurrent_simulation_state_isolation(app, client, admin_headers, sample_xlsx):
    """回归测试: 同一文件的并发仿真不得互相污染共享 Service 状态"""
    headers, _ = create_invited_user(client, admin_headers)
    file_id, _ = upload_sample(client, headers, sample_xlsx)

    def sim(mu_free):
        c = app.test_client()
        r = c.post('/api/simulation', headers=headers,
                   json=_sim_payload(file_id, data_params={'mu_free': mu_free}))
        assert r.status_code == 200, r.get_json()
        return r.get_json()

    base_a = sim(0.8)['y']
    base_b = sim(5.0)['y']
    assert base_a != base_b, '不同 mu_free 应产生不同曲线'

    results = {}
    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {}
        for mu in [0.8, 5.0] * 3:
            futures[ex.submit(sim, mu)] = mu
        for fut, mu in futures.items():
            results[mu] = fut.result()['y']

    assert results[0.8] == base_a
    assert results[5.0] == base_b


# ---------- 账号有效期 / 审计日志 ----------

def test_register_default_expiry_30d(client, admin_headers):
    _, username = create_invited_user(client, admin_headers)
    # register/login 返回的 user dict 已包含 expires_at
    resp = client.post('/api/auth/login', json={'username': username, 'password': PASSWORD})
    body = resp.get_json()['user']
    assert body['expires_at'] is not None
    from datetime import datetime, timedelta
    exp = datetime.fromisoformat(body['expires_at'])
    assert timedelta(days=29) < (exp - datetime.utcnow()) <= timedelta(days=31)
    assert body['is_expired'] is False


def test_expired_user_blocked_then_renewed(app, client, admin_headers, sample_xlsx):
    from datetime import timedelta
    from models import utcnow, db as _db

    headers, username = create_invited_user(client, admin_headers)
    file_id, _ = upload_sample(client, headers, sample_xlsx)

    # 手动把账号置为过期
    with app.app_context():
        user = User.query.filter_by(username=username).first()
        user.expires_at = utcnow() - timedelta(days=1)
        _db.session.commit()
        uid = user.id

    # 登录被拒 + 业务接口 403
    assert client.post('/api/auth/login',
                       json={'username': username, 'password': PASSWORD}).status_code == 403
    assert client.get('/api/files', headers=headers).status_code == 403
    assert client.post('/api/plot-data', headers=headers, json={
        'file_id': file_id, 'w': W, 'l': L, 'type': 'output', 'v_value': 5.0}).status_code == 403

    # 管理员续期 30 天后恢复
    resp = client.patch(f'/api/admin/users/{uid}', headers=admin_headers,
                        json={'extend_days': 30})
    assert resp.status_code == 200
    body = resp.get_json()['user']
    assert body['is_expired'] is False
    assert client.get('/api/files', headers=headers).status_code == 200

    # 永久有效
    resp = client.patch(f'/api/admin/users/{uid}', headers=admin_headers,
                        json={'permanent': True})
    assert resp.get_json()['user']['expires_at'] is None


def test_admin_can_access_and_analyze_user_files(client, admin_headers, user_headers, sample_xlsx):
    file_id, _ = upload_sample(client, user_headers, sample_xlsx)

    # 管理员可读取用户文件详情与曲线 (代为分析)
    assert client.get(f'/api/files/{file_id}', headers=admin_headers).status_code == 200
    resp = client.post('/api/plot-data', headers=admin_headers, json={
        'file_id': file_id, 'w': W, 'l': L, 'type': 'output', 'v_value': 5.0})
    assert resp.status_code == 200

    # 管理员文件列表包含所有用户文件及属主
    resp = client.get('/api/files', headers=admin_headers)
    files = resp.get_json()['files']
    assert any(f['id'] == file_id and f['owner_username'] for f in files)


def test_operation_logs_recorded(client, admin_headers, user_headers, sample_xlsx):
    file_id, _ = upload_sample(client, user_headers, sample_xlsx)

    client.post('/api/plot-data', headers=user_headers, json={
        'file_id': file_id, 'w': W, 'l': L, 'type': 'output', 'v_value': 5.0})
    client.delete(f'/api/files/{file_id}', headers=user_headers)

    resp = client.get('/api/admin/logs?page=1&page_size=10', headers=admin_headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['total'] >= 3
    actions = {log['action'] for log in body['logs']}
    assert {'upload', 'plot', 'delete'} <= actions

    # 按动作过滤
    resp = client.get('/api/admin/logs?action=plot', headers=admin_headers)
    assert all(log['action'] == 'plot' for log in resp.get_json()['logs'])

    # 普通用户无权查看日志
    assert client.get('/api/admin/logs', headers=user_headers).status_code == 403
