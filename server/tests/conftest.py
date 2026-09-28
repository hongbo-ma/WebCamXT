"""
pytest 全局 fixture
必须在导入 app 之前设置环境变量 (Config 在 import 时求值),
将测试数据库与上传目录隔离到临时目录, 不污染开发数据。
"""
import os
import sys
import tempfile
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

_TEST_ROOT = Path(tempfile.mkdtemp(prefix='tcad_test_'))
os.environ['JWT_SECRET_KEY'] = 'pytest-secret-key-0123456789abcdef0123456789abcdef'
os.environ['DATABASE_URL'] = f"sqlite:///{(_TEST_ROOT / 'test.db').as_posix()}"
os.environ['UPLOAD_FOLDER'] = str(_TEST_ROOT / 'uploads')

import pytest


@pytest.fixture(scope='session')
def app():
    from app import create_app
    application = create_app()
    application.config['TESTING'] = True
    return application


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c
