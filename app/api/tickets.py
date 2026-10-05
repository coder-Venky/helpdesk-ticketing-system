from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.ticket import Ticket
from app.models.comment import Comment
from app.models.attachment import Attachment, ActivityLog
from app.models.user import User
from app.utils import success_response, error_response, paginate_query, allowed_file, save_uploaded_file
from app.utils.decorators import admin_required, engineer_required, get_current_user
from app.services import (
    send_ticket_created_email, send_ticket_assigned_email,
    send_status_update_email, create_notification
)
import os

tickets_bp = Blueprint('tickets', __name__, url_prefix='/api/tickets')


def log_activity(ticket_id, user_id, action, field=None, old_val=None, new_val=None, desc=None):
    log = ActivityLog(
        ticket_id=ticket_id, user_id=user_id, action=action,
        field_changed=field, old_value=str(old_val) if old_val else None,
        new_value=str(new_val) if new_val else None,
        description=desc
    )
    db.session.add(log)


@tickets_bp.route('', methods=['GET'])
@jwt_required()
def list_tickets():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    query = Ticket.query

    # Role-based filtering
    if user.role == 'user':
        query = query.filter_by(created_by_id=user_id)
    elif user.role == 'engineer':
        query = query.filter(
            (Ticket.assigned_to_id == user_id) | (Ticket.created_by_id == user_id)
        )

    # Filters
    status = request.args.get('status')
    priority = request.args.get('priority')
    category = request.args.get('category')
    assigned_to = request.args.get('assigned_to')
    search = request.args.get('search')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'desc')

    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if category:
        query = query.filter_by(category=category)
    if assigned_to:
        if assigned_to == 'me':
            query = query.filter_by(assigned_to_id=user_id)
        elif assigned_to == 'unassigned':
            query = query.filter(Ticket.assigned_to_id.is_(None))
        else:
            query = query.filter_by(assigned_to_id=int(assigned_to))
    if search:
        query = query.filter(
            Ticket.title.ilike(f'%{search}%') |
            Ticket.description.ilike(f'%{search}%') |
            Ticket.ticket_number.ilike(f'%{search}%')
        )
    if date_from:
        query = query.filter(Ticket.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Ticket.created_at <= datetime.fromisoformat(date_to))

    # Sorting
    sort_col = getattr(Ticket, sort, Ticket.created_at)
    if order == 'desc':
        query = query.order_by(sort_col.desc())
    else:
        query = query.order_by(sort_col.asc())

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 15))
    result = paginate_query(query, page, per_page)

    return success_response({
        'tickets': [t.to_dict(include_relations=True) for t in result['items']],
        'pagination': {k: v for k, v in result.items() if k != 'items'}
    })


@tickets_bp.route('', methods=['POST'])
@jwt_required()
def create_ticket():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    data = request.get_json()

    if not data:
        return error_response('No data provided')

    title = data.get('title', '').strip()
    description = data.get('description', '').strip()
    if not title or not description:
        return error_response('Title and description are required')

    priority = data.get('priority', 'medium')
    if priority not in Ticket.PRIORITY_CHOICES:
        priority = 'medium'

    category = data.get('category', 'General')
    if category not in Ticket.CATEGORY_CHOICES:
        category = 'General'

    ticket = Ticket(
        ticket_number=Ticket.generate_ticket_number(),
        title=title,
        description=description,
        category=category,
        priority=priority,
        status='open',
        tags=data.get('tags'),
        due_date=datetime.fromisoformat(data['due_date']) if data.get('due_date') else None,
        created_by_id=user_id,
    )
    db.session.add(ticket)
    db.session.flush()

    log_activity(ticket.id, user_id, 'created', desc=f'Ticket created by {user.name}')
    db.session.commit()

    # Notifications
    try:
        send_ticket_created_email(ticket, user)
    except Exception as e:
        current_app.logger.warning(f"Email error: {e}")

    # Notify admins
    admins = User.query.filter_by(role='admin', is_active=True).all()
    for admin in admins:
        create_notification(admin.id, 'New Ticket', f'{user.name} raised: {ticket.title}',
                           f'/tickets/{ticket.id}', 'info')

    return success_response(ticket.to_dict(include_relations=True), 'Ticket created', 201)


@tickets_bp.route('/<int:ticket_id>', methods=['GET'])
@jwt_required()
def get_ticket(ticket_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    ticket = Ticket.query.get_or_404(ticket_id)

    # Access check
    if user.role == 'user' and ticket.created_by_id != user_id:
        return error_response('Access denied', 403)

    data = ticket.to_dict(include_relations=True)
    data['comments'] = [c.to_dict() for c in ticket.comments.order_by('created_at').all()
                        if not c.is_internal or user.role in ('admin', 'engineer')]
    data['attachments'] = [a.to_dict() for a in ticket.attachments.all()]
    data['activity_logs'] = [l.to_dict() for l in ticket.activity_logs.order_by('created_at').all()]
    return success_response(data)


@tickets_bp.route('/<int:ticket_id>', methods=['PUT'])
@jwt_required()
def update_ticket(ticket_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    ticket = Ticket.query.get_or_404(ticket_id)

    if user.role == 'user' and ticket.created_by_id != user_id:
        return error_response('Access denied', 403)

    data = request.get_json()
    if not data:
        return error_response('No data provided')

    if 'title' in data and user.role != 'user':
        ticket.title = data['title'].strip()
    if 'description' in data:
        ticket.description = data['description'].strip()
    if 'category' in data and data['category'] in Ticket.CATEGORY_CHOICES:
        ticket.category = data['category']
    if 'priority' in data and data['priority'] in Ticket.PRIORITY_CHOICES and user.role in ('admin', 'engineer'):
        old = ticket.priority
        ticket.priority = data['priority']
        log_activity(ticket.id, user_id, 'updated_priority', 'priority', old, data['priority'])
    if 'status' in data and data['status'] in Ticket.STATUS_CHOICES and user.role in ('admin', 'engineer'):
        old_status = ticket.status
        ticket.status = data['status']
        if data['status'] == 'resolved':
            ticket.resolved_at = datetime.utcnow()
        elif data['status'] == 'closed':
            ticket.closed_at = datetime.utcnow()
        log_activity(ticket.id, user_id, 'status_changed', 'status', old_status, data['status'])
        try:
            send_status_update_email(ticket, old_status, data['status'])
        except Exception as e:
            current_app.logger.warning(f"Email error: {e}")
        if ticket.creator:
            create_notification(ticket.created_by_id, 'Ticket Updated',
                               f'Status changed to {data["status"].replace("_"," ").title()}',
                               f'/tickets/{ticket.id}', 'info')
    if 'due_date' in data:
        ticket.due_date = datetime.fromisoformat(data['due_date']) if data['due_date'] else None
    if 'tags' in data:
        ticket.tags = data['tags']

    ticket.updated_at = datetime.utcnow()
    db.session.commit()
    return success_response(ticket.to_dict(include_relations=True), 'Ticket updated')


@tickets_bp.route('/<int:ticket_id>', methods=['DELETE'])
@admin_required
def delete_ticket(ticket_id):
    user_id = int(get_jwt_identity())
    ticket = Ticket.query.get_or_404(ticket_id)
    db.session.delete(ticket)
    db.session.commit()
    return success_response(message='Ticket deleted')


@tickets_bp.route('/<int:ticket_id>/assign', methods=['POST'])
@admin_required
def assign_ticket(ticket_id):
    user_id = int(get_jwt_identity())
    ticket = Ticket.query.get_or_404(ticket_id)
    data = request.get_json()
    engineer_id = data.get('engineer_id')

    if engineer_id:
        engineer = User.query.get(engineer_id)
        if not engineer or engineer.role not in ('admin', 'engineer'):
            return error_response('Invalid engineer', 400)
        old_assignee = ticket.assigned_to_id
        ticket.assigned_to_id = engineer_id
        if ticket.status == 'open':
            ticket.status = 'in_progress'
        log_activity(ticket.id, user_id, 'assigned', 'assigned_to', old_assignee, engineer_id,
                    f'Assigned to {engineer.name}')
        try:
            send_ticket_assigned_email(ticket, engineer)
        except Exception as e:
            current_app.logger.warning(f"Email error: {e}")
        create_notification(engineer_id, 'New Assignment',
                           f'Ticket {ticket.ticket_number} assigned to you',
                           f'/tickets/{ticket.id}', 'warning')
    else:
        ticket.assigned_to_id = None
        log_activity(ticket.id, user_id, 'unassigned', desc='Ticket unassigned')

    db.session.commit()
    return success_response(ticket.to_dict(include_relations=True), 'Ticket assigned')


@tickets_bp.route('/<int:ticket_id>/comments', methods=['POST'])
@jwt_required()
def add_comment(ticket_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    ticket = Ticket.query.get_or_404(ticket_id)

    if user.role == 'user' and ticket.created_by_id != user_id:
        return error_response('Access denied', 403)

    data = request.get_json()
    body = data.get('body', '').strip()
    if not body:
        return error_response('Comment body required')

    is_internal = data.get('is_internal', False) and user.role in ('admin', 'engineer')
    comment = Comment(ticket_id=ticket_id, user_id=user_id, body=body, is_internal=is_internal)
    db.session.add(comment)

    log_activity(ticket.id, user_id, 'commented', desc=f'{user.name} added a comment')

    # Notify ticket owner
    if ticket.created_by_id != user_id:
        create_notification(ticket.created_by_id, 'New Comment',
                           f'{user.name} commented on your ticket {ticket.ticket_number}',
                           f'/tickets/{ticket.id}', 'info')

    db.session.commit()
    return success_response(comment.to_dict(), 'Comment added', 201)


@tickets_bp.route('/<int:ticket_id>/attachments', methods=['POST'])
@jwt_required()
def upload_attachment(ticket_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    ticket = Ticket.query.get_or_404(ticket_id)

    if user.role == 'user' and ticket.created_by_id != user_id:
        return error_response('Access denied', 403)

    if 'file' not in request.files:
        return error_response('No file provided')

    file = request.files['file']
    if not file.filename:
        return error_response('No file selected')
    if not allowed_file(file.filename):
        return error_response('File type not allowed')

    original_filename, stored_filename, filepath = save_uploaded_file(file, subfolder=f'tickets/{ticket_id}')
    file_size = os.path.getsize(filepath)

    attachment = Attachment(
        ticket_id=ticket_id,
        uploaded_by_id=user_id,
        original_filename=original_filename,
        stored_filename=stored_filename,
        filepath=filepath,
        mimetype=file.mimetype,
        size=file_size
    )
    db.session.add(attachment)
    log_activity(ticket.id, user_id, 'attachment_added', desc=f'Attached file: {original_filename}')
    db.session.commit()

    return success_response(attachment.to_dict(), 'File uploaded', 201)


@tickets_bp.route('/attachments/<int:attachment_id>/download', methods=['GET'])
@jwt_required()
def download_attachment(attachment_id):
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    attachment = Attachment.query.get_or_404(attachment_id)
    ticket = Ticket.query.get(attachment.ticket_id)

    if user.role == 'user' and ticket.created_by_id != user_id:
        return error_response('Access denied', 403)

    return send_file(attachment.filepath, as_attachment=True,
                    download_name=attachment.original_filename,
                    mimetype=attachment.mimetype)
