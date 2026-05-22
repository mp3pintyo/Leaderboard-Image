import hmac
import secrets
from functools import wraps
from flask import abort, jsonify, request, session
from authlib.integrations.flask_client import OAuth

oauth = OAuth()
CSRF_SESSION_KEY = '_csrf_token'


def init_oauth(app):
    """Initialize OAuth providers based on available configuration."""
    oauth.init_app(app)

    if app.config.get('GOOGLE_CLIENT_ID'):
        oauth.register(
            name='google',
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )

    if app.config.get('GITHUB_CLIENT_ID'):
        oauth.register(
            name='github',
            api_base_url='https://api.github.com/',
            access_token_url='https://github.com/login/oauth/access_token',
            authorize_url='https://github.com/login/oauth/authorize',
            client_kwargs={'scope': 'read:user user:email'}
        )


def login_required(f):
    """Decorator: returns 401 JSON if user is not authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({"error": "Bejelentkezés szükséges a szavazáshoz."}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_csrf_token():
    """Get or create the per-session CSRF token."""
    token = session.get(CSRF_SESSION_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        session[CSRF_SESSION_KEY] = token
    return token


def _get_submitted_csrf_token():
    """Extract the CSRF token from headers, form data, or JSON."""
    header_token = request.headers.get('X-CSRF-Token')
    if header_token:
        return header_token

    form_token = request.form.get('csrf_token')
    if form_token:
        return form_token

    if request.is_json:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            return payload.get('csrf_token')

    return None


def csrf_protect(f):
    """Require a valid CSRF token for state-changing requests."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        expected_token = session.get(CSRF_SESSION_KEY)
        submitted_token = _get_submitted_csrf_token()

        if not expected_token or not submitted_token or not hmac.compare_digest(expected_token, str(submitted_token)):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Érvénytelen vagy hiányzó biztonsági token."}), 403
            abort(403)

        return f(*args, **kwargs)

    return decorated_function


def get_current_user():
    """Get the current logged-in user from session, or None."""
    return session.get('user')


def save_user(db, provider, provider_id, email, name):
    """Save or update user in the database. Returns user id."""
    existing = db.execute(
        'SELECT id FROM users WHERE provider = ? AND provider_id = ?',
        (provider, str(provider_id))
    ).fetchone()

    if existing:
        db.execute(
            'UPDATE users SET email = ?, name = ?, last_login = CURRENT_TIMESTAMP WHERE id = ?',
            (email, name, existing['id'])
        )
        return existing['id']
    else:
        cursor = db.execute(
            'INSERT INTO users (provider, provider_id, email, name) VALUES (?, ?, ?, ?)',
            (provider, str(provider_id), email, name)
        )
        return cursor.lastrowid
