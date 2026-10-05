import os
import uuid
from flask import current_app
from werkzeug.utils import secure_filename


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_uploaded_file(file, subfolder=''):
    """Save an uploaded file and return stored filename and path."""
    original_filename = secure_filename(file.filename)
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    stored_filename = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

    upload_dir = current_app.config['UPLOAD_FOLDER']
    if subfolder:
        upload_dir = os.path.join(upload_dir, subfolder)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, stored_filename)
    file.save(filepath)
    return original_filename, stored_filename, filepath


def paginate_query(query, page, per_page=15):
    """Return paginated results with metadata."""
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        'items': paginated.items,
        'total': paginated.total,
        'pages': paginated.pages,
        'page': paginated.page,
        'per_page': paginated.per_page,
        'has_next': paginated.has_next,
        'has_prev': paginated.has_prev,
    }


def success_response(data=None, message='Success', status_code=200):
    """Return a Flask (Response, status_code) tuple with JSON payload."""
    from flask import jsonify
    payload = {'success': True, 'message': message}
    if data is not None:
        payload['data'] = data
    return jsonify(payload), status_code


def error_response(message='An error occurred', status_code=400, errors=None):
    """Return a Flask (Response, status_code) tuple with JSON error payload."""
    from flask import jsonify
    payload = {'success': False, 'error': message}
    if errors:
        payload['errors'] = errors
    return jsonify(payload), status_code
