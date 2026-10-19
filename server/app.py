#!/usr/bin/env python3
"""
TCAD Backend Flask API Server (BS 架构版)
- JWT 认证 + 邀请码注册
- 用户文件隔离
- 多用户并发安全 (无全局状态)
"""
import os
import json
import math
import hashlib
import traceback
from datetime import timedelta

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager, get_jwt_identity, create_access_token
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import numpy as np

from config import Config
from models import db, User, InviteCode, FileRecord, OperationLog, utcnow, log_operation
from auth import (handle_error, admin_required, active_required, get_current_user,
                  get_file_with_ownership, generate_invite_code)
from service_factory import locked_service, invalidate, invalidate_user, set_cached_service
from compute_service import ComputeService


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'instance'), exist_ok=True)

    db.init_app(app)
    jwt = JWTManager(app)
    # 同源部署 (vite/nginx 反代) 无需 CORS; 设置 CORS_ORIGINS 环境变量可按需开启
    if Config.CORS_ORIGINS:
        CORS(app, origins=Config.CORS_ORIGINS)

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        return jsonify({'error': 'Invalid token'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error_string):
        return jsonify({'error': 'Authorization token is required'}), 401

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has been revoked'}), 401

    with app.app_context():
        db.create_all()
        _migrate_sqlite(app)

    _register_auth_routes(app)
    _register_admin_routes(app)
    _register_file_routes(app)
    _register_analysis_routes(app)
    _register_error_handlers(app)
    return app


def _migrate_sqlite(app):
    """轻量迁移: SQLite 已有表新增列 (db.create_all 不会为已有表加列)。
    存量用户 expires_at 保持 NULL = 永久有效, 避免升级即锁号。"""
    from sqlalchemy import text
    with db.engine.connect() as conn:
        cols = [row[1] for row in conn.execute(text('PRAGMA table_info(users)'))]
        if 'expires_at' not in cols:
            conn.execute(text('ALTER TABLE users ADD COLUMN expires_at DATETIME'))
            conn.commit()
            app.logger.info('migrated: users.expires_at added')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def calculate_fitting_error_rate(service, w, l, type_sel, voltage_array, sim_current, bias_voltage):
    try:
        if type_sel == 0:
            exp_x, exp_y = service.get_output_data(w, l, 0, bias_voltage)
        else:
            exp_x, exp_y = service.get_transfer_data(w, l, 1, bias_voltage)

        if len(exp_x) == 0 or len(exp_y) == 0:
            return 0.005

        sim_voltage = np.array(voltage_array)
        sim_current_arr = np.array(sim_current)
        exp_voltage = np.array(exp_x)
        exp_current = np.array(exp_y)

        errors = []
        for i, v_sim in enumerate(sim_voltage):
            closest_idx = np.argmin(np.abs(exp_voltage - v_sim))
            exp_i = exp_current[closest_idx]
            sim_i = sim_current_arr[i]
            if abs(exp_i) > 1e-12:
                errors.append(abs(sim_i - exp_i) / abs(exp_i))

        if errors:
            return min(max(float(np.mean(errors)), 0.001), 1.0)
        return 0.005
    except Exception:
        return 0.005


def _js_number_str(v):
    """将浮点数转为与 JS Number.toString() 一致的字符串 (100.0 -> '100', 100.5 -> '100.5'),
    保证 combinations 键能被前端 `${w}_${l}` 正确命中"""
    s = repr(float(v))
    return s[:-2] if s.endswith('.0') else s


def build_combinations(service):
    combinations = {'vgs_vds_map': {}, 'w_l_pairs': []}
    ws_list = service.get_ws()
    ls_list = service.get_ls()

    for w in ws_list:
        for l in ls_list:
            w_l_key = f'{_js_number_str(w)}_{_js_number_str(l)}'
            try:
                vgs_list = service.get_vgs(w, l)
                mask = (
                    (service.df[service.W] == w) &
                    (service.df[service.L] == l) &
                    (service.df[service.TYPE] == 1)
                )
                vds_filtered = service.df[mask][service.DRAIN_V].drop_duplicates().sort_values()
                vds_data = vds_filtered.astype(float).tolist()

                combinations['vgs_vds_map'][w_l_key] = {
                    'vgs': [float(v) for v in vgs_list] if vgs_list else [],
                    'vds': [float(v) for v in vds_data] if vds_data else []
                }
                combinations['w_l_pairs'].append({'w': float(w), 'l': float(l)})
            except Exception:
                pass
    return combinations


def _do_simulation(service, logger, *, w, l, type_sel,
                   vgs_min, vgs_max, vds_min, vds_max, step,
                   enable_rc, max_iterations, error_tolerance,
                   t_tail, t_deep, g_tail, g_deep, T, data_params):
    """执行 TCAD 仿真计算 (调用方必须已通过 locked_service 持有该文件的锁)"""
    service.M = data_params.get('M', 0.2)

    if t_tail > T:
        N_tail = g_tail * service.KB * T * math.pi / math.sin(math.pi * T / t_tail)
        phi_tail = service.KB * t_tail
    else:
        N_tail = g_tail * service.KB * T * (T / t_tail - 1)
        phi_tail = service.KB * T

    if t_deep > T:
        N_deep = g_deep * service.KB * T * math.pi / math.sin(math.pi * T / t_deep)
        phi_deep = service.KB * t_deep
    else:
        N_deep = g_deep * service.KB * T * (T / t_deep - 1)
        phi_deep = service.KB * T

    N_tail = N_tail * 1e-18
    N_deep = N_deep * 1e-18

    service.phi_tail = phi_tail
    service.phi_deep = phi_deep
    service.Ntail_eff = N_tail
    service.Ndeep_eff = N_deep
    service.T = T
    service.ufree = float(data_params['mu_free'])
    service.Vfb = float(data_params['Vfb'])
    service.phi_F0 = float(data_params['phi_F0'])
    service.VT = T * service.KB
    service.set_cox_area(float(data_params['CoxArea']))

    simulation_params = {
        'N_tail': N_tail * 1e18,
        'N_deep': N_deep * 1e18,
        'phi_tail': phi_tail,
        'phi_deep': phi_deep,
        'mu_free': float(data_params['mu_free']),
        'Vfb': float(data_params['Vfb']),
        'phi_F0': float(data_params['phi_F0']),
        'CoxArea': float(data_params['CoxArea'])
    }

    U_FE_1, U_FE_2, SS, V_th = service.u_fe_computer(w, l)

    if enable_rc:
        service._fitting(w, l, simulation_params, enable_rc, max_iterations, error_tolerance)

    if type_sel == 0:
        V_start = vds_min
        V_end = vds_max
        Vbias = vgs_min
    else:
        V_start = vgs_min
        V_end = vgs_max
        Vbias = vds_min

    num_points = int((V_end - V_start) / step) + 1
    voltage_array = np.linspace(V_start, V_end, num_points)

    if type_sel == 0:
        V_sl = service.get_vgs(w, l)
    else:
        mask = (
            (service.df[service.W] == w) &
            (service.df[service.L] == l) &
            (service.df[service.TYPE] == 1)
        )
        vds_filtered = service.df[mask][service.DRAIN_V].drop_duplicates().sort_values()
        V_sl = vds_filtered.astype(float).tolist()

    current_array = service.TCAD_I_simulation(
        type_sel=type_sel, Vbias=Vbias, Vswp=voltage_array,
        data_params=simulation_params, W=w, L=l, V_sl=V_sl
    )

    if hasattr(current_array, 'tolist'):
        y_values = current_array.tolist()
    else:
        y_values = list(current_array)

    y_values = [0.0 if (val != val or val == float('inf') or val == float('-inf')) else float(val) for val in y_values]

    fitting_error_rate = calculate_fitting_error_rate(
        service, w, l, type_sel, voltage_array, y_values,
        Vbias if type_sel == 0 else V_start
    )

    rc_array = None
    if enable_rc and hasattr(service, 'Rc_V') and service.Rc_V is not None:
        try:
            w_idx = service.get_w_index(w)
            l_idx = service.get_l_index(w, l)
            _all = service.get_vgs(w, l)
            index = 0
            for i in range(len(_all)):
                if abs(_all[i] - Vbias) < 1e-6:
                    index = i
                    break
            rc_data = service.Rc_V[w_idx][l_idx][index]
            rc_array = []
            for row in rc_data:
                if isinstance(row, list):
                    for val in row:
                        rc_array.append(0.0 if (val != val or val == float('inf') or val == float('-inf')) else float(val))
                else:
                    rc_array.append(0.0 if (row != row or row == float('inf') or row == float('-inf')) else float(row))
        except Exception as e:
            logger.warning(f'Failed to get RC array: {str(e)}')
            rc_array = None

    return {
        'x': voltage_array.tolist() if hasattr(voltage_array, 'tolist') else list(voltage_array),
        'y': y_values,
        'enable_rc': enable_rc,
        'rc_array': rc_array,
        'fitting_error_rate': fitting_error_rate,
        'w': w, 'l': l, 'type_sel': type_sel,
        'U_FE_1': [f'{val:.3e}' for val in U_FE_1] if U_FE_1 is not None else [],
        'U_FE_2': [f'{val:.3e}' for val in U_FE_2] if U_FE_2 is not None else [],
        'SS': [f'{val:.2f}' for val in SS] if SS is not None else [],
        'V_th': f'{V_th:.3f}' if V_th is not None else '0.000'
    }


def _register_auth_routes(app):

    @app.route('/api/auth/register', methods=['POST'])
    def register():
        data = request.get_json()
        if not data:
            return handle_error('No JSON data provided')

        required = ['username', 'password', 'invite_code']
        for field in required:
            if field not in data:
                return handle_error(f'Missing required field: {field}')

        invite = InviteCode.query.filter_by(code=data['invite_code']).first()
        if not invite:
            return handle_error('邀请码无效', 400)
        if not invite.is_active:
            return handle_error('邀请码已被撤销', 400)
        if invite.used_by is not None:
            return handle_error('邀请码已被使用', 400)
        if invite.expires_at < utcnow():
            return handle_error('邀请码已过期', 400)

        if User.query.filter_by(username=data['username']).first():
            return handle_error('用户名已存在', 409)

        user = User(
            username=data['username'],
            password_hash=generate_password_hash(data['password']),
            email=data.get('email'),
            role='user',
            expires_at=utcnow() + timedelta(days=Config.DEFAULT_USER_EXPIRE_DAYS),
        )
        db.session.add(user)
        db.session.flush()

        invite.used_by = user.id
        invite.used_at = utcnow()
        db.session.commit()

        token = create_access_token(identity=str(user.id))
        return jsonify({'token': token, 'user': user.to_dict()})

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        data = request.get_json()
        if not data:
            return handle_error('No JSON data provided')

        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return handle_error('用户名和密码不能为空')

        user = User.query.filter_by(username=username).first()
        if not user or not check_password_hash(user.password_hash, password):
            return handle_error('用户名或密码错误', 401)
        if user.is_expired():
            return handle_error('账号已过期, 请联系管理员续期 (ACCOUNT_EXPIRED)', 403)

        token = create_access_token(identity=str(user.id))
        return jsonify({'token': token, 'user': user.to_dict()})

    @app.route('/api/auth/me', methods=['GET'])
    @active_required
    def me():
        user = get_current_user()
        if not user:
            return handle_error('用户不存在', 404)
        return jsonify({'user': user.to_dict()})


def _register_admin_routes(app):

    @app.route('/api/admin/invites', methods=['POST'])
    @admin_required
    def create_invite():
        data = request.get_json() or {}
        expire_days = data.get('expires_days', Config.INVITE_DEFAULT_EXPIRE_DAYS)

        user_id = int(get_jwt_identity())
        code = generate_invite_code()
        while InviteCode.query.filter_by(code=code).first():
            code = generate_invite_code()

        invite = InviteCode(
            code=code,
            created_by=user_id,
            expires_at=utcnow() + timedelta(days=expire_days),
        )
        db.session.add(invite)
        db.session.commit()
        return jsonify(invite.to_dict())

    @app.route('/api/admin/invites', methods=['GET'])
    @admin_required
    def list_invites():
        invites = InviteCode.query.order_by(InviteCode.created_at.desc()).all()
        return jsonify({'invites': [inv.to_dict() for inv in invites]})

    @app.route('/api/admin/invites/<int:invite_id>', methods=['DELETE'])
    @admin_required
    def revoke_invite(invite_id):
        invite = InviteCode.query.get(invite_id)
        if not invite:
            return handle_error('邀请码不存在', 404)
        if invite.used_by is not None:
            return handle_error('已使用的邀请码不可撤销', 400)
        invite.is_active = False
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/admin/users', methods=['GET'])
    @admin_required
    def list_users():
        users = User.query.order_by(User.created_at.desc()).all()
        result = []
        for u in users:
            d = u.to_dict()
            d['file_count'] = FileRecord.query.filter_by(user_id=u.id).count()
            result.append(d)
        return jsonify({'users': result})

    @app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
    @admin_required
    def delete_user(user_id):
        current_id = int(get_jwt_identity())
        if user_id == current_id:
            return handle_error('不能删除自己', 400)

        user = User.query.get(user_id)
        if not user:
            return handle_error('用户不存在', 404)

        files = FileRecord.query.filter_by(user_id=user_id).all()
        invalidate_user(user_id, files)
        for f in files:
            if os.path.exists(f.stored_path):
                os.remove(f.stored_path)
            db.session.delete(f)

        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/admin/users/<int:user_id>', methods=['PATCH'])
    @admin_required
    def update_user_role(user_id):
        data = request.get_json()
        if not data:
            return handle_error('Missing JSON data')

        user = User.query.get(user_id)
        if not user:
            return handle_error('用户不存在', 404)

        # 角色调整
        if 'role' in data:
            if data['role'] not in ('admin', 'user'):
                return handle_error('role 必须是 admin 或 user')
            user.role = data['role']

        # 有效期管理: permanent=true 设为永久; extend_days=N 在现有基础上顺延 N 天
        renewed = False
        if data.get('permanent'):
            user.expires_at = None
            renewed = True
        elif 'extend_days' in data:
            try:
                days = int(data['extend_days'])
            except (TypeError, ValueError):
                return handle_error('extend_days 必须是整数')
            if days <= 0:
                return handle_error('extend_days 必须大于 0')
            base = user.expires_at if (user.expires_at and user.expires_at > utcnow()) else utcnow()
            user.expires_at = base + timedelta(days=days)
            renewed = True

        db.session.commit()
        if renewed:
            operator = get_current_user()
            log_operation(operator, 'renew', detail=(
                f"renewed user '{user.username}'"
                + (' permanently' if user.expires_at is None else f" to {user.expires_at.isoformat()}")
            ))
        return jsonify({'user': user.to_dict()})

    @app.route('/api/admin/logs', methods=['GET'])
    @admin_required
    def list_logs():
        """操作日志: 分页 + 按 用户/文件/动作 过滤"""
        try:
            page = max(int(request.args.get('page', 1)), 1)
            page_size = min(max(int(request.args.get('page_size', 20)), 1), 100)
        except ValueError:
            return handle_error('page/page_size 必须是整数')

        query = OperationLog.query
        user_id = request.args.get('user_id')
        file_id = request.args.get('file_id')
        action = request.args.get('action')
        if user_id:
            query = query.filter_by(user_id=int(user_id))
        if file_id:
            query = query.filter_by(file_id=int(file_id))
        if action:
            query = query.filter_by(action=action)

        total = query.count()
        logs = (query.order_by(OperationLog.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size).all())
        return jsonify({'logs': [log.to_dict() for log in logs], 'total': total})


def _register_file_routes(app):

    @app.route('/api/files', methods=['GET'])
    @active_required
    def list_files():
        user = get_current_user()
        if user.role == 'admin':
            # 管理员: 返回所有用户的文件 (含属主), 用于审计与代为分析
            records = FileRecord.query.order_by(FileRecord.uploaded_at.desc()).all()
            files = [f.to_dict(include_combinations=False,
                               owner_username=f.user.username if f.user else None)
                     for f in records]
        else:
            records = FileRecord.query.filter_by(user_id=user.id)\
                .order_by(FileRecord.uploaded_at.desc()).all()
            files = [f.to_dict(include_combinations=False) for f in records]
        return jsonify({'files': files})

    @app.route('/api/upload', methods=['POST'])
    @active_required
    def upload_file():
        user_id = int(get_jwt_identity())

        if 'file' not in request.files:
            return handle_error('No file provided')
        file = request.files['file']
        if file.filename == '':
            return handle_error('No file selected')
        if not allowed_file(file.filename):
            return handle_error('Invalid file type. Only .xls and .xlsx files are allowed')

        user_dir = os.path.join(Config.UPLOAD_FOLDER, str(user_id))
        os.makedirs(user_dir, exist_ok=True)

        record = FileRecord(
            user_id=user_id,
            original_filename=file.filename,
            stored_path='',
            file_size=0,
        )
        db.session.add(record)
        db.session.flush()

        safe_name = secure_filename(file.filename) or f'file_{record.id}.xlsx'
        stored_name = f'{record.id}_{safe_name}'
        filepath = os.path.join(user_dir, stored_name)
        file.save(filepath)

        file_size = os.path.getsize(filepath)

        md5 = hashlib.md5()
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                md5.update(chunk)

        record.stored_path = filepath
        record.file_size = file_size
        record.md5 = md5.hexdigest()

        try:
            service = ComputeService()
            service._set_compute_file(filepath)
            combinations = build_combinations(service)
            record.combinations_json = json.dumps(combinations)
            set_cached_service(record.id, service)
        except Exception as e:
            db.session.rollback()
            if os.path.exists(filepath):
                os.remove(filepath)
            return handle_error('文件解析失败', 400, str(e))

        db.session.commit()
        log_operation(get_current_user(), 'upload', record,
                      detail=f'{record.original_filename} ({record.file_size} B)')
        return jsonify({'file_id': record.id, 'combinations': combinations})

    @app.route('/api/files/<int:file_id>', methods=['GET'])
    @active_required
    def get_file(file_id):
        record, error = get_file_with_ownership(file_id)
        if error:
            return error
        owner = record.user.username if record.user else None
        return jsonify(record.to_dict(include_combinations=True, owner_username=owner))

    @app.route('/api/files/<int:file_id>', methods=['DELETE'])
    @active_required
    def delete_file(file_id):
        record, error = get_file_with_ownership(file_id)
        if error:
            return error

        fname = record.original_filename
        invalidate(record.id)
        if os.path.exists(record.stored_path):
            os.remove(record.stored_path)
        db.session.delete(record)
        db.session.commit()
        log_operation(get_current_user(), 'delete', None,
                      detail=f'{fname} (file #{file_id})')
        return jsonify({'success': True})


def _register_analysis_routes(app):

    @app.route('/api/plot-data', methods=['POST'])
    @active_required
    def get_plot_data():
        data = request.get_json()
        if not data:
            return handle_error('No JSON data provided')

        file_id = data.get('file_id')
        if not file_id:
            return handle_error('Missing required field: file_id')

        record, error = get_file_with_ownership(file_id)
        if error:
            return error

        required = ['w', 'l', 'type', 'v_value']
        for field in required:
            if field not in data:
                return handle_error(f'Missing required field: {field}')

        w = float(data['w'])
        l = float(data['l'])
        curve_type = data['type']
        v_value = float(data['v_value'])

        if curve_type not in ['output', 'transfer']:
            return handle_error("Invalid type. Must be 'output' or 'transfer'")

        try:
            with locked_service(record.id, record.stored_path) as service:
                ws_list = service.get_ws()
                ls_list = service.get_ls()
                if not any(abs(float(v) - w) < 1e-6 for v in ws_list):
                    return handle_error(f'Width value {w} not found in data')
                if not any(abs(float(v) - l) < 1e-6 for v in ls_list):
                    return handle_error(f'Length value {l} not found for width {w}')

                if curve_type == 'output':
                    x, y = service.get_output_data(w, l, 0, v_value)
                else:
                    x, y = service.get_transfer_data(w, l, 1, v_value)

                log_operation(get_current_user(), 'plot', record,
                              detail=f'type={curve_type} w={w} l={l} v={v_value}')
                return jsonify({
                    'x': x.tolist() if hasattr(x, 'tolist') else list(x),
                    'y': y.tolist() if hasattr(y, 'tolist') else list(y)
                })
        except Exception as e:
            app.logger.error(f'Plot data error: {str(e)}')
            app.logger.error(traceback.format_exc())
            return handle_error('Internal server error', 500, str(e))

    @app.route('/api/auto_fitting', methods=['POST'])
    @active_required
    def auto_fitting():
        data = request.get_json()
        if not data:
            return handle_error('No JSON data provided')

        file_id = data.get('file_id')
        if not file_id:
            return handle_error('Missing required field: file_id')

        record, error = get_file_with_ownership(file_id)
        if error:
            return error

        required = ['w', 'l', 'data_params']
        for field in required:
            if field not in data:
                return handle_error(f'Missing required field: {field}')

        w = float(data['w'])
        l = float(data['l'])
        data_params = data['data_params']

        required_params = ['t_tail', 't_deep', 'g_tail', 'g_deep', 'T', 'mu_free', 'Vfb', 'phi_F0', 'CoxArea']
        for param in required_params:
            if param not in data_params:
                return handle_error(f'Missing required parameter: {param}')

        try:
            with locked_service(record.id, record.stored_path) as service:
                ws_list = service.get_ws()
                ls_list = service.get_ls()
                if not any(abs(float(v) - w) < 1e-6 for v in ws_list):
                    return handle_error(f'Width value {w} not found in data')
                if not any(abs(float(v) - l) < 1e-6 for v in ls_list):
                    return handle_error(f'Length value {l} not found for width {w}')

                U_FE_1, U_FE_2, SS, V_th = service.u_fe_computer(w, l)

                log_operation(get_current_user(), 'auto_fitting', record,
                              detail=f'w={w} l={l} V_th={V_th}')
                response = {
                    'U_FE_1': [f'{val:.3e}' for val in U_FE_1] if U_FE_1 is not None else [],
                    'U_FE_2': [f'{val:.3e}' for val in U_FE_2] if U_FE_2 is not None else [],
                    'SS': [f'{val:.2f}' for val in SS] if SS is not None else [],
                    'V_th': f'{V_th:.3f}' if V_th is not None else '0.000'
                }
                return jsonify(response)
        except Exception as e:
            app.logger.error(f'Auto fitting error: {str(e)}')
            app.logger.error(traceback.format_exc())
            return handle_error('Internal server error', 500, str(e))

    @app.route('/api/simulation', methods=['POST'])
    @active_required
    def simulation():
        data = request.get_json()
        if not data:
            return handle_error('No JSON data provided')

        file_id = data.get('file_id')
        if not file_id:
            return handle_error('Missing required field: file_id')

        record, error = get_file_with_ownership(file_id)
        if error:
            return error

        required = ['w', 'l', 'type_sel', 'vgs_min', 'vgs_max', 'vds_min', 'vds_max', 'step', 'data_params']
        for field in required:
            if field not in data:
                return handle_error(f'Missing required field: {field}')

        w = float(data['w'])
        l = float(data['l'])
        type_sel = int(data['type_sel'])
        vgs_min = float(data['vgs_min'])
        vgs_max = float(data['vgs_max'])
        vds_min = float(data['vds_min'])
        vds_max = float(data['vds_max'])
        step = float(data['step'])
        enable_rc = data.get('enable_rc', False)
        max_iterations = data.get('max_iterations', 100)
        error_tolerance = data.get('error_tolerance', 0.01)
        data_params = data['data_params']

        required_params = ['t_tail', 't_deep', 'g_tail', 'g_deep', 'T', 'mu_free', 'Vfb', 'phi_F0', 'CoxArea']
        for param in required_params:
            if param not in data_params:
                return handle_error(f'Missing required parameter in data_params: {param}')

        t_tail = float(data_params['t_tail'])
        t_deep = float(data_params['t_deep'])
        T = float(data_params['T'])
        if abs(t_tail - T) < 0.001:
            return handle_error("t_tail cannot be equal to T")
        if abs(t_deep - T) < 0.001:
            return handle_error("t_deep cannot be equal to T")
        if step <= 0:
            return handle_error("Step must be greater than 0")
        if type_sel not in [0, 1]:
            return handle_error("type_sel must be 0 (output) or 1 (transfer)")

        g_tail = float(data_params['g_tail'])
        g_deep = float(data_params['g_deep'])

        try:
            with locked_service(record.id, record.stored_path) as service:
                service.reset_fitting_parameters()
                try:
                    ws_list = service.get_ws()
                    ls_list = service.get_ls()
                    if not any(abs(float(v) - w) < 1e-6 for v in ws_list):
                        return handle_error(f'Width value {w} not found in data')
                    if not any(abs(float(v) - l) < 1e-6 for v in ls_list):
                        return handle_error(f'Length value {l} not found for width {w}')

                    response = _do_simulation(
                        service, app.logger,
                        w=w, l=l, type_sel=type_sel,
                        vgs_min=vgs_min, vgs_max=vgs_max,
                        vds_min=vds_min, vds_max=vds_max,
                        step=step,
                        enable_rc=enable_rc,
                        max_iterations=max_iterations,
                        error_tolerance=error_tolerance,
                        t_tail=t_tail, t_deep=t_deep,
                        g_tail=g_tail, g_deep=g_deep,
                        T=T, data_params=data_params,
                    )
                    log_operation(get_current_user(), 'simulation', record, detail=(
                        f'type={"output" if type_sel == 0 else "transfer"} '
                        f'w={w} l={l} rc={enable_rc} err={response["fitting_error_rate"]:.4f}'))
                    return jsonify(response)
                finally:
                    # 无论成功或异常, 都将共享 Service 的拟合状态恢复干净
                    service.reset_fitting_parameters()
        except Exception as e:
            app.logger.error(f'Simulation error: {str(e)}')
            app.logger.error(traceback.format_exc())
            return handle_error('Internal server error', 500, str(e))

    @app.route('/api/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'healthy'})


def _register_error_handlers(app):

    @app.errorhandler(404)
    def not_found(error):
        return handle_error('Endpoint not found', 404)

    @app.errorhandler(405)
    def method_not_allowed(error):
        return handle_error('Method not allowed', 405)

    @app.errorhandler(413)
    def payload_too_large(error):
        return handle_error('File too large', 413)


app = create_app()

if __name__ == '__main__':
    print("Starting TCAD Backend Flask API Server...")
    print("Health check: http://localhost:5000/api/health")
    app.run(host='0.0.0.0', port=5000, debug=False)
