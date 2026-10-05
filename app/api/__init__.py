from app.api.auth import auth_bp
from app.api.tickets import tickets_bp
from app.api.dashboard import dashboard_bp, reports_bp, users_bp, notifications_bp

__all__ = ['auth_bp', 'tickets_bp', 'dashboard_bp', 'reports_bp', 'users_bp', 'notifications_bp']
