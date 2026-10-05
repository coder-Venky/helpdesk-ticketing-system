from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import func, case
from app.extensions import db
from app.models.ticket import Ticket
from app.models.user import User
from app.models.attachment import Notification
from app.utils import success_response, error_response
from app.utils.decorators import admin_required, engineer_required
from app.services import generate_tickets_pdf, generate_tickets_excel

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')
reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')
users_bp = Blueprint('users', __name__, url_prefix='/api/users')
notifications_bp = Blueprint('notifications', __name__, url_prefix='/api/notifications')


# ─── Dashboard / Analytics ─────────────────────────────────────────────────────

@dashboard_bp.route('/stats', methods=['GET'])
@jwt_required()
def get_stats():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)

    base_query = Ticket.query
    if user.role == 'user':
        base_query = base_query.filter_by(created_by_id=user_id)
    elif user.role == 'engineer':
        base_query = base_query.filter(
            (Ticket.assigned_to_id == user_id) | (Ticket.created_by_id == user_id)
        )

    total = base_query.count()
    by_status = dict(db.session.query(Ticket.status, func.count(Ticket.id))
                     .filter(Ticket.id.in_([t.id for t in base_query.all()]))
                     .group_by(Ticket.status).all())
    by_priority = dict(db.session.query(Ticket.priority, func.count(Ticket.id))
                       .filter(Ticket.id.in_([t.id for t in base_query.all()]))
                       .group_by(Ticket.priority).all())
    by_category = dict(db.session.query(Ticket.category, func.count(Ticket.id))
                       .filter(Ticket.id.in_([t.id for t in base_query.all()]))
                       .group_by(Ticket.category).all())

    # Tickets over last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    daily_tickets = db.session.query(
        func.date(Ticket.created_at).label('date'),
        func.count(Ticket.id).label('count')
    ).filter(Ticket.created_at >= thirty_days_ago).group_by(func.date(Ticket.created_at)).all()

    # Engineer performance (admin only)
    engineer_stats = []
    if user.role == 'admin':
        engineers = User.query.filter(User.role.in_(['engineer', 'admin'])).all()
        for eng in engineers:
            assigned = Ticket.query.filter_by(assigned_to_id=eng.id).count()
            resolved = Ticket.query.filter_by(assigned_to_id=eng.id, status='resolved').count()
            engineer_stats.append({
                'name': eng.name,
                'assigned': assigned,
                'resolved': resolved,
            })

    # Avg resolution time
    resolved_tickets = base_query.filter(Ticket.status.in_(['resolved', 'closed'])).filter(Ticket.resolved_at.isnot(None)).all()
    avg_resolution = 0
    if resolved_tickets:
        total_hours = sum((t.resolved_at - t.created_at).total_seconds() / 3600 for t in resolved_tickets)
        avg_resolution = round(total_hours / len(resolved_tickets), 1)

    return success_response({
        'total': total,
        'by_status': {
            'open': by_status.get('open', 0),
            'in_progress': by_status.get('in_progress', 0),
            'resolved': by_status.get('resolved', 0),
            'closed': by_status.get('closed', 0),
        },
        'by_priority': {
            'low': by_priority.get('low', 0),
            'medium': by_priority.get('medium', 0),
            'high': by_priority.get('high', 0),
            'critical': by_priority.get('critical', 0),
        },
        'by_category': by_category,
        'daily_tickets': [{'date': str(r.date), 'count': r.count} for r in daily_tickets],
        'engineer_stats': engineer_stats,
        'avg_resolution_hours': avg_resolution,
    })


# ─── Reports ───────────────────────────────────────────────────────────────────

@reports_bp.route('/pdf', methods=['GET'])
@admin_required
def export_pdf():
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    total = Ticket.query.count()
    stats = {
        'open': Ticket.query.filter_by(status='open').count(),
        'in_progress': Ticket.query.filter_by(status='in_progress').count(),
        'resolved': Ticket.query.filter_by(status='resolved').count(),
        'closed': Ticket.query.filter_by(status='closed').count(),
    }
    buffer = generate_tickets_pdf(tickets, stats=stats)
    filename = f"helpdesk_report_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(buffer, mimetype='application/pdf', as_attachment=True, download_name=filename)


@reports_bp.route('/excel', methods=['GET'])
@admin_required
def export_excel():
    tickets = Ticket.query.order_by(Ticket.created_at.desc()).all()
    buffer = generate_tickets_excel(tickets)
    filename = f"helpdesk_report_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(buffer, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True, download_name=filename)


# ─── User Management ───────────────────────────────────────────────────────────

@users_bp.route('', methods=['GET'])
@admin_required
def list_users():
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    role = request.args.get('role')
    search = request.args.get('search')

    query = User.query
    if role:
        query = query.filter_by(role=role)
    if search:
        query = query.filter(
            User.name.ilike(f'%{search}%') | User.email.ilike(f'%{search}%')
        )
    query = query.order_by(User.created_at.desc())
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return success_response({
        'users': [u.to_dict() for u in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'page': paginated.page,
    })


@users_bp.route('/<int:user_id>', methods=['GET'])
@admin_required
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    data = user.to_dict()
    data['tickets_created'] = user.created_tickets.count()
    data['tickets_assigned'] = user.assigned_tickets.count()
    return success_response(data)


@users_bp.route('/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    user = User.query.get_or_404(user_id)
    data = request.get_json()

    if 'role' in data and data['role'] in ('admin', 'engineer', 'user'):
        user.role = data['role']
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'department' in data:
        user.department = data['department']
    if 'name' in data:
        user.name = data['name'].strip()

    db.session.commit()
    return success_response(user.to_dict(), 'User updated')


@users_bp.route('/engineers', methods=['GET'])
@jwt_required()
def list_engineers():
    engineers = User.query.filter(User.role.in_(['engineer', 'admin']), User.is_active == True).all()
    return success_response([u.to_dict() for u in engineers])


# ─── Notifications ─────────────────────────────────────────────────────────────

@notifications_bp.route('', methods=['GET'])
@jwt_required()
def get_notifications():
    user_id = int(get_jwt_identity())
    notifs = Notification.query.filter_by(user_id=user_id).order_by(
        Notification.created_at.desc()
    ).limit(20).all()
    unread = Notification.query.filter_by(user_id=user_id, is_read=False).count()
    return success_response({
        'notifications': [n.to_dict() for n in notifs],
        'unread_count': unread,
    })


@notifications_bp.route('/mark-read', methods=['POST'])
@jwt_required()
def mark_notifications_read():
    user_id = int(get_jwt_identity())
    data = request.get_json() or {}
    notif_ids = data.get('ids')
    if notif_ids:
        Notification.query.filter(
            Notification.user_id == user_id,
            Notification.id.in_(notif_ids)
        ).update({'is_read': True}, synchronize_session=False)
    else:
        Notification.query.filter_by(user_id=user_id, is_read=False).update({'is_read': True})
    db.session.commit()
    return success_response(message='Notifications marked as read')
