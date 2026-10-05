from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, session
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, set_access_cookies,
    set_refresh_cookies, unset_jwt_cookies
)
from app.extensions import db
from app.models.user import User
from app.utils import success_response, error_response
from app.services import (
    generate_otp_secret, generate_email_otp, verify_email_otp,
    generate_reset_token, send_otp_email, send_password_reset_email
)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

_otp_store = {}       # {email: (otp, expiry_ts)}
_reset_store = {}     # {token: (email, expiry_ts)}


@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    name = data.get('name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    role = data.get('role', 'user')

    if not all([name, email, password]):
        return error_response('Name, email and password are required')
    if len(password) < 8:
        return error_response('Password must be at least 8 characters')
    if role not in ['admin', 'engineer', 'user']:
        role = 'user'
    if User.query.filter_by(email=email).first():
        return error_response('Email already registered', 409)

    user = User(
        name=name, email=email, role=role,
        department=data.get('department'), phone=data.get('phone')
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    session['user_id'] = user.id
    resp, status = success_response({
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token,
    }, 'Registration successful', 201)
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp, status


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data:
        return error_response('No data provided')

    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return error_response('Invalid email or password', 401)
    if not user.is_active:
        return error_response('Account is deactivated. Contact admin.', 403)

    user.last_login = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    session['user_id'] = user.id
    resp, status = success_response({
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token,
    }, 'Login successful')
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp, status


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = int(get_jwt_identity())
    access_token = create_access_token(identity=str(user_id))
    return success_response({'access_token': access_token}, 'Token refreshed')


@auth_bp.route('/logout', methods=['POST'])
@jwt_required(optional=True)
def logout():
    session.clear()
    resp, status = success_response(message='Logged out successfully')
    unset_jwt_cookies(resp)
    return resp, status


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return error_response('User not found', 404)
    return success_response(user.to_dict())


@auth_bp.route('/otp/send', methods=['POST'])
def otp_send():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('No account with that email', 404)
    if not user.is_active:
        return error_response('Account deactivated', 403)

    if not user.otp_secret:
        user.otp_secret = generate_otp_secret()
        db.session.commit()

    otp = generate_email_otp(user.otp_secret)
    send_otp_email(user, otp)
    # Also log to console in dev
    current_app.logger.info(f"[DEV OTP] {user.email}: {otp}")
    return success_response(message='OTP sent to your email. Check server logs in dev mode.')


@auth_bp.route('/otp/verify', methods=['POST'])
def otp_verify():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()

    user = User.query.filter_by(email=email).first()
    if not user or not user.otp_secret:
        return error_response('Invalid request', 400)

    if not verify_email_otp(user.otp_secret, otp):
        return error_response('Invalid or expired OTP', 401)

    user.last_login = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    session['user_id'] = user.id
    resp, status = success_response({
        'user': user.to_dict(),
        'access_token': access_token,
        'refresh_token': refresh_token,
    }, 'OTP login successful')
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp, status


@auth_bp.route('/password/reset-request', methods=['POST'])
def password_reset_request():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user:
        # Don't reveal whether email exists
        return success_response(message='If that email exists, a reset link was sent.')

    import time, hashlib
    token = generate_reset_token(email)
    _reset_store[email] = (token, int(time.time()) + 3600)
    reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password?token={token}&email={email}"
    send_password_reset_email(user, reset_url)
    current_app.logger.info(f"[DEV RESET] {reset_url}")
    return success_response(message='If that email exists, a reset link was sent.')


@auth_bp.route('/password/reset', methods=['POST'])
def password_reset():
    import time
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    token = data.get('token', '').strip()
    new_password = data.get('new_password', '')

    if len(new_password) < 8:
        return error_response('Password must be at least 8 characters')

    stored = _reset_store.get(email)
    if not stored or stored[0] != token or time.time() > stored[1]:
        return error_response('Invalid or expired reset token', 400)

    user = User.query.filter_by(email=email).first()
    if not user:
        return error_response('User not found', 404)

    user.set_password(new_password)
    db.session.commit()
    del _reset_store[email]
    return success_response(message='Password reset successfully. You can now log in.')


@auth_bp.route('/token-from-session', methods=['POST'])
def token_from_session():
    """Issue fresh JWT tokens to a client that has a valid Flask session.
    This lets the frontend recover JWT tokens after localStorage is cleared,
    without requiring the user to log in again.
    """
    user_id = session.get('user_id')
    if not user_id:
        return error_response('No active session', 401)

    user = User.query.get(user_id)
    if not user or not user.is_active:
        return error_response('User not found or inactive', 401)

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    resp, status = success_response({
        'access_token': access_token,
        'refresh_token': refresh_token,
    }, 'Tokens issued from session')
    set_access_cookies(resp, access_token)
    set_refresh_cookies(resp, refresh_token)
    return resp, status


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
def update_profile():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return error_response('User not found', 404)

    data = request.get_json()
    if 'name' in data:
        user.name = data['name'].strip()
    if 'department' in data:
        user.department = data['department']
    if 'phone' in data:
        user.phone = data['phone']
    if 'current_password' in data and 'new_password' in data:
        if not user.check_password(data['current_password']):
            return error_response('Current password incorrect', 401)
        if len(data['new_password']) < 8:
            return error_response('New password must be at least 8 characters')
        user.set_password(data['new_password'])

    db.session.commit()
    return success_response(user.to_dict(), 'Profile updated')
