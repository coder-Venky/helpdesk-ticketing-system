from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from app.models.user import User


def role_required(*roles):
    """Decorator to restrict route access by user role."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            user_id = int(get_jwt_identity())
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return jsonify({'error': 'Account not found or inactive'}), 401
            if user.role not in roles:
                return jsonify({'error': f'Access denied. Required role: {", ".join(roles)}'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def admin_required(fn):
    return role_required('admin')(fn)


def engineer_required(fn):
    return role_required('admin', 'engineer')(fn)


def get_current_user():
    """Helper to retrieve the current JWT user from DB."""
    user_id = int(get_jwt_identity())
    if user_id:
        return User.query.get(user_id)
    return None
