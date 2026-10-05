from datetime import datetime
from app.extensions import db


class Attachment(db.Model):
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    filepath = db.Column(db.String(500), nullable=False)
    mimetype = db.Column(db.String(100))
    size = db.Column(db.Integer)  # bytes
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    uploader = db.relationship('User', foreign_keys=[uploaded_by_id], backref='uploads')

    def size_human(self):
        if not self.size:
            return '0 B'
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.size < 1024:
                return f'{self.size:.1f} {unit}'
            self.size /= 1024
        return f'{self.size:.1f} TB'

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'original_filename': self.original_filename,
            'size': self.size,
            'size_human': self.size_human(),
            'mimetype': self.mimetype,
            'uploaded_by': self.uploader.name if self.uploader else 'Unknown',
            'created_at': self.created_at.isoformat(),
        }


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    field_changed = db.Column(db.String(50))
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'user_id': self.user_id,
            'actor_name': self.user.name if self.user else 'System',
            'actor_role': self.user.role if self.user else None,
            'action': self.action,
            'field_changed': self.field_changed,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
        }


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    notification_type = db.Column(db.String(50), default='info')  # info, success, warning, error
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'link': self.link,
            'is_read': self.is_read,
            'notification_type': self.notification_type,
            'created_at': self.created_at.isoformat(),
        }
