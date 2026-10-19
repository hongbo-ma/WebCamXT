import hashlib
import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')

_DEV_DEFAULT_JWT_KEY = 'dev-secret-change-in-production-use-a-longer-key-at-least-32-bytes'


def _resolve_jwt_key():
    raw = os.environ.get('JWT_SECRET_KEY', '')
    if not raw:
        print('[WARN] JWT_SECRET_KEY 未设置, 正在使用开发默认密钥; '
              '生产环境必须通过环境变量设置随机密钥, 例如: python -c "import secrets; print(secrets.token_hex(32))"')
        raw = _DEV_DEFAULT_JWT_KEY
    # 通过 SHA-256 派生固定长度密钥, 保证任意输入都 >= 32 字节
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{os.path.join(INSTANCE_DIR, "tcad.db")}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = _resolve_jwt_key()
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    # 支持环境变量覆盖, 便于测试与容器化部署
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'uploads'))
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'xls', 'xlsx'}

    # 跨域来源白名单 (逗号分隔). 默认为空 = 不启用 CORS:
    # 前端 dev 走 vite 代理、生产走 nginx 反代, 均为同源请求, 无需 CORS。
    CORS_ORIGINS = [o.strip() for o in os.environ.get('CORS_ORIGINS', '').split(',') if o.strip()]

    INVITE_DEFAULT_EXPIRE_DAYS = 7

    # 新用户账号默认有效期 (天); 管理员可在用户管理中续期或设为永久
    DEFAULT_USER_EXPIRE_DAYS = 30
