from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


def utcnow():
    """统一使用 naive UTC 时间 (SQLite 兼容), 避免本地时区不一致"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    role = db.Column(db.String(20), default='user', nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)
    # 账号有效期; NULL = 永久 (管理员账号默认永久)
    expires_at = db.Column(db.DateTime, nullable=True)

    def is_expired(self):
        return (
            self.expires_at is not None
            and self.role != 'admin'
            and self.expires_at < utcnow()
        )

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
        }


class InviteCode(db.Model):
    __tablename__ = 'invite_codes'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    used_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    creator = db.relationship('User', foreign_keys=[created_by], backref='created_invites')
    used_user = db.relationship('User', foreign_keys=[used_by])

    def to_dict(self):
        return {
            'id': self.id,
            'code': self.code,
            'is_used': self.used_by is not None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'used_by_username': self.used_user.username if self.used_user else None,
            'is_active': self.is_active,
        }


class FileRecord(db.Model):
    __tablename__ = 'file_records'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=True)
    md5 = db.Column(db.String(32), nullable=True)
    combinations_json = db.Column(db.Text, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship('User', backref='files')

    def to_dict(self, include_combinations=True, owner_username=None):
        import json
        data = {
            'id': self.id,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'user_id': self.user_id,
            'owner_username': owner_username,
        }
        if include_combinations and self.combinations_json:
            data['combinations'] = json.loads(self.combinations_json)
        else:
            data['combinations'] = None
        return data


class OperationLog(db.Model):
    """用户操作审计日志: 记录 谁(user) 对 哪个文件(file) 做了 什么操作(action)"""
    __tablename__ = 'operation_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False)          # 快照, 用户删除后仍可读
    file_id = db.Column(db.Integer, nullable=True, index=True)
    file_name = db.Column(db.String(255), nullable=True)          # 快照, 文件删除后仍可读
    file_owner_name = db.Column(db.String(80), nullable=True)     # 快照: 文件属主 (管理员代查时与操作者不同)
    action = db.Column(db.String(32), nullable=False, index=True)  # upload/delete/plot/simulation/auto_fitting/renew
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'file_id': self.file_id,
            'file_name': self.file_name,
            'file_owner_name': self.file_owner_name,
            'action': self.action,
            'detail': self.detail,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


def log_operation(user, action, file_record=None, detail=None):
    """记录一条操作日志并立即提交 (独立事务, 不影响调用方业务事务)"""
    user = user if isinstance(user, User) else User.query.get(int(user))
    if user is None:
        return
    entry = OperationLog(
        user_id=user.id,
        username=user.username,
        file_id=file_record.id if file_record else None,
        file_name=file_record.original_filename if file_record else None,
        file_owner_name=file_record.user.username if (file_record and file_record.user) else None,
        action=action,
        detail=detail,
    )
    db.session.add(entry)
    db.session.commit()
