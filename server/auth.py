import secrets
import string
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, FileRecord

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


def get_current_user():
    user_id = int(get_jwt_identity())
    return User.query.get(user_id)


def get_file_with_ownership(file_id):
    user_id = int(get_jwt_identity())
    record = FileRecord.query.get(file_id)
    if not record:
        return None, handle_error('文件不存在', 404)
    if record.user_id != user_id:
        return None, handle_error('无权访问此文件', 403)
    return record, None
