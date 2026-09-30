import os
import re
import json
import random
import secrets
import sqlite3
import sys
import glob
import logging
import datetime
import threading
import time
from collections import deque
import numpy as np
import ranking
from flask import Flask, render_template, jsonify, request, send_from_directory, abort, redirect, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix
from database import (close_db, get_db, init_db, get_prompt_ids, update_elo, immediate_transaction, utc_now_iso,
                      utc_now_naive, utc_iso_from_datetime, to_iso_utc, OUTCOME_WIN, OUTCOME_TIE, OUTCOME_BOTH_BAD)
from config import (DATA_DIR, ALLOWED_EXTENSIONS, DEFAULT_ELO, MODELS, DEFAULT_VIDEO_URL, REVEAL_DELAY_MS,
                    FROZEN_BOTTOM_COUNT, NEW_MODEL_BOOST_THRESHOLD, NEW_MODEL_BOOST_WEIGHT,
                    BATTLE_TTL_SECONDS, MAX_OPEN_BATTLES, MIN_VOTE_DELAY_MS, DAILY_VOTE_LIMIT,
                    BATTLE_RATE_LIMIT_PER_MINUTE, BT_BOOTSTRAP_ROUNDS, BT_PRIOR_GAMES, PRELIMINARY_MATCH_THRESHOLD,
                    PERSONAL_LEADERBOARD_MIN_VOTES,
                    DEFAULT_SECRET_KEY, SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET)
from auth import csrf_protect, get_csrf_token, oauth, init_oauth, login_required, get_current_user, save_user

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
logger = logging.getLogger('arena')


def model_display(model):
    """A megjelenítendő név: "Szolgáltató: Modell"."""
    return f"{model.get('provider')}: {model['name']}" if model.get('provider') else model['name']


def model_public(model_id):
    """Egy modell nyilvános azonosító adatai (szavazás után felfedhető)."""
    model = MODELS[model_id]
    return {
        'id': model_id,
        'name': model['name'],
        'provider': model.get('provider') or '',
        'display': model_display(model),
    }


def get_model_video(model):
    url = (model.get('video_url') or DEFAULT_VIDEO_URL).strip() or DEFAULT_VIDEO_URL
    return {
        "video_url": url,
        "video_is_custom": url.rstrip('/') != DEFAULT_VIDEO_URL.rstrip('/'),
    }


app = Flask(__name__)
app.config['DATA_DIR'] = DATA_DIR # Flask konfigurációban is tároljuk

# The generated images are stable assets. Keep them fresh enough for occasional
# replacements while allowing repeated Arena appearances to come from the
# browser cache instead of transferring the same multi-megabyte file again.
IMAGE_CACHE_MAX_AGE_SECONDS = 7 * 24 * 60 * 60

# Check if DATA_MODE is set for remote image loading
DATA_MODE = os.environ.get('DATA_MODE')
SESSION_ID_KEY = 'sid'
LOGIN_NEXT_KEY = 'login_next'
ALLOW_INSECURE_DEV_SECRET = __name__ == '__main__'

if SECRET_KEY == DEFAULT_SECRET_KEY and not ALLOW_INSECURE_DEV_SECRET:
    raise RuntimeError('SECRET_KEY must be set outside the direct local dev entrypoint.')

# Authentication and session configuration
app.secret_key = SECRET_KEY
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = DATA_MODE is not None
app.config['GOOGLE_CLIENT_ID'] = GOOGLE_CLIENT_ID
app.config['GOOGLE_CLIENT_SECRET'] = GOOGLE_CLIENT_SECRET
app.config['GITHUB_CLIENT_ID'] = GITHUB_CLIENT_ID
app.config['GITHUB_CLIENT_SECRET'] = GITHUB_CLIENT_SECRET

# Trust proxy headers for HTTPS and the client IP behind reverse proxy (Render.com)
if DATA_MODE:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

app.teardown_appcontext(close_db)

# Initialize OAuth providers
init_oauth(app)


@app.after_request
def set_security_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    if request.path.startswith('/api/'):
        response.headers.setdefault('Cache-Control', 'no-store')
    return response


@app.route('/static/js/<path:filename>')
def serve_js(filename):
    """Serve JavaScript files with proper MIME type for ES modules."""
    return send_from_directory('static/js', filename, mimetype='application/javascript')

# Adatbázis inicializálása indításkor (ha szükséges)
with app.app_context():
    init_db()

AVAILABLE_PROMPTS = [] # Gyorsítótárazzuk a prompt ID-kat
_prompt_text_cache = {}
_prompt_model_files_cache = {}
_battle_pairs_cache = None


def get_price_per_1000_images(min_price_per_image):
    """A konfigurált minimum API-árat alakítja USD / 1000 képre."""
    if not isinstance(min_price_per_image, (int, float)) or isinstance(min_price_per_image, bool):
        return None
    if min_price_per_image < 0:
        return None
    return round(float(min_price_per_image) * 1000, 4)

def update_available_prompts():
    """Frissíti az elérhető prompt ID-k listáját és üríti a hozzájuk tartozó gyorsítótárakat."""
    global AVAILABLE_PROMPTS, _battle_pairs_cache
    AVAILABLE_PROMPTS = get_prompt_ids()
    _prompt_text_cache.clear()
    _prompt_model_files_cache.clear()
    _battle_pairs_cache = None
    if not AVAILABLE_PROMPTS:
        logger.warning("No valid prompts found in data directory!")

def update_frozen_models(db=None):
    """Befagyasztja a leaderboard alsó FROZEN_BOTTOM_COUNT modelljét.

    A befagyasztott modellek nem vesznek részt az Arena Battle-ben,
    de továbbra is láthatók a Side-by-Side módban és a Leaderboard-on.
    """
    try:
        db = db or get_db()
        with db:
            db.execute("UPDATE model_elo SET frozen = 0")
            if not FROZEN_BOTTOM_COUNT or FROZEN_BOTTOM_COUNT <= 0:
                return
            # Modellek lekérdezése ELO szerint növekvő sorrendben (legrosszabbak elöl)
            rows = db.execute("SELECT model FROM model_elo ORDER BY elo ASC LIMIT ?", (FROZEN_BOTTOM_COUNT,)).fetchall()
            db.executemany("UPDATE model_elo SET frozen = 1 WHERE model = ?", [(r['model'],) for r in rows])
        logger.info("Frozen %d models at the bottom of the leaderboard.", len(rows))
    except sqlite3.Error:
        logger.exception("Error updating frozen models")

# Befagyasztott modellek frissítése indításkor (a függvény definíciója után)
with app.app_context():
    update_frozen_models()

# Manifest cache DATA_MODE-hoz
_manifest_cache = None

def load_manifest():
    """Betölti a manifest.json fájlt DATA_MODE-ban a képfájl kiterjesztes meghatározásához."""
    global _manifest_cache
    if _manifest_cache is None:
        manifest_path = os.path.join(app.config['DATA_DIR'], 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r', encoding='utf-8') as f:
                _manifest_cache = json.load(f)
            logger.info("Manifest loaded: %d prompts.", len(_manifest_cache))
        else:
            logger.warning("manifest.json not found! Run generate_manifest.py locally and commit it.")
            _manifest_cache = {}
    return _manifest_cache


def _manifest_filename(entry):
    """A manifest bejegyzés lehet egyszerű fájlnév vagy {"file": ..., "key": ...} objektum."""
    if isinstance(entry, dict):
        return entry.get('file')
    return entry


def find_model_file(prompt_id, model_base_name):
    """
    Megkeresi a megfelelő modell fájlt a megadott mappában, a kiterjesztéstől függetlenül.
    DATA_MODE esetén a manifest.json-ból olvassa ki a fájlnevet (nincs helyi kép).

    :param prompt_id: A prompt mappájának azonosítója
    :param model_base_name: A modell fájl alapneve kiterjesztés nélkül
    :return: A teljes fájlnév kiterjesztéssel, vagy None ha nem található
    """
    if DATA_MODE:
        manifest = load_manifest()
        return _manifest_filename(manifest.get(prompt_id, {}).get(model_base_name))

    directory = os.path.join(app.config['DATA_DIR'], prompt_id)

    # Megnézzük az összes lehetséges kiterjesztéssel, hogy létezik-e a fájl
    for ext in ALLOWED_EXTENSIONS:
        potential_file = f"{model_base_name}{ext}"
        if os.path.exists(os.path.join(directory, potential_file)):
            return potential_file

    # Ha nem találtuk meg a pontos egyezést, próbáljuk meg fájlmintával
    for file in glob.glob(os.path.join(directory, f"{glob.escape(model_base_name)}.*")):
        if os.path.splitext(file)[1].lower() in ALLOWED_EXTENSIONS:
            return os.path.basename(file)

    return None


def get_prompt_model_files(prompt_id):
    """{model_id: fájlnév} azoknak a modelleknek, amelyeknek van képe az adott prompthoz (gyorsítótárazva)."""
    files = _prompt_model_files_cache.get(prompt_id)
    if files is None:
        files = {}
        for model_id, model in MODELS.items():
            filename = find_model_file(prompt_id, model['filename'])
            if filename:
                files[model_id] = filename
        _prompt_model_files_cache[prompt_id] = files
    return files


def get_image_url(prompt_id, filename):
    """
    Get the full URL for an image file.
    Returns remote URL if DATA_MODE is set, otherwise local path.
    """
    if DATA_MODE:
        return f"{DATA_MODE}/{prompt_id}/{filename}"
    return f"/images/{prompt_id}/{filename}"


def get_model_image_url(prompt_id, model_id):
    filename = get_prompt_model_files(prompt_id).get(model_id)
    return get_image_url(prompt_id, filename) if filename else None


def read_prompt_text(prompt_id):
    """A prompt szövege (gyorsítótárazva). None, ha nem olvasható."""
    if prompt_id in _prompt_text_cache:
        return _prompt_text_cache[prompt_id]
    prompt_path = os.path.join(app.config['DATA_DIR'], prompt_id, 'prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            text = f.read().strip()
    except OSError:
        logger.exception("Error reading prompt file for prompt_id=%s", prompt_id)
        return None
    _prompt_text_cache[prompt_id] = text
    return text


class SlidingWindowRateLimiter:
    """Egyszerű, folyamaton belüli csúszóablakos korlátozó (egy Gunicorn workerrel pontos)."""

    def __init__(self, limit, window_seconds):
        self.limit = limit
        self.window = window_seconds
        self._hits = {}
        self._lock = threading.Lock()

    def allow(self, key):
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 10000:
                # Régi kulcsok takarítása, hogy a memória ne nőjön korlátlanul
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]:
                    del self._hits[stale]
            return True


battle_rate_limiter = SlidingWindowRateLimiter(BATTLE_RATE_LIMIT_PER_MINUTE, 60)
# Proxy mögött több felhasználó is osztozhat egy IP-címen, ezért ez csak laza külső korlát
ip_rate_limiter = SlidingWindowRateLimiter(BATTLE_RATE_LIMIT_PER_MINUTE * 10, 60)


def get_session_key():
    """Véletlen, sessionhöz kötött azonosító: a battle-ök ehhez a sessionhöz tartoznak."""
    sid = session.get(SESSION_ID_KEY)
    if not sid:
        sid = secrets.token_urlsafe(18)
        session[SESSION_ID_KEY] = sid
    return sid


def rate_limit_key():
    user = get_current_user()
    if user:
        return f"user:{user['id']}"
    return f"sid:{get_session_key()}"


def battle_request_allowed():
    return (ip_rate_limiter.allow(f"ip:{request.remote_addr}")
            and battle_rate_limiter.allow(rate_limit_key()))


def api_error(message, status, code=None):
    body = {"error": message}
    if code:
        body["code"] = code
    return jsonify(body), status


@app.before_request
def before_first_request_func():
    # Debug módban minden kérésnél frissítjük a prompt listát, hogy az új mappák
    # újraindítás nélkül megjelenjenek. Élesben csak az első kérésnél töltjük be.
    if app.debug or not AVAILABLE_PROMPTS:
        update_available_prompts()

# Szavazatok resetelésére szolgáló függvény
def reset_votes():
    """Törli az összes szavazatot és visszaállítja az ELO pontszámokat az alapértelmezettre."""
    try:
        db = get_db()
        now = utc_now_iso()
        with db:
            db.execute('DELETE FROM votes')
            db.execute('DELETE FROM battles')
            db.execute('DELETE FROM elo_history')
            db.execute('UPDATE model_elo SET elo = ?, frozen = 0, last_updated = ?', (DEFAULT_ELO, now))
            # Kezdeti ELO értékek rögzítése a historikus táblában is
            db.executemany('INSERT INTO elo_history (model, elo, timestamp) VALUES (?, ?, ?)',
                           [(model, DEFAULT_ELO, now) for model in MODELS.keys()])
        logger.info("Database reset: all votes and ELO history deleted.")
        return True
    except sqlite3.Error:
        logger.exception("Database error during reset")
        return False


@app.route('/')
def index():
    """Főoldal megjelenítése."""
    # A modellek listáját névvel és szolgáltatóval adjuk át a template-nek.
    # Rendezés display alapján, így a dropdownok is ABC-s listát mutatnak.
    models_for_template = sorted(
        ({**model_public(model_id), 'open_source': bool(model.get('open_source'))} for model_id, model in MODELS.items()),
        key=lambda m: m['display'].lower()
    )

    user = get_current_user()
    user_info = {'name': user['name'], 'provider': user['provider']} if user else None

    auth_providers = []
    if app.config.get('GOOGLE_CLIENT_ID'):
        auth_providers.append('google')
    if app.config.get('GITHUB_CLIENT_ID'):
        auth_providers.append('github')

    return render_template('index.html', models=models_for_template, reveal_delay_ms=REVEAL_DELAY_MS,
                           user=user_info, auth_providers=auth_providers, csrf_token=get_csrf_token(),
                           dev_mode=app.debug, login_error=request.args.get('login_error') == '1')


# --- Auth Endpoints ---

_SAFE_NEXT_RE = re.compile(r'^#/[\w\-/?=&.%,~]*$')


def _remember_login_next():
    next_route = request.args.get('next', '')
    if _SAFE_NEXT_RE.match(next_route):
        session[LOGIN_NEXT_KEY] = next_route
    else:
        session.pop(LOGIN_NEXT_KEY, None)


def _finish_login(user_id, name, provider):
    next_route = session.get(LOGIN_NEXT_KEY) or ''
    session.clear()
    session['user'] = {'id': user_id, 'name': name, 'provider': provider}
    get_csrf_token()
    return redirect(url_for('index') + (next_route if _SAFE_NEXT_RE.match(next_route) else ''))


@app.route('/auth/dev-login')
def auth_dev_login():
    """Fejlesztői bejelentkezés - CSAK debug módban érhető el."""
    if not app.debug:
        abort(404)
    _remember_login_next()
    db = get_db()
    with db:
        user_id = save_user(db, 'dev', 'dev-user', 'dev@localhost', 'Dev User')
    return _finish_login(user_id, 'Dev User', 'dev')


@app.route('/auth/login/<provider>')
def auth_login(provider):
    """Bejelentkezés indítása a megadott OAuth providerrel."""
    if provider not in ('google', 'github'):
        abort(404)
    client = oauth.create_client(provider)
    if client is None:
        abort(404)
    _remember_login_next()
    redirect_uri = url_for('auth_callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


def _fetch_oauth_user(provider, client):
    token = client.authorize_access_token()
    if provider == 'google':
        userinfo = token.get('userinfo') or client.userinfo()
        return {
            'provider': 'google',
            'provider_id': userinfo['sub'],
            'email': userinfo.get('email', ''),
            'name': userinfo.get('name') or userinfo.get('email') or 'Google User',
        }

    github_user = client.get('user').json()
    email = github_user.get('email') or ''
    if not email:
        emails = client.get('user/emails').json()
        if isinstance(emails, list):
            primary = next((e for e in emails if e.get('primary') and e.get('verified')), None)
            if primary:
                email = primary['email']
    return {
        'provider': 'github',
        'provider_id': str(github_user['id']),
        'email': email,
        'name': github_user.get('name') or github_user.get('login') or 'GitHub User',
    }


@app.route('/auth/callback/<provider>')
def auth_callback(provider):
    """OAuth callback a bejelentkezés befejezéséhez."""
    if provider not in ('google', 'github'):
        abort(404)
    client = oauth.create_client(provider)
    if client is None:
        abort(404)

    try:
        user_data = _fetch_oauth_user(provider, client)
    except Exception:
        # Megszakított bejelentkezés, lejárt state, hálózati hiba: ne 500-as oldal legyen
        logger.warning("OAuth login failed for provider=%s", provider, exc_info=True)
        return redirect(url_for('index', login_error=1))

    db = get_db()
    with db:
        user_id = save_user(db, user_data['provider'], user_data['provider_id'],
                            user_data['email'], user_data['name'])
    return _finish_login(user_id, user_data['name'], user_data['provider'])


@app.route('/auth/logout', methods=['POST'])
@csrf_protect
def auth_logout():
    """Kijelentkezés - session törlése."""
    session.clear()
    return redirect(url_for('index'))


@app.route('/api/auth/status')
def auth_status():
    """Visszaadja a bejelentkezési állapotot."""
    user = get_current_user()
    if user:
        return jsonify({'logged_in': True, 'user': {'name': user['name'], 'provider': user['provider']}})
    return jsonify({'logged_in': False})


@app.route('/images/<prompt_id>/<filename>')
def serve_image(prompt_id, filename):
    """Képfájlok kiszolgálása a data mappából."""
    # Biztonsági ellenőrzés: csak az engedélyezett kiterjesztéseket engedélyezzük
    if os.path.splitext(filename)[1].lower() not in ALLOWED_EXTENSIONS:
        abort(404)
    if prompt_id not in AVAILABLE_PROMPTS:
        abort(404)

    directory = os.path.join(app.config['DATA_DIR'], prompt_id)
    # `send_from_directory` biztonságosabb, mint kézzel összerakni az útvonalat
    response = send_from_directory(directory, filename, conditional=True, max_age=IMAGE_CACHE_MAX_AGE_SECONDS)
    response.headers['Cache-Control'] = (
        f'public, max-age={IMAGE_CACHE_MAX_AGE_SECONDS}, stale-while-revalidate=86400'
    )
    return response


# --- Arena Battle ---

def _battle_candidate_pairs():
    """Az összes olyan modellpár, amelynek legalább egy közös promptja van: {(a, b): [prompt_id, ...]}"""
    global _battle_pairs_cache
    if _battle_pairs_cache is None:
        prompts_by_model = {}
        for prompt_id in AVAILABLE_PROMPTS:
            for model_id in get_prompt_model_files(prompt_id):
                prompts_by_model.setdefault(model_id, set()).add(prompt_id)
        model_ids = sorted(prompts_by_model)
        pairs = {}
        for i, a in enumerate(model_ids):
            for b in model_ids[i + 1:]:
                shared = prompts_by_model[a] & prompts_by_model[b]
                if shared:
                    pairs[(a, b)] = sorted(shared)
        _battle_pairs_cache = pairs
    return _battle_pairs_cache


def get_pair_and_match_counts(db):
    """(párok meccsszáma {(a, b): n} rendezett kulccsal, modellenkénti meccsszám)"""
    pair_counts, match_counts = {}, {}
    for row in db.execute('SELECT winner, loser, COUNT(*) AS n FROM votes GROUP BY winner, loser'):
        a, b = sorted((row['winner'], row['loser']))
        pair_counts[(a, b)] = pair_counts.get((a, b), 0) + row['n']
        match_counts[a] = match_counts.get(a, 0) + row['n']
        match_counts[b] = match_counts.get(b, 0) + row['n']
    return pair_counts, match_counts


def choose_battle(db):
    """Kiválaszt egy modellpárt és egy közös promptot.

    A párok súlya 1 / (1 + eddigi meccsek), így a ritkán látott párosítások gyakrabban kerülnek elő
    (és ezzel az új modellek is). A kevés meccses modelleket tartalmazó párok extra boostot kapnak.
    """
    pairs = _battle_candidate_pairs()
    frozen = {r['model'] for r in db.execute('SELECT model FROM model_elo WHERE COALESCE(frozen, 0) = 1')}
    eligible = [(pair, prompts) for pair, prompts in pairs.items()
                if pair[0] in MODELS and pair[1] in MODELS and pair[0] not in frozen and pair[1] not in frozen]
    if not eligible:
        # Ha a befagyasztás miatt nincs pár, használjuk az összeset
        eligible = [(pair, prompts) for pair, prompts in pairs.items() if pair[0] in MODELS and pair[1] in MODELS]
    if not eligible:
        return None

    pair_counts, match_counts = get_pair_and_match_counts(db)
    weights = []
    for (a, b), _prompts in eligible:
        weight = 1.0 / (1 + pair_counts.get((a, b), 0))
        if min(match_counts.get(a, 0), match_counts.get(b, 0)) < NEW_MODEL_BOOST_THRESHOLD:
            weight *= NEW_MODEL_BOOST_WEIGHT
        weights.append(weight)

    (a, b), prompts = random.choices(eligible, weights=weights, k=1)[0]
    # Véletlenszerű oldal-elosztás, hogy ne legyen oldalbias
    if random.random() < 0.5:
        a, b = b, a
    return random.choice(prompts), a, b


def _expire_extra_battles(db, session_key, now):
    db.execute(
        '''UPDATE battles SET resolved_at = ?, outcome = 'expired'
           WHERE session_key = ? AND resolved_at IS NULL AND id NOT IN (
               SELECT id FROM battles WHERE session_key = ? AND resolved_at IS NULL
               ORDER BY issued_at DESC LIMIT ?)''',
        (now, session_key, session_key, MAX_OPEN_BATTLES)
    )


def _cleanup_old_battles(db):
    cutoff = utc_iso_from_datetime(utc_now_naive() - datetime.timedelta(days=7))
    db.execute('DELETE FROM battles WHERE issued_at < ?', (cutoff,))


@app.route('/api/battle_data')
def get_battle_data():
    """Új vak battle kiadása. A modellek kiléte csak szavazás/kihagyás után derül ki."""
    if not AVAILABLE_PROMPTS:
        return api_error("Nincs elérhető prompt.", 500)
    if not battle_request_allowed():
        return api_error("Túl sok kérés. Várj egy kicsit, mielőtt új párt kérsz.", 429, 'rate_limited')

    db = get_db()
    choice = choose_battle(db)
    if not choice:
        return api_error("Nincs elég modell a battle-höz.", 500)
    prompt_id, model_a, model_b = choice

    prompt_text = read_prompt_text(prompt_id)
    image_a = get_model_image_url(prompt_id, model_a)
    image_b = get_model_image_url(prompt_id, model_b)
    if prompt_text is None or not image_a or not image_b:
        return api_error("A battle adatai nem tölthetők be.", 500)

    user = get_current_user()
    session_key = get_session_key()
    battle_id = secrets.token_urlsafe(16)
    now = utc_now_iso()
    with db:
        db.execute(
            '''INSERT INTO battles (id, session_key, user_id, prompt_id, model_a, model_b, issued_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (battle_id, session_key, user['id'] if user else None, prompt_id, model_a, model_b, now)
        )
        _expire_extra_battles(db, session_key, now)
        if random.random() < 0.02:
            _cleanup_old_battles(db)

    return jsonify({
        "battle_id": battle_id,
        "prompt_id": prompt_id,
        "prompt_text": prompt_text,
        "image_a": image_a,
        "image_b": image_b,
        "vote_delay_ms": MIN_VOTE_DELAY_MS,
    })


class BattleError(Exception):
    def __init__(self, message, status, code='battle_closed'):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def _parse_iso(value):
    return datetime.datetime.fromisoformat(to_iso_utc(value).rstrip('Z'))


def _load_open_battle(db, battle_id):
    """Az aktuális sessionhöz tartozó, még nem lezárt és le nem járt battle."""
    if not isinstance(battle_id, str) or not battle_id:
        raise BattleError("Hiányzó battle azonosító.", 400, 'bad_request')
    battle = db.execute('SELECT * FROM battles WHERE id = ?', (battle_id,)).fetchone()
    if not battle or battle['session_key'] != session.get(SESSION_ID_KEY):
        raise BattleError("Ismeretlen battle. Tölts be új párt.", 409)
    if battle['resolved_at']:
        raise BattleError("Erre a párra már szavaztál, vagy lejárt.", 409)
    age = utc_now_naive() - _parse_iso(battle['issued_at'])
    if age.total_seconds() > BATTLE_TTL_SECONDS:
        raise BattleError("A battle lejárt. Tölts be új párt.", 409)
    return battle, age


def _votes_today(db, user_id):
    today = utc_now_naive().strftime('%Y-%m-%d')
    return db.execute('SELECT COUNT(*) FROM votes WHERE user_id = ? AND voted_at >= ?',
                      (user_id, today)).fetchone()[0]


def _resolve_battle(db, battle_id, outcome):
    cur = db.execute('UPDATE battles SET resolved_at = ?, outcome = ? WHERE id = ? AND resolved_at IS NULL',
                     (utc_now_iso(), outcome, battle_id))
    if cur.rowcount != 1:
        raise BattleError("Erre a párra már szavaztál.", 409)


VOTE_CHOICES = {'a', 'b', OUTCOME_TIE, OUTCOME_BOTH_BAD}


@app.route('/api/vote', methods=['POST'])
@login_required
@csrf_protect
def record_vote():
    """Szavazat rögzítése egy kiadott battle-re: 'a', 'b', 'tie' vagy 'both_bad'."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return api_error("Érvénytelen kérésformátum.", 400)
    choice = data.get('choice')
    if choice not in VOTE_CHOICES:
        return api_error("Érvénytelen szavazat.", 400)

    user = get_current_user()
    db = get_db()
    try:
        with immediate_transaction(db):
            battle, age = _load_open_battle(db, data.get('battle_id'))
            if age.total_seconds() * 1000 < MIN_VOTE_DELAY_MS:
                raise BattleError("Túl gyors szavazás. Nézd meg a képeket, mielőtt döntesz.", 429, 'too_fast')
            votes_today = _votes_today(db, user['id'])
            if votes_today >= DAILY_VOTE_LIMIT:
                raise BattleError(f"Elérted a napi {DAILY_VOTE_LIMIT} szavazatos limitet. Holnap folytathatod!", 429, 'daily_limit')

            model_a, model_b = battle['model_a'], battle['model_b']
            if choice == 'a':
                winner, loser, outcome, score_a = model_a, model_b, OUTCOME_WIN, 1.0
            elif choice == 'b':
                winner, loser, outcome, score_a = model_b, model_a, OUTCOME_WIN, 0.0
            else:
                # Döntetlennél winner = bal, loser = jobb oldali modell; az outcome jelzi a döntetlent
                winner, loser, outcome, score_a = model_a, model_b, choice, 0.5

            _resolve_battle(db, battle['id'], choice)
            db.execute(
                '''INSERT INTO votes (prompt_id, winner, loser, user_id, voted_at, outcome, left_model, battle_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (battle['prompt_id'], winner, loser, user['id'], utc_now_iso(), outcome, model_a, battle['id'])
            )
            elo_changes = update_elo(db, model_a, model_b, score_a)
    except BattleError as e:
        return api_error(e.message, e.status, e.code)
    except sqlite3.Error:
        logger.exception("Database error while recording vote")
        return api_error("Adatbázis hiba a szavazat mentésekor.", 500)

    if FROZEN_BOTTOM_COUNT and FROZEN_BOTTOM_COUNT > 0:
        update_frozen_models(db)

    def reveal(model_id):
        old, new = elo_changes[model_id]
        return {**model_public(model_id), "elo_before": round(old, 1), "elo_after": round(new, 1),
                "elo_delta": round(new - old, 1)}

    return jsonify({
        "success": True,
        "choice": choice,
        "model_a": reveal(model_a),
        "model_b": reveal(model_b),
        "votes_today": votes_today + 1,
        "daily_limit": DAILY_VOTE_LIMIT,
    })


@app.route('/api/battle/skip', methods=['POST'])
@csrf_protect
def skip_battle():
    """Battle kihagyása: a pár lezárul (többé nem szavazható), a modellek kiléte felfedhető."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return api_error("Érvénytelen kérésformátum.", 400)
    db = get_db()
    try:
        with immediate_transaction(db):
            battle, _age = _load_open_battle(db, data.get('battle_id'))
            _resolve_battle(db, battle['id'], 'skip')
    except BattleError as e:
        return api_error(e.message, e.status, e.code)
    return jsonify({"success": True, "model_a": model_public(battle['model_a']),
                    "model_b": model_public(battle['model_b'])})


# --- Side-by-Side ---

@app.route('/api/side_by_side_data')
def get_side_by_side_data():
    """Adatok a Side-by-Side módhoz: 2-3 modell képe ugyanarra a promptra.

    Paraméterek: model1, model2, [model3], és opcionálisan
    prompt_id (konkrét prompt), after (a következő prompt ezután) vagy previous_prompt_id (véletlen, de ne ez).
    Csak olyan promptot választ, amelyhez minden kiválasztott modellnek van képe.
    """
    model_ids = [request.args.get('model1'), request.args.get('model2')]
    if request.args.get('model3'):
        model_ids.append(request.args.get('model3'))

    if not model_ids[0] or not model_ids[1]:
        return api_error("Legalább két modellt ki kell választani.", 400)
    if any(m not in MODELS for m in model_ids):
        return api_error("Ismeretlen modell.", 400)
    if len(set(model_ids)) != len(model_ids):
        return api_error("Különböző modelleket válassz.", 400)
    if not AVAILABLE_PROMPTS:
        return api_error("Nincs elérhető prompt.", 500)

    candidates = [p for p in AVAILABLE_PROMPTS
                  if all(m in get_prompt_model_files(p) for m in model_ids)]
    if not candidates:
        return api_error("Ehhez a modellkombinációhoz nincs közös prompt.", 404)

    requested = request.args.get('prompt_id')
    after = request.args.get('after')
    previous = request.args.get('previous_prompt_id')
    if requested:
        if requested not in candidates:
            return api_error("Ehhez a prompthoz nincs meg minden kiválasztott modell képe.", 404)
        prompt_id = requested
    elif after:
        later = [p for p in candidates if p > after]
        prompt_id = later[0] if later else candidates[0]
    else:
        pool = [p for p in candidates if p != previous] or candidates
        prompt_id = random.choice(pool)

    prompt_text = read_prompt_text(prompt_id)
    if prompt_text is None:
        return api_error("A prompt nem olvasható.", 500)

    data = {"prompt_id": prompt_id, "prompt_text": prompt_text, "prompt_ids": candidates}
    for index, model_id in enumerate(model_ids, start=1):
        data[f"model{index}"] = {**model_public(model_id), "image_url": get_model_image_url(prompt_id, model_id)}
    return jsonify(data)


@app.route('/api/get_image')
def get_image_for_model():
    """Visszaadja egy adott modell képének URL-jét egy adott prompt ID-hoz."""
    model_id = request.args.get('model')
    prompt_id = request.args.get('prompt_id')

    if not model_id or not prompt_id:
        return api_error("A model és a prompt_id paraméter kötelező.", 400)
    if model_id not in MODELS:
        return api_error("Ismeretlen modell.", 400)
    if prompt_id not in AVAILABLE_PROMPTS:
        return api_error("Ismeretlen prompt.", 400)
    image_url = get_model_image_url(prompt_id, model_id)
    if not image_url:
        return api_error("Ehhez a prompthoz nincs kép ettől a modelltől.", 404)
    return jsonify({"image_url": image_url})


# --- Statisztikák ---

def get_model_stats(db, user_id=None):
    """Modellenként: győzelmek, vereségek, döntetlenek és összes meccs."""
    where, params = ('WHERE user_id = ?', (user_id, user_id)) if user_id is not None else ('', ())
    rows = db.execute(f'''
        SELECT model, SUM(w) AS wins, SUM(l) AS losses, SUM(t) AS ties FROM (
            SELECT winner AS model, (outcome = 'win') AS w, 0 AS l, (outcome != 'win') AS t FROM votes {where}
            UNION ALL
            SELECT loser AS model, 0 AS w, (outcome = 'win') AS l, (outcome != 'win') AS t FROM votes {where}
        ) GROUP BY model
    ''', params).fetchall()
    stats = {}
    for row in rows:
        wins, losses, ties = row['wins'] or 0, row['losses'] or 0, row['ties'] or 0
        stats[row['model']] = {'wins': wins, 'losses': losses, 'ties': ties, 'matches': wins + losses + ties}
    return stats


def win_rate(stats):
    """Győzelmi arány %-ban; a döntetlen fél győzelemnek számít."""
    if not stats or not stats['matches']:
        return 0.0
    return round((stats['wins'] + 0.5 * stats['ties']) / stats['matches'] * 100, 2)


def filter_model_type(model, model_type):
    is_open_source = bool(model.get('open_source'))
    return not ((model_type == 'open-source' and not is_open_source) or
                (model_type == 'closed-source' and is_open_source))


def build_leaderboard_row(model_id, stats, elo, frozen=False):
    model = MODELS[model_id]
    stats = stats or {'wins': 0, 'losses': 0, 'ties': 0, 'matches': 0}
    return {
        **model_public(model_id),
        **get_model_video(model),
        "release_date": model.get('release_date') or '',
        "max_resolution": model.get('max_resolution') or '',
        "pricing": model.get('pricing') or '',
        "price_per_1000": get_price_per_1000_images(model.get('min_api_price_per_image')),
        "wins": stats['wins'],
        "losses": stats['losses'],
        "ties": stats['ties'],
        "matches": stats['matches'],
        "win_rate": win_rate(stats),
        "elo": round(elo, 1),
        "open_source": bool(model.get('open_source')),
        "frozen": frozen,
    }


# --- Bradley-Terry rangsor ---

MODEL_IDS = list(MODELS.keys())
MODEL_INDEX = {model_id: index for index, model_id in enumerate(MODEL_IDS)}
RANKING_CACHE_SECONDS = 30
_ranking_cache = {'key': None, 'computed_at': 0.0, 'data': None}
_ranking_lock = threading.Lock()


def load_vote_pairs(db, user_id=None):
    """(i, j, score_i) hármasok a Bradley-Terry illesztéshez (döntetlen = 0.5)."""
    query = 'SELECT winner, loser, outcome FROM votes'
    params = ()
    if user_id is not None:
        query += ' WHERE user_id = ?'
        params = (user_id,)
    pairs = []
    for row in db.execute(query, params):
        i, j = MODEL_INDEX.get(row['winner']), MODEL_INDEX.get(row['loser'])
        if i is None or j is None:
            continue
        pairs.append((i, j, 1.0 if row['outcome'] == OUTCOME_WIN else 0.5))
    return pairs


def get_global_ranking(db):
    """A globális BT rangsor. Új szavazat után legfeljebb RANKING_CACHE_SECONDS-ig a régi eredményt adja,
    így gyakori szavazásnál sem számolunk minden kérésre újra."""
    key = tuple(db.execute('SELECT COUNT(*), COALESCE(MAX(id), 0) FROM votes').fetchone())
    now = time.monotonic()
    with _ranking_lock:
        cached = _ranking_cache['data']
        if cached is not None and (_ranking_cache['key'] == key or now - _ranking_cache['computed_at'] < RANKING_CACHE_SECONDS):
            return cached
        result = ranking.compute_ratings(load_vote_pairs(db), len(MODEL_IDS), BT_PRIOR_GAMES, BT_BOOTSTRAP_ROUNDS)
        data = {**result, 'computed_at': utc_now_iso(), 'vote_count': key[0]}
        _ranking_cache.update(key=key, computed_at=now, data=data)
        return data


def apply_ranking(rows, rating, ci_lower=None, ci_upper=None):
    """Pontszám, CI és helyezéssáv a (már szűrt) sorokhoz; rendezés pontszám szerint.
    A helyezéssáv a megjelenített (szűrt) modellek között értendő."""
    for row in rows:
        index = MODEL_INDEX[row['id']]
        row['score'] = round(float(rating[index]), 1)
        if ci_lower is not None and row['matches'] > 0:
            row['ci_lower'] = round(float(ci_lower[index]), 1)
            row['ci_upper'] = round(float(ci_upper[index]), 1)
        else:
            row['ci_lower'] = row['ci_upper'] = None
        row['preliminary'] = row['matches'] < PRELIMINARY_MATCH_THRESHOLD

    # Adat nélküli modellek a lista végére kerülnek, helyezés nélkül
    rows.sort(key=lambda r: (r['matches'] == 0, -r['score']))
    with_ci = [r for r in rows if r['ci_lower'] is not None]
    if with_ci:
        best, worst = ranking.rank_spread([r['ci_lower'] for r in with_ci], [r['ci_upper'] for r in with_ci])
        for row, b, w in zip(with_ci, best, worst):
            row['rank'], row['rank_worst'] = int(b), int(w)
    for position, row in enumerate(rows, start=1):
        if 'rank' not in row:
            has_rank = row['matches'] > 0
            row['rank'] = row['rank_worst'] = position if has_rank else None
    return rows


@app.route('/api/leaderboard')
def get_leaderboard():
    """Leaderboard: Bradley-Terry pontszám 95%-os CI-vel, helyezéssávval, szavazatszámmal.
    Az online ELO (az ELO-történet grafikon alapja) az `elo` mezőben marad meg."""
    try:
        model_type = request.args.get('model_type', 'all')
        db = get_db()
        stats = get_model_stats(db)
        elo_data = {row['model']: row for row in db.execute('SELECT model, elo, COALESCE(frozen, 0) AS frozen FROM model_elo')}
        ranking_data = get_global_ranking(db)

        rows = []
        for model_id, model in MODELS.items():
            if not filter_model_type(model, model_type):
                continue
            elo_row = elo_data.get(model_id)
            rows.append(build_leaderboard_row(
                model_id, stats.get(model_id),
                elo_row['elo'] if elo_row else DEFAULT_ELO,
                bool(elo_row['frozen']) if elo_row else False,
            ))
        return jsonify(apply_ranking(rows, ranking_data['rating'], ranking_data['ci_lower'], ranking_data['ci_upper']))
    except sqlite3.Error:
        logger.exception("Database error while fetching leaderboard")
        return api_error("Adatbázis hiba a leaderboard lekérésekor.", 500)


@app.route('/api/leaderboard/stats')
def get_leaderboard_stats():
    """Összesítő és módszertani adatok: szavazatok, döntetlenek, oldaltorzítás."""
    db = get_db()
    totals = db.execute('''
        SELECT COUNT(*) AS total,
               SUM(outcome = 'win') AS decisive,
               SUM(outcome = 'tie') AS ties,
               SUM(outcome = 'both_bad') AS both_bad,
               COUNT(DISTINCT user_id) AS voters
        FROM votes
    ''').fetchone()
    side = db.execute('''
        SELECT COUNT(*) AS n, SUM(winner = left_model) AS left_wins
        FROM votes WHERE outcome = 'win' AND left_model IS NOT NULL
    ''').fetchone()
    n, left_wins = side['n'] or 0, side['left_wins'] or 0
    low, high = ranking.wilson_interval(left_wins, n)
    ranking_data = get_global_ranking(db)
    return jsonify({
        "total_votes": totals['total'] or 0,
        "decisive_votes": totals['decisive'] or 0,
        "ties": totals['ties'] or 0,
        "both_bad": totals['both_bad'] or 0,
        "voters": totals['voters'] or 0,
        "position_bias": {
            "votes": n,
            "left_win_rate": round(left_wins / n * 100, 1) if n else None,
            "ci_lower": round(low * 100, 1) if low is not None else None,
            "ci_upper": round(high * 100, 1) if high is not None else None,
        },
        "method": {
            "name": "Bradley-Terry (MLE)",
            "bootstrap_rounds": BT_BOOTSTRAP_ROUNDS,
            "prior_games": BT_PRIOR_GAMES,
            "preliminary_threshold": PRELIMINARY_MATCH_THRESHOLD,
            "computed_at": ranking_data['computed_at'],
        },
    })


@app.route('/api/leaderboard/matrix')
def get_leaderboard_matrix():
    """Párharc-mátrix a top N modellre: tényleges győzelmi arány, meccsszám és a BT által várt arány.
    cells[i][j] = a sorban lévő i. modell eredménye az oszlopban lévő j. modell ellen."""
    try:
        top = max(2, min(int(request.args.get('top', 12)), 25))
    except ValueError:
        top = 12
    model_type = request.args.get('model_type', 'all')
    db = get_db()
    ranking_data = get_global_ranking(db)
    stats = get_model_stats(db)
    candidates = [m for m in MODEL_IDS
                  if filter_model_type(MODELS[m], model_type) and stats.get(m, {}).get('matches', 0) > 0]
    candidates.sort(key=lambda m: -ranking_data['rating'][MODEL_INDEX[m]])
    selected = candidates[:top]
    idx = [MODEL_INDEX[m] for m in selected]
    wins = ranking_data['wins'][np.ix_(idx, idx)]
    games = wins + wins.T
    rating = ranking_data['rating'][idx]
    expected = 1.0 / (1.0 + 10 ** ((rating[None, :] - rating[:, None]) / 400))

    def cell(i, j):
        if i == j:
            return None
        n = float(games[i, j])
        return {
            "win_rate": round(float(wins[i, j]) / n * 100, 1) if n else None,
            "games": int(round(n)),
            "expected": round(float(expected[i, j]) * 100, 1),
        }

    return jsonify({
        "models": [{**model_public(m), "score": round(float(ranking_data['rating'][MODEL_INDEX[m]]), 1)} for m in selected],
        "cells": [[cell(i, j) for j in range(len(selected))] for i in range(len(selected))],
    })


@app.route('/api/leaderboard/mine')
@login_required
def get_personal_leaderboard():
    """Saját toplista: Bradley-Terry pontszám csak a felhasználó saját szavazataiból.
    PERSONAL_LEADERBOARD_MIN_VOTES szavazat alatt még nem számolunk (túl zajos lenne)."""
    try:
        user = get_current_user()
        db = get_db()
        model_type = request.args.get('model_type', 'all')
        pairs = load_vote_pairs(db, user_id=user['id'])
        base = {"vote_count": len(pairs), "min_votes": PERSONAL_LEADERBOARD_MIN_VOTES}
        if len(pairs) < PERSONAL_LEADERBOARD_MIN_VOTES:
            return jsonify({**base, "unlocked": False, "leaderboard": []})

        result = ranking.compute_ratings(pairs, len(MODEL_IDS), BT_PRIOR_GAMES, bootstrap_rounds=0)
        stats = get_model_stats(db, user_id=user['id'])
        rows = [
            build_leaderboard_row(model_id, stats.get(model_id), DEFAULT_ELO)
            for model_id, model in MODELS.items()
            if filter_model_type(model, model_type) and stats.get(model_id, {}).get('matches', 0) > 0
        ]
        return jsonify({**base, "unlocked": True, "leaderboard": apply_ranking(rows, result['rating'])})
    except sqlite3.Error:
        logger.exception("Database error (personal leaderboard)")
        return api_error("Adatbázis hiba.", 500)


ELO_HISTORY_RANGES = {'1w': 7, '2w': 14, '1m': 30, '3m': 90}
ELO_HISTORY_MAX_POINTS = 160


@app.route('/api/elo_history')
def get_elo_history():
    """Az online ELO időbeli alakulása a top N modellre, szerveroldalon ritkítva.

    Paraméterek: range (1w, 2w, 1m, 3m, all), top (1-30).
    Időszakonként (bucket) csak az utolsó értéket adjuk vissza, így a válasz mérete
    nem nő a szavazatok számával.
    """
    try:
        top = max(1, min(int(request.args.get('top', 10)), 30))
    except ValueError:
        top = 10
    range_key = request.args.get('range', 'all')
    db = get_db()
    current = [(row['model'], row['elo']) for row in db.execute('SELECT model, elo FROM model_elo ORDER BY elo DESC')
               if row['model'] in MODELS]
    selected = [model_id for model_id, _elo in current[:top]]
    if not selected:
        return jsonify({"series": [], "models_total": 0})

    end = utc_now_naive()
    if range_key in ELO_HISTORY_RANGES:
        start = end - datetime.timedelta(days=ELO_HISTORY_RANGES[range_key])
    else:
        first = db.execute('SELECT MIN(timestamp) FROM elo_history').fetchone()[0]
        start = _parse_iso(first) if first else end
    span = max((end - start).total_seconds(), 3600.0)
    bucket_seconds = max(span / ELO_HISTORY_MAX_POINTS, 60.0)
    start_iso = utc_iso_from_datetime(start)
    placeholders = ','.join('?' * len(selected))

    series = {model_id: {} for model_id in selected}
    # A tartomány előtti utolsó érték a vonal kezdőpontja
    for row in db.execute(f'''
        SELECT h.model, h.elo FROM elo_history h
        JOIN (SELECT model, MAX(id) AS id FROM elo_history
              WHERE timestamp < ? AND model IN ({placeholders}) GROUP BY model) last
        ON h.id = last.id
    ''', (start_iso, *selected)):
        series[row['model']][0] = (start_iso, row['elo'])
    for row in db.execute(f'''
        SELECT model, elo, timestamp FROM elo_history
        WHERE timestamp >= ? AND model IN ({placeholders}) ORDER BY timestamp, id
    ''', (start_iso, *selected)):
        timestamp = to_iso_utc(row['timestamp'])
        bucket = int((_parse_iso(timestamp) - start).total_seconds() // bucket_seconds) + 1
        series[row['model']][bucket] = (timestamp, row['elo'])

    current_elo = dict(current)
    now_iso = utc_iso_from_datetime(end)
    result = []
    for model_id in selected:
        points = [{"x": ts, "y": round(elo, 1)} for _bucket, (ts, elo) in sorted(series[model_id].items())]
        if points:
            # A vonal a mai napig tart
            points.append({"x": now_iso, "y": round(current_elo[model_id], 1)})
        result.append({**model_public(model_id), "elo": round(current_elo[model_id], 1), "points": points})
    return jsonify({"series": result, "models_total": len(current)})


@app.route('/api/prompt_ids')
def get_prompt_ids_api():
    """Visszaadja az összes prompt ID-t (sorrendben)."""
    return jsonify({"prompt_ids": AVAILABLE_PROMPTS})

@app.route('/api/prompt_text')
def get_prompt_text_api():
    """Visszaadja a prompt szövegét egy adott prompt_id-hoz."""
    prompt_id = request.args.get('prompt_id')
    if not prompt_id or prompt_id not in AVAILABLE_PROMPTS:
        return api_error("Ismeretlen vagy hiányzó prompt_id.", 400)
    prompt_text = read_prompt_text(prompt_id)
    if prompt_text is None:
        return api_error("A prompt nem olvasható.", 500)
    return jsonify({"prompt_text": prompt_text})


@app.route('/api/model_info')
def get_model_info():
    """Visszaadja egy vagy két modell konfigurációs adatait összehasonlításhoz."""
    model1_id = request.args.get('model1')
    model2_id = request.args.get('model2')

    if not model1_id:
        return api_error("A model1 paraméter kötelező.", 400)
    if model1_id not in MODELS or (model2_id and model2_id not in MODELS):
        return api_error("Ismeretlen modell.", 400)

    def build_model_info(model_id):
        m = MODELS[model_id]
        return {
            **model_public(model_id),
            "open_source": m['open_source'],
            "release_date": m.get('release_date'),
            "type": m.get('type', 'image-generation'),
            "tags": m.get('tags', []),
            "max_resolution": m.get('max_resolution'),
            "pricing": m.get('pricing'),
            "api_available": m.get('api_available', False),
            "speed": m.get('speed'),
            "website": m.get('website'),
            **get_model_video(m),
        }

    result = {"model1": build_model_info(model1_id)}
    if model2_id:
        result["model2"] = build_model_info(model2_id)
    return jsonify(result)


@app.route('/api/compare_stats')
def get_compare_stats():
    """Két modell összehasonlító statisztikái: globális, egymás elleni és prompt-szintű eredmények."""
    model1_id = request.args.get('model1')
    model2_id = request.args.get('model2')

    if not model1_id or not model2_id:
        return api_error("Mindkét modellt ki kell választani.", 400)
    if model1_id not in MODELS or model2_id not in MODELS:
        return api_error("Ismeretlen modell.", 400)

    try:
        db = get_db()
        elos = {row['model']: row['elo'] for row in db.execute(
            'SELECT model, elo FROM model_elo WHERE model IN (?, ?)', (model1_id, model2_id))}
        stats = get_model_stats(db)

        # Egymás elleni eredmények
        h2h = db.execute('''
            SELECT SUM(outcome = 'win' AND winner = ?) AS m1, SUM(outcome = 'win' AND winner = ?) AS m2,
                   SUM(outcome != 'win') AS ties
            FROM votes WHERE (winner = ? AND loser = ?) OR (winner = ? AND loser = ?)
        ''', (model1_id, model2_id, model1_id, model2_id, model2_id, model1_id)).fetchone()
        h2h_1, h2h_2, h2h_ties = h2h['m1'] or 0, h2h['m2'] or 0, h2h['ties'] or 0

        # Prompt-szintű statisztikák egyetlen lekérdezéssel modellenként
        def per_prompt(model_id):
            rows = db.execute('''
                SELECT prompt_id,
                       SUM(outcome = 'win' AND winner = ?) AS wins,
                       SUM(outcome != 'win') AS ties,
                       COUNT(*) AS matches
                FROM votes WHERE winner = ? OR loser = ? GROUP BY prompt_id
            ''', (model_id, model_id, model_id)).fetchall()
            return {r['prompt_id']: {'wins': r['wins'] or 0, 'ties': r['ties'] or 0, 'losses': 0,
                                     'matches': r['matches']} for r in rows}

        m1_prompts, m2_prompts = per_prompt(model1_id), per_prompt(model2_id)
        empty = {'wins': 0, 'ties': 0, 'losses': 0, 'matches': 0}

        def prompt_entry(s):
            return {"wins": s['wins'], "ties": s['ties'], "matches": s['matches'], "win_rate": round(win_rate(s), 1)}

        prompt_stats = []
        for prompt_id in AVAILABLE_PROMPTS:
            prompt_text = read_prompt_text(prompt_id) or prompt_id
            prompt_stats.append({
                "prompt_id": prompt_id,
                "prompt_text": prompt_text[:100] + ('...' if len(prompt_text) > 100 else ''),
                "model1": prompt_entry(m1_prompts.get(prompt_id, empty)),
                "model2": prompt_entry(m2_prompts.get(prompt_id, empty)),
            })

        ranking_data = get_global_ranking(db)

        def global_entry(model_id):
            s = stats.get(model_id, empty)
            index = MODEL_INDEX[model_id]
            has_data = s['matches'] > 0
            return {**model_public(model_id), "elo": round(elos.get(model_id, DEFAULT_ELO), 1),
                    "score": round(float(ranking_data['rating'][index]), 1),
                    "ci_lower": round(float(ranking_data['ci_lower'][index]), 1) if has_data else None,
                    "ci_upper": round(float(ranking_data['ci_upper'][index]), 1) if has_data else None,
                    "preliminary": s['matches'] < PRELIMINARY_MATCH_THRESHOLD,
                    "wins": s['wins'], "ties": s['ties'], "matches": s['matches'], "win_rate": win_rate(s)}

        return jsonify({
            "model1": global_entry(model1_id),
            "model2": global_entry(model2_id),
            "head_to_head": {"model1_wins": h2h_1, "model2_wins": h2h_2, "ties": h2h_ties,
                             "total": h2h_1 + h2h_2 + h2h_ties},
            "prompt_stats": prompt_stats,
        })
    except sqlite3.Error:
        logger.exception("Database error while fetching compare stats")
        return api_error("Adatbázis hiba az összehasonlítás lekérésekor.", 500)


if __name__ == '__main__':
    # Parancssori argumentumok kezelése
    if len(sys.argv) > 1 and sys.argv[1] == 'reset-votes':
        with app.app_context():
            ok = reset_votes()
        print("A szavazatok sikeresen törölve!" if ok else "Hiba történt a szavazatok törlése közben!")
        sys.exit(0 if ok else 1)

    # Indítás előtt frissítjük a prompt listát
    update_available_prompts()
    # Debug mód fejlesztéshez, élesben Gunicorn fut (gunicorn.conf.py)
    app.run(debug=True, host='0.0.0.0')
