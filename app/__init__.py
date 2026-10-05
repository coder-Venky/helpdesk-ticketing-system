import os
from flask import Flask, jsonify
from app.config import config
from app.extensions import db, migrate, jwt, mail, cors, csrf


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')

    app = Flask(__name__, template_folder='templates', static_folder='../static')
    app.config.from_object(config.get(config_name, config['default']))

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    cors.init_app(app, supports_credentials=True, origins=['http://localhost:5000'])
    csrf.init_app(app)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Register blueprints
    from app.api import auth_bp, tickets_bp, dashboard_bp, reports_bp, users_bp, notifications_bp
    from app.web import web_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tickets_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(web_bp)

    # Exempt API blueprints from CSRF (they use JWT)
    csrf.exempt(auth_bp)
    csrf.exempt(tickets_bp)
    csrf.exempt(dashboard_bp)
    csrf.exempt(reports_bp)
    csrf.exempt(users_bp)
    csrf.exempt(notifications_bp)

    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token has expired', 'code': 'token_expired'}), 401

    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Invalid token', 'code': 'invalid_token'}), 401

    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Authorization token required', 'code': 'authorization_required'}), 401

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        from flask import request, render_template
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Resource not found'}), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import request
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Internal server error'}), 500
        return '<h1>500 - Internal Server Error</h1>', 500

    # Shell context
    @app.shell_context_processor
    def make_shell_context():
        from app.models import User, Ticket, Comment, Attachment, ActivityLog, Notification
        return {'db': db, 'User': User, 'Ticket': Ticket, 'Comment': Comment,
                'Attachment': Attachment, 'ActivityLog': ActivityLog, 'Notification': Notification}

    return app
