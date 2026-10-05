from flask import Blueprint, render_template, redirect, url_for, request, flash, make_response, session
from app.models.user import User
from app.models.ticket import Ticket
from app.models.attachment import Notification

web_bp = Blueprint('web', __name__)


def get_current_user_from_cookie():
    """Get current user from Flask session for web routes."""
    user_id = session.get('user_id')
    if user_id:
        return User.query.get(user_id)
    return None


@web_bp.route('/')
def index():
    user = get_current_user_from_cookie()
    if user:
        return redirect(url_for('web.dashboard'))
    return redirect(url_for('web.login'))


@web_bp.route('/login')
def login():
    user = get_current_user_from_cookie()
    if user:
        return redirect(url_for('web.dashboard'))
    return render_template('auth/login.html')


@web_bp.route('/register')
def register():
    user = get_current_user_from_cookie()
    if user:
        return redirect(url_for('web.dashboard'))
    return render_template('auth/register.html')


@web_bp.route('/forgot-password')
def forgot_password():
    return render_template('auth/forgot_password.html')


@web_bp.route('/reset-password')
def reset_password():
    token = request.args.get('token', '')
    email = request.args.get('email', '')
    return render_template('auth/reset_password.html', token=token, email=email)


@web_bp.route('/otp-login')
def otp_login():
    return render_template('auth/otp_login.html')


@web_bp.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for('web.login')))
    response.delete_cookie('access_token_cookie')
    response.delete_cookie('refresh_token_cookie')
    return response


@web_bp.route('/dashboard')
def dashboard():
    user = get_current_user_from_cookie()
    if not user:
        return redirect(url_for('web.login'))
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return render_template('admin/dashboard.html', current_user=user, unread_count=unread)


@web_bp.route('/tickets')
def tickets():
    user = get_current_user_from_cookie()
    if not user:
        return redirect(url_for('web.login'))
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return render_template('tickets/list.html', current_user=user, unread_count=unread,
                          categories=Ticket.CATEGORY_CHOICES,
                          statuses=Ticket.STATUS_CHOICES,
                          priorities=Ticket.PRIORITY_CHOICES)


@web_bp.route('/tickets/new')
def new_ticket():
    user = get_current_user_from_cookie()
    if not user:
        return redirect(url_for('web.login'))
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return render_template('tickets/create.html', current_user=user, unread_count=unread,
                          categories=Ticket.CATEGORY_CHOICES,
                          priorities=Ticket.PRIORITY_CHOICES)


@web_bp.route('/tickets/<int:ticket_id>')
def ticket_detail(ticket_id):
    user = get_current_user_from_cookie()
    if not user:
        return redirect(url_for('web.login'))
    ticket = Ticket.query.get_or_404(ticket_id)
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    engineers = User.query.filter(User.role.in_(['engineer', 'admin']), User.is_active == True).all()
    return render_template('tickets/detail.html', current_user=user, ticket=ticket,
                          engineers=engineers, unread_count=unread,
                          statuses=Ticket.STATUS_CHOICES,
                          priorities=Ticket.PRIORITY_CHOICES)


@web_bp.route('/admin/users')
def admin_users():
    user = get_current_user_from_cookie()
    if not user or user.role != 'admin':
        return redirect(url_for('web.dashboard'))
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return render_template('admin/users.html', current_user=user, unread_count=unread)


@web_bp.route('/profile')
def profile():
    user = get_current_user_from_cookie()
    if not user:
        return redirect(url_for('web.login'))
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return render_template('tickets/profile.html', current_user=user, unread_count=unread)


@web_bp.route('/reports')
def reports():
    user = get_current_user_from_cookie()
    if not user or user.role not in ('admin', 'engineer'):
        return redirect(url_for('web.dashboard'))
    unread = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return render_template('admin/reports.html', current_user=user, unread_count=unread)
