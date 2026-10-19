import secrets
import string
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from models import User, FileRecord, utcnow

SAFE_CHARS = (
    string.ascii_letters.replace('l', '').replace('I', '')
    + string.digits.replace('0', '').replace('1', '')
)


def generate_invite_code(length=8):
    return ''.join(secrets.choice(SAFE_CHARS) for _ in range(length))


def handle_error(error_msg, status_code=400, details=None):
    response = {'error': error_msg}
    if details:
        response['details'] = str(details)
    return jsonify(response), status_code


def admin_required(fn):
    @jwt_required()
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or user.role != 'admin':
            return handle_error('需要管理员权限', 403)
        return fn(*args, **kwargs)
    return wrapper


def active_required(fn):
    """JWT 认证 + 账号有效期校验; 过期账号返回 403 (前端据此引导续期)。
    管理员账号不受有效期限制, 避免锁死管理入口。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = User.query.get(int(get_jwt_identity()))
        if not user:
            return handle_error('用户不存在', 401)
        if user.is_expired():
            return handle_error('账号已过期, 请联系管理员续期 (ACCOUNT_EXPIRED)', 403)
        return fn(*args, **kwargs)
    return wrapper


def get_current_user():
    user_id = int(get_jwt_identity())
    return User.query.get(user_id)


def get_file_with_ownership(file_id):
    """按属主校验文件访问权; 管理员可访问任意用户的文件 (用于审计与代为分析)"""
    user = get_current_user()
    record = FileRecord.query.get(file_id)
    if not record:
        return None, handle_error('文件不存在', 404)
    is_admin = user is not None and user.role == 'admin'
    if record.user_id != (user.id if user else None) and not is_admin:
        return None, handle_error('无权访问此文件', 403)
    return record, None
