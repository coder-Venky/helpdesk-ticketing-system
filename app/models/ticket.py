from datetime import datetime
from app.extensions import db


class Ticket(db.Model):
    __tablename__ = 'tickets'

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default='General')
    status = db.Column(db.String(20), nullable=False, default='open')
    # open, in_progress, resolved, closed
    priority = db.Column(db.String(20), nullable=False, default='medium')
    # low, medium, high, critical
    tags = db.Column(db.String(255))
    due_date = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    comments = db.relationship('Comment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    attachments = db.relationship('Attachment', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='ticket', lazy='dynamic', cascade='all, delete-orphan')

    STATUS_CHOICES = ['open', 'in_progress', 'resolved', 'closed']
    PRIORITY_CHOICES = ['low', 'medium', 'high', 'critical']
    CATEGORY_CHOICES = ['Hardware', 'Software', 'Network', 'Access', 'Email', 'General', 'Change Request', 'Other']

    @staticmethod
    def generate_ticket_number():
        import random, string
        prefix = 'TKT'
        timestamp = datetime.utcnow().strftime('%Y%m')
        suffix = ''.join(random.choices(string.digits, k=4))
        return f'{prefix}-{timestamp}-{suffix}'

    def resolution_time_hours(self):
        if self.resolved_at:
            delta = self.resolved_at - self.created_at
            return round(delta.total_seconds() / 3600, 1)
        return None

    def to_dict(self, include_relations=False):
        data = {
            'id': self.id,
            'ticket_number': self.ticket_number,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'status': self.status,
            'priority': self.priority,
            'tags': self.tags,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'created_by_id': self.created_by_id,
            'assigned_to_id': self.assigned_to_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'resolution_time_hours': self.resolution_time_hours(),
        }
        if include_relations:
            data['creator'] = self.creator.to_dict() if self.creator else None
            data['assignee'] = self.assignee.to_dict() if self.assignee else None
            data['comments_count'] = self.comments.count()
            data['attachments_count'] = self.attachments.count()
        return data

    def __repr__(self):
        return f'<Ticket {self.ticket_number}>'
