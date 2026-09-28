#!/usr/bin/env python3
"""
TCAD 管理 CLI 工具
用法:
  python manage.py create-admin --username admin --password xxx [--email admin@xxx]
"""
import argparse
import sys

from werkzeug.security import generate_password_hash

from app import create_app
from models import db, User


def create_admin(username, password, email=None):
    app = create_app()
    with app.app_context():
        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f"错误: 用户名 '{username}' 已存在")
            sys.exit(1)

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            email=email,
            role='admin',
        )
        db.session.add(user)
        db.session.commit()
        print(f"管理员账号创建成功: {username} (id={user.id})")


def main():
    parser = argparse.ArgumentParser(description='TCAD 管理 CLI')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    p_admin = subparsers.add_parser('create-admin', help='创建管理员账号')
    p_admin.add_argument('--username', required=True, help='管理员用户名')
    p_admin.add_argument('--password', required=True, help='管理员密码')
    p_admin.add_argument('--email', default=None, help='邮箱 (可选)')

    args = parser.parse_args()

    if args.command == 'create-admin':
        create_admin(args.username, args.password, args.email)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
