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
from config import (DATA_DIR, ALLOWED_EXTENSIONS, DEFAULT_ELO, K_FACTOR, MODELS, DEFAULT_VIDEO_URL, REVEAL_DELAY_MS,
                    FROZEN_BOTTOM_COUNT, NEW_MODEL_BOOST_THRESHOLD, NEW_MODEL_BOOST_WEIGHT, TARGETED_PAIRING_STRENGTH,
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


def _origin(url):
    match = re.match(r'^(https?://[^/]+)', url or '')
    return match.group(1) if match else ''


# Content-Security-Policy: csak saját és a jsDelivr CDN szkriptjei futhatnak; a képek a
# saját szerverről vagy a DATA_MODE (Cloudflare R2) címről jöhetnek.
CONTENT_SECURITY_POLICY = '; '.join([
    "default-src 'self'",
    "script-src 'self' https://cdn.jsdelivr.net",
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'",
    f"img-src 'self' data: blob: {_origin(DATA_MODE)}".strip(),
    "font-src 'self' data:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


@app.after_request
def set_security_headers(response):
    response.headers.setdefault('Content-Security-Policy', CONTENT_SECURITY_POLICY)
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
    """Befagyasztja a leaderboard alsó FROZEN_BOTTOM_COUNT modelljét (Bradley-Terry pontszám szerint).

    A befagyasztott modellek nem vesznek részt az Arena Battle-ben,
    de továbbra is láthatók a Side-by-Side módban és a Leaderboard-on.
    Csak olyan modell fagyasztható be, amelynek már van meccse.
    """
    try:
        db = db or get_db()
        bottom = []
        if FROZEN_BOTTOM_COUNT and FROZEN_BOTTOM_COUNT > 0:
            point = get_point_ranking(db)
            games = (point['wins'] + point['wins'].T).sum(axis=1)
            played = [m for m in MODEL_IDS if games[MODEL_INDEX[m]] > 0]
            played.sort(key=lambda m: point['rating'][MODEL_INDEX[m]])
            bottom = played[:FROZEN_BOTTOM_COUNT]
        with db:
            db.execute("UPDATE model_elo SET frozen = 0")
            db.executemany("UPDATE model_elo SET frozen = 1 WHERE model = ?", [(m,) for m in bottom])
        if bottom:
            logger.info("Frozen %d models at the bottom of the leaderboard.", len(bottom))
    except sqlite3.Error:
        logger.exception("Error updating frozen models")

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
    """A modell képének URL-je. DATA_MODE-ban, ha a manifest tartalmaz tartalom-alapú kulcsot
    (img/<blob sha>), azt használjuk: így az URL nem árulja el a modell nevét szavazás előtt."""
    filename = get_prompt_model_files(prompt_id).get(model_id)
    if not filename:
        return None
    if DATA_MODE:
        entry = load_manifest().get(prompt_id, {}).get(MODELS[model_id]['filename'])
        key = entry.get('key') if isinstance(entry, dict) else None
        if key:
            return f"{DATA_MODE}/{key}"
    return get_image_url(prompt_id, filename)


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
                           dev_mode=app.debug, login_error=request.args.get('login_error') == '1',
                           help_cfg=HELP_CONFIG, help_win_table=HELP_WIN_TABLE)


# A Súgó oldal a tényleges beállításokat mutatja, így a szöveg nem avul el, ha a config változik
HELP_CONFIG = {
    'reveal_delay_ms': REVEAL_DELAY_MS,
    'min_vote_delay_ms': MIN_VOTE_DELAY_MS,
    'daily_vote_limit': DAILY_VOTE_LIMIT,
    'max_open_battles': MAX_OPEN_BATTLES,
    'battle_ttl_seconds': BATTLE_TTL_SECONDS,
    'new_model_threshold': NEW_MODEL_BOOST_THRESHOLD,
    'new_model_weight': NEW_MODEL_BOOST_WEIGHT,
    'frozen_count': FROZEN_BOTTOM_COUNT,
    'bootstrap_rounds': BT_BOOTSTRAP_ROUNDS,
    'preliminary_threshold': PRELIMINARY_MATCH_THRESHOLD,
    'personal_min_votes': PERSONAL_LEADERBOARD_MIN_VOTES,
    'default_elo': DEFAULT_ELO,
    'k_factor': K_FACTOR,
    'cache_seconds': 30,
}
# Pontkülönbség → a magasabb pontszámú modell nyerési esélye (%)
HELP_WIN_TABLE = [(diff, str(round(100 / (1 + 10 ** (-diff / 400)))))
                  for diff in (0, 25, 50, 100, 150, 200, 300, 400)]


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


MAX_PAIR_INFORMATION = 4.0


def pair_information(rating_a, rating_b, sigma_a, sigma_b, median_sigma):
    """Mennyit tanulna a rangsor ebből a párból (0 … MAX_PAIR_INFORMATION).

    - közelség: 4·p·(1−p), ahol p az egyik modell várt nyerési esélye – 1, ha a kimenet teljesen
      bizonytalan (azonos pontszám), és közel 0, ha az eredmény szinte biztos;
    - bizonytalanság: a két modell CI-félszélességének átlaga a tipikus (medián) félszélességhez képest.
    """
    p = 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400))
    closeness = 4.0 * p * (1.0 - p)
    uncertainty = (sigma_a + sigma_b) / (2.0 * max(median_sigma, 1.0))
    return min(closeness * uncertainty, MAX_PAIR_INFORMATION)


def pair_weight(pair_games, information, boosted):
    """Egy modellpár kiválasztási súlya.

    A ritkán látott párok (1 / (1 + eddigi meccsek)) és a sokat mondó párok
    (1 + TARGETED_PAIRING_STRENGTH · információ) gyakrabban kerülnek elő; az új modellek párjai
    NEW_MODEL_BOOST_WEIGHT-szeres esélyt kapnak. Minden pár súlya pozitív, így bármelyik előfordulhat.
    """
    weight = (1.0 + TARGETED_PAIRING_STRENGTH * information) / (1 + pair_games)
    return weight * NEW_MODEL_BOOST_WEIGHT if boosted else weight


def choose_battle(db):
    """Kiválaszt egy modellpárt (célzott párosítással) és egy közös promptot."""
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
    ranking_data = get_global_ranking(db)
    rating = ranking_data['rating']
    half_width = (ranking_data['ci_upper'] - ranking_data['ci_lower']) / 2.0
    played = [MODEL_INDEX[m] for m in MODEL_IDS if match_counts.get(m, 0) > 0]
    known = half_width[played] if played else np.array([])
    median_sigma = float(np.median(known)) if known.size else 1.0
    # Adat nélküli modell bizonytalansága: a legbizonytalanabb ismert modellé (vagy 300 pont)
    unknown_sigma = float(known.max()) if known.size else 300.0

    def sigma(model_id):
        return float(half_width[MODEL_INDEX[model_id]]) if match_counts.get(model_id, 0) > 0 else unknown_sigma

    weights = []
    for (a, b), _prompts in eligible:
        information = pair_information(rating[MODEL_INDEX[a]], rating[MODEL_INDEX[b]], sigma(a), sigma(b), median_sigma)
        boosted = min(match_counts.get(a, 0), match_counts.get(b, 0)) < NEW_MODEL_BOOST_THRESHOLD
        weights.append(pair_weight(pair_counts.get((a, b), 0), information, boosted))

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

    try:
        score_changes = score_change_for_vote(db, model_a, model_b, score_a)
    except Exception:
        logger.exception("Could not compute score change for vote")
        score_changes = {}

    def reveal(model_id):
        old, new = elo_changes[model_id]
        data = {**model_public(model_id), "elo_before": round(old, 1), "elo_after": round(new, 1),
                "elo_delta": round(new - old, 1)}
        if model_id in score_changes:
            before, after = score_changes[model_id]
            data.update(score_before=round(before, 1), score_after=round(after, 1), score_delta=round(after - before, 1))
        return data

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
_point_cache = {'key': None, 'data': None}
_bootstrap_cache = {'key': None, 'computed_at': 0.0, 'data': None}
_ranking_lock = threading.Lock()


def reset_ranking_cache():
    """A rangsor-gyorsítótárak ürítése (pl. tesztekben vagy adatbázis-csere után)."""
    with _ranking_lock:
        _point_cache.update(key=None, data=None)
        _bootstrap_cache.update(key=None, computed_at=0.0, data=None)


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


def _votes_key(db):
    return tuple(db.execute('SELECT COUNT(*), COALESCE(MAX(id), 0) FROM votes').fetchone())


def get_point_ranking(db):
    """A Bradley-Terry pontszámok (CI nélkül) – mindig a legfrissebb szavazatokból.
    Gyors (~15 ms), ezért minden új szavazat után újraszámoljuk."""
    key = _votes_key(db)
    with _ranking_lock:
        if _point_cache['key'] == key and _point_cache['data'] is not None:
            return _point_cache['data']
    pairs = load_vote_pairs(db)
    wins = ranking.build_win_matrix(pairs, len(MODEL_IDS))
    rating = ranking.to_rating(ranking.fit_bradley_terry(wins, BT_PRIOR_GAMES))
    data = {'key': key, 'pairs': pairs, 'wins': wins, 'rating': rating}
    with _ranking_lock:
        _point_cache.update(key=key, data=data)
    return data


def get_global_ranking(db):
    """A globális BT rangsor: friss pontszám + bootstrap konfidenciaintervallum.

    A pontszám mindig friss. A bootstrap CI (~0,3 s) új szavazat után legfeljebb
    RANKING_CACHE_SECONDS-ig a korábbi számításból jön; ha közben a pontszám kicsit elmozdult,
    az intervallumot kiterjesztjük, hogy mindig tartalmazza a pontszámot.
    """
    point = get_point_ranking(db)
    now = time.monotonic()
    with _ranking_lock:
        cached = _bootstrap_cache['data']
        fresh = cached is not None and (_bootstrap_cache['key'] == point['key']
                                        or now - _bootstrap_cache['computed_at'] < RANKING_CACHE_SECONDS)
    if not fresh:
        result = ranking.compute_ratings(point['pairs'], len(MODEL_IDS), BT_PRIOR_GAMES, BT_BOOTSTRAP_ROUNDS)
        cached = {'ci_lower': result['ci_lower'], 'ci_upper': result['ci_upper'], 'computed_at': utc_now_iso()}
        with _ranking_lock:
            _bootstrap_cache.update(key=point['key'], computed_at=now, data=cached)
    rating = point['rating']
    return {
        'rating': rating,
        'wins': point['wins'],
        'ci_lower': np.minimum(cached['ci_lower'], rating),
        'ci_upper': np.maximum(cached['ci_upper'], rating),
        'computed_at': cached['computed_at'],
        'vote_count': point['key'][0],
    }


def score_change_for_vote(db, model_a, model_b, score_a):
    """A két modell Leaderboard-pontszáma a szavazat előtt és után (a szavazat már az adatbázisban van)."""
    point = get_point_ranking(db)
    i, j = MODEL_INDEX[model_a], MODEL_INDEX[model_b]
    wins_before = point['wins'].copy()
    wins_before[i, j] -= score_a
    wins_before[j, i] -= 1.0 - score_a
    before = ranking.to_rating(ranking.fit_bradley_terry(wins_before, BT_PRIOR_GAMES))
    after = point['rating']
    return {model_id: (float(before[index]), float(after[index])) for model_id, index in ((model_a, i), (model_b, j))}


def apply_ranking(rows, rating, ci_lower=None, ci_upper=None):
    """Pontszám, CI és helyezés a (már szűrt) sorokhoz; rendezés pontszám szerint.

    - position: a modell sorszáma a pontszám szerinti listában (ez jelenik meg a „#” oszlopban);
    - rank / rank_worst: a statisztikailag lehetséges helyezéssáv (a CI-k átfedése alapján).
    Mindkettő a megjelenített (szűrt) modellek között értendő."""
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
        has_rank = row['matches'] > 0
        # A megjelenített helyezés: sorszám a pontszám szerinti listában (adat nélküli modellnél nincs)
        row['position'] = position if has_rank else None
        if 'rank' not in row:
            row['rank'] = row['rank_worst'] = position if has_rank else None
    return rows


def build_ranked_leaderboard(db, model_type='all'):
    """A rangsor sorai (pontszám, CI, helyezés, statisztikák) a megadott modelltípusra."""
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
    return apply_ranking(rows, ranking_data['rating'], ranking_data['ci_lower'], ranking_data['ci_upper'])


@app.route('/api/leaderboard')
def get_leaderboard():
    """Leaderboard: Bradley-Terry pontszám 95%-os CI-vel, helyezéssávval, szavazatszámmal.
    Az online ELO a felületen már nem jelenik meg; az `elo` mező csak visszafelé kompatibilitás miatt maradt."""
    try:
        return jsonify(build_ranked_leaderboard(get_db(), request.args.get('model_type', 'all')))
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


HISTORY_RANGES = {'1w': 7, '2w': 14, '1m': 30, '3m': 90}
HISTORY_MAX_POINTS = 160
_history_cache = {'key': None, 'data': {}}


def compute_score_history(db, range_key):
    """A Bradley-Terry pontszámok alakulása: az adott időpontig beérkezett összes szavazatból számolva.

    Visszamenőleg is működik, mert minden szavazatnak megvan az időpontja. Az időszakot
    HISTORY_MAX_POINTS egyenlő részre osztjuk, és minden határpontnál újraillesztjük a modellt
    (egy illesztés ~1 ms). Az eredményt a szavazatok állapotáig gyorsítótárazzuk.
    """
    point = get_point_ranking(db)
    with _ranking_lock:
        if _history_cache['key'] != point['key']:
            _history_cache.update(key=point['key'], data={})
        cached = _history_cache['data'].get(range_key)
    if cached is not None:
        return cached

    votes = []
    for row in db.execute('SELECT winner, loser, outcome, voted_at FROM votes ORDER BY voted_at, id'):
        i, j = MODEL_INDEX.get(row['winner']), MODEL_INDEX.get(row['loser'])
        if i is None or j is None or not row['voted_at']:
            continue
        votes.append((i, j, 1.0 if row['outcome'] == OUTCOME_WIN else 0.5, to_iso_utc(row['voted_at'])))

    result = {'times': [], 'ratings': np.zeros((0, len(MODEL_IDS))), 'games': np.zeros((0, len(MODEL_IDS)))}
    if votes:
        end = utc_now_naive()
        first = _parse_iso(votes[0][3])
        start = end - datetime.timedelta(days=HISTORY_RANGES[range_key]) if range_key in HISTORY_RANGES else first
        start = max(start, first)
        span = max((end - start).total_seconds(), 3600.0)
        boundaries = [start + datetime.timedelta(seconds=span * k / HISTORY_MAX_POINTS)
                      for k in range(HISTORY_MAX_POINTS + 1)]

        wins = np.zeros((len(MODEL_IDS), len(MODEL_IDS)))
        times, ratings, games = [], [], []
        index = 0
        last_rating = None
        for boundary in boundaries:
            boundary_iso = utc_iso_from_datetime(boundary)
            changed = False
            while index < len(votes) and votes[index][3] <= boundary_iso:
                i, j, score, _ts = votes[index]
                wins[i, j] += score
                wins[j, i] += 1.0 - score
                index += 1
                changed = True
            if changed or last_rating is None:
                last_rating = ranking.to_rating(ranking.fit_bradley_terry(wins, BT_PRIOR_GAMES))
            times.append(boundary_iso)
            ratings.append(last_rating)
            games.append((wins + wins.T).sum(axis=1))
        # Az utolsó pont pontosan a mostani (Leaderboard) pontszám legyen
        ratings[-1] = point['rating']
        games[-1] = (point['wins'] + point['wins'].T).sum(axis=1)
        result = {'times': times, 'ratings': np.array(ratings), 'games': np.array(games)}

    with _ranking_lock:
        if _history_cache['key'] == point['key']:
            _history_cache['data'][range_key] = result
    return result


@app.route('/api/history')
def get_score_history():
    """A top N modell Leaderboard-pontszámának (Bradley-Terry) időbeli alakulása.

    Paraméterek: range (1w, 2w, 1m, 3m, all), top (1-30).
    Egy modell vonala attól az időponttól indul, amikor az első meccsét játszotta.
    """
    try:
        top = max(1, min(int(request.args.get('top', 10)), 30))
    except ValueError:
        top = 10
    range_key = request.args.get('range', 'all')
    if range_key not in HISTORY_RANGES:
        range_key = 'all'
    db = get_db()
    point = get_point_ranking(db)
    current_games = (point['wins'] + point['wins'].T).sum(axis=1)
    played = [m for m in MODEL_IDS if current_games[MODEL_INDEX[m]] > 0]
    played.sort(key=lambda m: -point['rating'][MODEL_INDEX[m]])
    selected = played[:top]

    history = compute_score_history(db, range_key)
    series = []
    for model_id in selected:
        index = MODEL_INDEX[model_id]
        points = [
            {"x": ts, "y": round(float(history['ratings'][k, index]), 1)}
            for k, ts in enumerate(history['times']) if history['games'][k, index] > 0
        ]
        series.append({**model_public(model_id), "score": round(float(point['rating'][index]), 1), "points": points})
    return jsonify({"series": series, "models_total": len(played)})


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

        # Pontszám, CI és helyezés ugyanúgy, ahogy a (teljes) Leaderboard mutatja
        ranked = {row['id']: row for row in build_ranked_leaderboard(db, 'all')}
        ranked_count = sum(1 for row in ranked.values() if row['position'] is not None)

        def global_entry(model_id):
            s = stats.get(model_id, empty)
            row = ranked[model_id]
            return {**model_public(model_id), "elo": round(elos.get(model_id, DEFAULT_ELO), 1),
                    "score": row['score'], "ci_lower": row['ci_lower'], "ci_upper": row['ci_upper'],
                    "position": row['position'], "rank": row['rank'], "rank_worst": row['rank_worst'],
                    "ranked_models": ranked_count, "preliminary": row['preliminary'],
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


# Befagyasztott modellek frissítése indításkor (a rangsor függvényeinek definíciója után)
with app.app_context():
    update_frozen_models()


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
