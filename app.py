import os
import random
import secrets
import sqlite3
import sys
import glob
import datetime
from flask import Flask, render_template, jsonify, request, send_from_directory, abort, redirect, url_for, session
from werkzeug.middleware.proxy_fix import ProxyFix
from database import get_db, init_db, get_prompt_ids, update_elo
from config import (DATA_DIR, ALLOWED_EXTENSIONS, DEFAULT_ELO, MODELS, REVEAL_DELAY_MS, FROZEN_BOTTOM_COUNT,
                    NEW_MODEL_BOOST_THRESHOLD, NEW_MODEL_BOOST_WEIGHT, DEBUG_MODE,
                    SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET)
from auth import oauth, init_oauth, login_required, get_current_user, save_user

app = Flask(__name__)
app.config['DATA_DIR'] = DATA_DIR # Flask konfigurációban is tároljuk

# Check if DATA_MODE is set for remote image loading
DATA_MODE = os.environ.get('DATA_MODE')

# Authentication and session configuration
if SECRET_KEY:
    app.secret_key = SECRET_KEY
elif DEBUG_MODE:
    app.secret_key = secrets.token_hex(32)
    app.logger.warning('SECRET_KEY is not set; using a temporary development key and resetting sessions on restart.')
else:
    raise RuntimeError('SECRET_KEY environment variable must be set when running outside development mode.')

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = not DEBUG_MODE
app.config['GOOGLE_CLIENT_ID'] = GOOGLE_CLIENT_ID
app.config['GOOGLE_CLIENT_SECRET'] = GOOGLE_CLIENT_SECRET
app.config['GITHUB_CLIENT_ID'] = GITHUB_CLIENT_ID
app.config['GITHUB_CLIENT_SECRET'] = GITHUB_CLIENT_SECRET

# Trust proxy headers for HTTPS behind reverse proxy (Render.com)
if DATA_MODE:
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize OAuth providers
init_oauth(app)

@app.route('/static/js/<path:filename>')
def serve_js(filename):
    """Serve JavaScript files with proper MIME type for ES modules."""
    return send_from_directory('static/js', filename, mimetype='application/javascript')

# Statikus fájlok kiszolgálása a node_modules mappából
# @app.route('/node_modules/<path:filename>')
# def serve_node_modules(filename):
#     node_modules_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'node_modules')
#     return send_from_directory(node_modules_dir, filename)

# Adatbázis inicializálása indításkor (ha szükséges)
with app.app_context():
    init_db()

AVAILABLE_PROMPTS = [] # Gyorsítótárazzuk a prompt ID-kat

def update_available_prompts():
    """Frissíti az elérhető prompt ID-k listáját."""
    global AVAILABLE_PROMPTS
    AVAILABLE_PROMPTS = get_prompt_ids()
    if not AVAILABLE_PROMPTS:
        print("Warning: No valid prompts found in data directory!")

def update_frozen_models():
    """Befagyasztja a leaderboard alsó FROZEN_BOTTOM_COUNT modelljét.
    
    A befagyasztott modellek nem vesznek részt az Arena Battle-ben,
    de továbbra is láthatók a Side-by-Side módban és a Leaderboard-on.
    """
    try:
        db = get_db()
        
        if not FROZEN_BOTTOM_COUNT or FROZEN_BOTTOM_COUNT <= 0:
            print("Frozen models feature is disabled (FROZEN_BOTTOM_COUNT = 0). Unfreezing all models.")
            with db:
                db.execute("UPDATE model_elo SET frozen = 0")
                db.commit()
            return

        # Modellek lekérdezése ELO szerint növekvő sorrendben (legrosszabbak elöl)
        rows = db.execute("SELECT model, elo FROM model_elo ORDER BY elo ASC").fetchall()
        models_ordered = [r['model'] for r in rows]
        
        # Az alsó N modell befagyasztása
        bottom_n = models_ordered[:FROZEN_BOTTOM_COUNT]
        
        with db:
            # Először minden modellt feloldunk
            db.execute("UPDATE model_elo SET frozen = 0")
            # Majd befagyasztjuk az alsó N-et
            for m in bottom_n:
                db.execute("UPDATE model_elo SET frozen = 1 WHERE model = ?", (m,))
            db.commit()
        
        print(f"Frozen {len(bottom_n)} models at the bottom of the leaderboard: {bottom_n}")
    except sqlite3.Error as e:
        print(f"Error updating frozen models: {e}")

# Befagyasztott modellek frissítése indításkor (a függvény definíciója után)
with app.app_context():
    update_frozen_models()

# Manifest cache DATA_MODE-hoz
_manifest_cache = None


def set_pending_battle(prompt_id, model1_id, model2_id):
    """Store the currently displayed battle in the session to prevent forged votes."""
    session['pending_battle'] = {
        'prompt_id': prompt_id,
        'models': sorted([model1_id, model2_id]),
    }
    session.modified = True


def consume_pending_battle(prompt_id, winner, loser):
    """Validate and consume the currently displayed battle."""
    pending_battle = session.pop('pending_battle', None)
    if not pending_battle:
        return False

    expected_models = pending_battle.get('models', [])
    return (
        pending_battle.get('prompt_id') == prompt_id and
        sorted([winner, loser]) == expected_models
    )

def load_manifest():
    """Betölti a manifest.json fájlt DATA_MODE-ban a képfájl kiterjesztes meghatározásához."""
    global _manifest_cache
    if _manifest_cache is None:
        manifest_path = os.path.join(app.config['DATA_DIR'], 'manifest.json')
        if os.path.exists(manifest_path):
            import json
            with open(manifest_path, 'r', encoding='utf-8') as f:
                _manifest_cache = json.load(f)
            print(f"Manifest loaded: {len(_manifest_cache)} prompts.")
        else:
            print("Warning: manifest.json not found! Run generate_manifest.py locally and commit it.")
            _manifest_cache = {}
    return _manifest_cache


# Új segédfüggvény a fájlok megtalálásához, ami nem veszi figyelembe a kiterjesztést
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
        return manifest.get(prompt_id, {}).get(model_base_name)

    directory = os.path.join(app.config['DATA_DIR'], prompt_id)
    
    # Megnézzük az összes lehetséges kiterjesztéssel, hogy létezik-e a fájl
    for ext in ALLOWED_EXTENSIONS:
        potential_file = f"{model_base_name}{ext}"
        if os.path.exists(os.path.join(directory, potential_file)):
            return potential_file
    
    # Ha nem találtuk meg a pontos egyezést, próbáljuk meg fájlmintával
    pattern = os.path.join(directory, f"{model_base_name}.*")
    matching_files = glob.glob(pattern)
    
    # Szűrjük az eredményt csak az engedélyezett kiterjesztésekre
    for file in matching_files:
        file_ext = os.path.splitext(file)[1].lower()
        if file_ext in ALLOWED_EXTENSIONS:
            return os.path.basename(file)
    
    return None


def get_image_url(prompt_id, filename):
    """
    Get the full URL for an image file.
    Returns remote URL if DATA_MODE is set, otherwise local path.
    """
    if DATA_MODE:
        return f"{DATA_MODE}/{prompt_id}/{filename}"
    else:
        return f"/images/{prompt_id}/{filename}"


@app.before_request
def before_first_request_func():
    # Első kérés előtt (vagy fejlesztéskor minden kérés előtt, ha `debug=True`)
    # frissítjük a prompt listát, hogy az új mappák megjelenjenek újraindítás nélkül.
    # Éles környezetben ezt ritkábban is lehet futtatni.
    if app.debug: # Csak debug módban frissítsen minden kérésnél
       update_available_prompts()
    elif not AVAILABLE_PROMPTS: # Vagy ha még üres a lista
       update_available_prompts()

# Szavazatok resetelésére szolgáló függvény
def reset_votes():
    """Törli az összes szavazatot és visszaállítja az ELO pontszámokat az alapértelmezettre."""
    try:
        db = get_db()
        with db:
            # Szavazatok törlése
            db.execute('DELETE FROM votes')
            
            # ELO történeti adatok törlése
            db.execute('DELETE FROM elo_history')
            
            # ELO pontszámok visszaállítása az alapértelmezettre és frozen flag törlése
            db.execute('UPDATE model_elo SET elo = ?, frozen = 0', (DEFAULT_ELO,))
            
            # Kezdeti ELO értékek rögzítése a historikus táblában is
            current_timestamp = datetime.datetime.now()
            for model in MODELS.keys():
                db.execute('INSERT INTO elo_history (model, elo, timestamp) VALUES (?, ?, ?)', 
                          (model, DEFAULT_ELO, current_timestamp))
            
            db.commit()
        print("Sikeres adatbázis resetelés! Az összes szavazat és ELO előzmény törölve, ELO pontszámok visszaállítva.")
        return True
    except sqlite3.Error as e:
        print(f"Adatbázis hiba a resetelés közben: {e}")
        return False
    except Exception as e:
        print(f"Hiba a resetelés közben: {e}")
        return False


@app.route('/')
def index():
    """Főoldal megjelenítése."""
    # A modellek listáját névvel és szolgáltatóval adjuk át a template-nek
    # display mező tartalmazza a megjelenítendő szöveget: "provider: name".
    # Rendezés display alapján, így a dropdownok is ABC-s listát mutatnak.
    models_for_template = sorted(
        (
            {
                'id': model_id,
                'name': model['name'],
                'provider': model.get('provider') or '',
                'display': f"{model.get('provider')}: {model['name']}" if model.get('provider') else model['name'],
            }
            for model_id, model in MODELS.items()
        ),
        key=lambda m: m['display'].lower()
    )
    
    # Auth state for template
    user = get_current_user()
    user_info = None
    if user:
        user_info = {'name': user['name'], 'provider': user['provider']}
    
    auth_providers = []
    if app.config.get('GOOGLE_CLIENT_ID'):
        auth_providers.append('google')
    if app.config.get('GITHUB_CLIENT_ID'):
        auth_providers.append('github')
    
    return render_template('index.html', models=models_for_template, reveal_delay_ms=REVEAL_DELAY_MS,
                         user=user_info, auth_providers=auth_providers,
                         dev_mode=app.debug)


# --- Auth Endpoints ---

@app.route('/auth/dev-login')
def auth_dev_login():
    """Fejlesztői bejelentkezés - CSAK debug módban érhető el."""
    if not DEBUG_MODE:
        abort(404)
    db = get_db()
    with db:
        user_id = save_user(db, 'dev', 'dev-user', 'dev@localhost', 'Dev User')
        db.commit()
    session['user'] = {'id': user_id, 'name': 'Dev User', 'provider': 'dev'}
    return redirect(url_for('index'))


@app.route('/auth/login/<provider>')
def auth_login(provider):
    """Bejelentkezés indítása a megadott OAuth providerrel."""
    if provider not in ('google', 'github'):
        abort(404)
    client = oauth.create_client(provider)
    if client is None:
        abort(404)
    redirect_uri = url_for('auth_callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


@app.route('/auth/callback/<provider>')
def auth_callback(provider):
    """OAuth callback a bejelentkezés befejezéséhez."""
    if provider not in ('google', 'github'):
        abort(404)
    client = oauth.create_client(provider)
    if client is None:
        abort(404)
    
    token = client.authorize_access_token()
    
    if provider == 'google':
        userinfo = token.get('userinfo')
        if not userinfo:
            userinfo = client.userinfo()
        user_data = {
            'provider': 'google',
            'provider_id': userinfo['sub'],
            'email': userinfo.get('email', ''),
            'name': userinfo.get('name', userinfo.get('email', 'Google User'))
        }
    elif provider == 'github':
        resp = client.get('user')
        github_user = resp.json()
        email = github_user.get('email', '')
        if not email:
            resp_emails = client.get('user/emails')
            emails = resp_emails.json()
            primary_email = next((e for e in emails if e.get('primary')), None)
            if primary_email:
                email = primary_email['email']
        user_data = {
            'provider': 'github',
            'provider_id': str(github_user['id']),
            'email': email,
            'name': github_user.get('name') or github_user.get('login', 'GitHub User')
        }
    
    # Save user to database
    db = get_db()
    with db:
        user_id = save_user(db, user_data['provider'], user_data['provider_id'],
                           user_data['email'], user_data['name'])
        db.commit()
    
    # Store in session
    session['user'] = {
        'id': user_id,
        'name': user_data['name'],
        'provider': user_data['provider']
    }
    
    return redirect(url_for('index'))


@app.route('/auth/logout')
def auth_logout():
    """Kijelentkezés - session törlése."""
    session.clear()
    return redirect(url_for('index'))


@app.route('/api/auth/status')
def auth_status():
    """Visszaadja a bejelentkezési állapotot."""
    user = get_current_user()
    if user:
        return jsonify({
            'logged_in': True,
            'user': {
                'name': user['name'],
                'provider': user['provider']
            }
        })
    return jsonify({'logged_in': False})


# Módosítás: Engedélyezzük a .jpeg kiterjesztést is
@app.route('/images/<prompt_id>/<filename>')
def serve_image(prompt_id, filename):
    """Képfájlok kiszolgálása a data mappából."""
    # Biztonsági ellenőrzés: csak az engedélyezett kiterjesztéseket engedélyezzük
    if not any(filename.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        print(f"Access denied for filename: {filename}")
        abort(404)

    # Ellenőrizzük, hogy a prompt_id létezik-e
    if prompt_id not in AVAILABLE_PROMPTS:
        print(f"Access denied for prompt_id: {prompt_id}")
        abort(404)

    directory = os.path.join(app.config['DATA_DIR'], prompt_id)
    # `send_from_directory` biztonságosabb, mint kézzel összerakni az útvonalat
    try:
        return send_from_directory(directory, filename)
    except FileNotFoundError:
        print(f"Image not found: {directory}/{filename}")
        abort(404)


# --- API Endpoints ---


# Módosítás: Arena Battle mód - ne jelenítse meg a modellek nevét szavazás előtt
@app.route('/api/battle_data')
def get_battle_data():
    """Adatokat ad vissza az Arena Battle módhoz."""    
    if not AVAILABLE_PROMPTS:
        return jsonify({"error": "No prompts available"}), 500

    prompt_id = random.choice(AVAILABLE_PROMPTS)
    prompt_path = os.path.join(app.config['DATA_DIR'], prompt_id, 'prompt.txt')

    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_text = f.read().strip()
    except FileNotFoundError:
        return jsonify({"error": f"Prompt file not found for ID: {prompt_id}"}), 500
    except Exception as e:
         return jsonify({"error": f"Error reading prompt file: {e}"}), 500
    
    # Válassz két KÜLÖNBÖZŐ modellt véletlenszerűen (befagyasztott modellek kizárásával)
    db = get_db()
    non_frozen_rows = db.execute("SELECT model FROM model_elo WHERE COALESCE(frozen, 0) = 0").fetchall()
    non_frozen_models = [r['model'] for r in non_frozen_rows]
    
    # Ha nincs elég nem befagyasztott modell, használjuk az összeset
    if len(non_frozen_models) < 2:
        model_ids = list(MODELS.keys())
    else:
        # Csak azokat a modelleket használjuk, amik a MODELS-ben is szerepelnek
        model_ids = [m for m in non_frozen_models if m in MODELS]
    
    if len(model_ids) < 2:
        return jsonify({"error": "Not enough models defined for battle"}), 500

    # Új modellek boost: a 50 meccs alatti modellek nagyobb eséllyel jelennek meg
    # az egyik battle-slotban. A másik slot teljesen véletlenszerű marad.
    match_counts_rows = db.execute(
        'SELECT model, COUNT(*) as cnt FROM '
        '(SELECT winner as model FROM votes UNION ALL SELECT loser as model FROM votes) '
        'GROUP BY model'
    ).fetchall()
    match_counts = {r['model']: r['cnt'] for r in match_counts_rows}

    weights = [
        NEW_MODEL_BOOST_WEIGHT if match_counts.get(m, 0) < NEW_MODEL_BOOST_THRESHOLD else 1
        for m in model_ids
    ]
    # Súlyozott pick az egyik slothoz, uniform random a másikhoz
    featured_id = random.choices(model_ids, weights=weights, k=1)[0]
    remaining_ids = [m for m in model_ids if m != featured_id]
    other_id = random.choice(remaining_ids)
    # Véletlenszerűen osszuk el a két slot között, hogy ne legyen oldalbias
    if random.random() < 0.5:
        model1_id, model2_id = featured_id, other_id
    else:
        model1_id, model2_id = other_id, featured_id

    model1_file = find_model_file(prompt_id, MODELS[model1_id]['filename'])
    model2_file = find_model_file(prompt_id, MODELS[model2_id]['filename'])
    if not model1_file:
        return jsonify({"error": f"Image for model {model1_id} not found in prompt {prompt_id}"}), 500
    if not model2_file:
        return jsonify({"error": f"Image for model {model2_id} not found in prompt {prompt_id}"}), 500

    set_pending_battle(prompt_id, model1_id, model2_id)

    data = {
        "prompt_id": prompt_id,
        "prompt_text": prompt_text,
        "model1": {
            "id": model1_id,
            "name": MODELS[model1_id]['name'],
            "provider": MODELS[model1_id].get('provider', ''),
            "image_url": get_image_url(prompt_id, model1_file)
        },
        "model2": {
            "id": model2_id,
            "name": MODELS[model2_id]['name'],
            "provider": MODELS[model2_id].get('provider', ''),
            "image_url": get_image_url(prompt_id, model2_file)
        },
        "reveal_models": False
    }
    return jsonify(data)

@app.route('/api/side_by_side_data')
def get_side_by_side_data():
    """Adatokat ad vissza az Arena Side-by-Side módhoz."""
    model1_id = request.args.get('model1')
    model2_id = request.args.get('model2')
    model3_id = request.args.get('model3')  # Optional third model
    previous_prompt_id = request.args.get('previous_prompt_id', None)

    if not model1_id or not model2_id:
        return jsonify({"error": "Both model1 and model2 parameters are required"}), 400
    if model1_id not in MODELS or model2_id not in MODELS:
        return jsonify({"error": "Invalid model key provided"}), 400
    if model3_id and model3_id not in MODELS:
        return jsonify({"error": "Invalid model3 key provided"}), 400
    if not AVAILABLE_PROMPTS:
        return jsonify({"error": "No prompts available"}), 500

    if len(AVAILABLE_PROMPTS) == 1:
        prompt_id = AVAILABLE_PROMPTS[0]
    else:
        available_prompts = [p for p in AVAILABLE_PROMPTS if p != previous_prompt_id]
        if not available_prompts:
            available_prompts = AVAILABLE_PROMPTS
        prompt_id = random.choice(available_prompts)

    prompt_path = os.path.join(app.config['DATA_DIR'], prompt_id, 'prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_text = f.read().strip()
    except FileNotFoundError:
        return jsonify({"error": f"Prompt file not found for ID: {prompt_id}"}), 500
    except Exception as e:
        return jsonify({"error": f"Error reading prompt file: {e}"}), 500
    model1_file = find_model_file(prompt_id, MODELS[model1_id]['filename'])
    model2_file = find_model_file(prompt_id, MODELS[model2_id]['filename'])
    if not model1_file:
        return jsonify({"error": f"Image for model {model1_id} not found in prompt {prompt_id}"}), 500
    if not model2_file:
        return jsonify({"error": f"Image for model {model2_id} not found in prompt {prompt_id}"}), 500

    data = {
        "prompt_id": prompt_id,
        "prompt_text": prompt_text,
        "model1": {
            "id": model1_id,
            "name": MODELS[model1_id]['name'],
            "image_url": get_image_url(prompt_id, model1_file)
        },
        "model2": {
            "id": model2_id,
            "name": MODELS[model2_id]['name'],
            "image_url": get_image_url(prompt_id, model2_file)
        }
    }
    
    # Add third model if requested
    if model3_id:
        model3_file = find_model_file(prompt_id, MODELS[model3_id]['filename'])
        if not model3_file:
            return jsonify({"error": f"Image for model {model3_id} not found in prompt {prompt_id}"}), 500
        data["model3"] = {
            "id": model3_id,
            "name": MODELS[model3_id]['name'],
            "image_url": get_image_url(prompt_id, model3_file)
        }
    
    return jsonify(data)

# Új API végpont a kép URL lekéréséhez modellváltáskor
@app.route('/api/get_image')
def get_image_for_model():
    """Visszaadja egy adott modell képének URL-jét egy adott prompt ID-hoz."""
    model_id = request.args.get('model')
    prompt_id = request.args.get('prompt_id')

    if not model_id or not prompt_id:
        return jsonify({"error": "Both model and prompt_id parameters are required"}), 400
    if model_id not in MODELS:
        return jsonify({"error": f"Invalid model key provided: {model_id}"}), 400
    if prompt_id not in AVAILABLE_PROMPTS:
        update_available_prompts()
        if prompt_id not in AVAILABLE_PROMPTS:
            return jsonify({"error": f"Invalid or unavailable prompt_id: {prompt_id}"}), 400
    model_filename_base = MODELS[model_id].get('filename')
    if not model_filename_base:
        return jsonify({"error": f"Filename configuration missing for model: {model_id}"}), 500
    image_file = find_model_file(prompt_id, model_filename_base)
    if not image_file:
        print(f"Image file not found for model '{model_id}' (base: '{model_filename_base}') in prompt '{prompt_id}'")
        return jsonify({"error": f"Image for model {model_id} not found in prompt {prompt_id}"}), 404
    image_url = get_image_url(prompt_id, image_file)
    return jsonify({"image_url": image_url})


@app.route('/api/vote', methods=['POST'])
@login_required
def record_vote():
    """Szavazat rögzítése az adatbázisban."""
    data = request.get_json()
    prompt_id = data.get('prompt_id')
    winner = data.get('winner')
    loser = data.get('loser')

    if not all([prompt_id, winner, loser]):
        return jsonify({"error": "Missing data for vote"}), 400
    if prompt_id not in AVAILABLE_PROMPTS:
        return jsonify({"error": "Invalid prompt id in vote"}), 400
    if winner not in MODELS or loser not in MODELS:
        return jsonify({"error": "Invalid model id in vote"}), 400
    if winner == loser:
        return jsonify({"error": "Winner and loser must be different models"}), 400
    if not consume_pending_battle(prompt_id, winner, loser):
        return jsonify({"error": "Invalid or expired battle state"}), 400
    try:
        user = get_current_user()
        db = get_db()
        with db:
            db.execute(
                'INSERT INTO votes (prompt_id, winner, loser, user_id) VALUES (?, ?, ?, ?)',
                (prompt_id, winner, loser, user['id'])
            )
            winner_new_elo, loser_new_elo = update_elo(db, winner, loser)
            db.commit()
        return jsonify({
            "success": True,
            "message": f"Vote recorded for {winner} against {loser}",
            "winner_new_elo": round(winner_new_elo, 1),
            "loser_new_elo": round(loser_new_elo, 1)
        })
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Database error while recording vote"}), 500
    except Exception as e:
        print(f"Error recording vote: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/leaderboard')
def get_leaderboard():
    """Leaderboard adatok lekérdezése és kiszámítása."""    
    try:
        model_type = request.args.get('model_type', 'all')
        db = get_db()
        wins_cursor = db.execute('''SELECT winner, COUNT(*) as win_count FROM votes GROUP BY winner''')
        wins = {row['winner']: row['win_count'] for row in wins_cursor.fetchall()}
        total_matches_cursor = db.execute('''SELECT model, COUNT(*) as match_count FROM (
                SELECT winner as model FROM votes
                UNION ALL
                SELECT loser as model FROM votes
            )
            GROUP BY model''')
        total_matches = {row['model']: row['match_count'] for row in total_matches_cursor.fetchall()}
        elo_cursor = db.execute('SELECT model, elo, COALESCE(frozen, 0) as frozen FROM model_elo')
        elo_data = {row['model']: {'elo': row['elo'], 'frozen': bool(row['frozen'])} for row in elo_cursor.fetchall()}

        leaderboard = []
        for model_id, model in MODELS.items():
            is_open_source = model['open_source']
            if (model_type == 'open-source' and not is_open_source) or \
               (model_type == 'closed-source' and is_open_source):
                continue
            model_wins = wins.get(model_id, 0)
            model_matches = total_matches.get(model_id, 0)
            win_rate = (model_wins / model_matches * 100) if model_matches > 0 else 0
            model_elo_data = elo_data.get(model_id, {'elo': DEFAULT_ELO, 'frozen': False})
            leaderboard.append({
                "id": model_id,
                "name": model['name'],
                "display": f"{model.get('provider')}: {model['name']}" if model.get('provider') else model['name'],
                "provider": model.get('provider') or '',
                "wins": model_wins,
                "matches": model_matches,
                "win_rate": round(win_rate, 2),
                "elo": round(model_elo_data['elo'], 1),
                "open_source": is_open_source,
                "frozen": model_elo_data['frozen']
            })
        leaderboard.sort(key=lambda x: x['elo'], reverse=True)
        return jsonify(leaderboard)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Database error while fetching leaderboard"}), 500
    except Exception as e:
        print(f"Error fetching leaderboard: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@app.route('/api/leaderboard/mine')
@login_required
def get_personal_leaderboard():
    """Saját toplista: ELO kiszámítása csak a bejelentkezett felhasználó szavazatai alapján."""
    try:
        user = get_current_user()
        user_id = user['id']
        db = get_db()

        # Csak a felhasználó saját szavazatai
        rows = db.execute(
            'SELECT winner, loser FROM votes WHERE user_id = ? ORDER BY id ASC',
            (user_id,)
        ).fetchall()

        model_type = request.args.get('model_type', 'all')

        if not rows:
            # Nincs még szavazat: visszaadjuk az összes modellt DEFAULT_ELO-val
            leaderboard = [
                {
                    "id": model_id,
                    "name": model['name'],
                    "wins": 0, "matches": 0, "win_rate": 0.0,
                    "elo": DEFAULT_ELO,
                    "open_source": model['open_source'],
                    "frozen": False
                }
                for model_id, model in MODELS.items()
                if not ((model_type == 'open-source' and not model['open_source']) or
                        (model_type == 'closed-source' and model['open_source']))
            ]
            leaderboard.sort(key=lambda x: x['elo'], reverse=True)
            return jsonify({"leaderboard": leaderboard, "vote_count": 0})

        # ELO számítás nulláról, csak saját szavazatokból
        from config import K_FACTOR
        personal_elo = {m: DEFAULT_ELO for m in MODELS}
        wins = {m: 0 for m in MODELS}
        matches = {m: 0 for m in MODELS}

        for row in rows:
            winner, loser = row['winner'], row['loser']
            if winner not in personal_elo or loser not in personal_elo:
                continue
            w_elo = personal_elo[winner]
            l_elo = personal_elo[loser]
            expected_w = 1 / (1 + 10 ** ((l_elo - w_elo) / 400))
            expected_l = 1 - expected_w
            personal_elo[winner] = w_elo + K_FACTOR * (1 - expected_w)
            personal_elo[loser]  = l_elo + K_FACTOR * (0 - expected_l)
            wins[winner] += 1
            matches[winner] += 1
            matches[loser]  += 1

        model_type = request.args.get('model_type', 'all')
        leaderboard = []
        for model_id, model in MODELS.items():
            is_open_source = model['open_source']
            if (model_type == 'open-source' and not is_open_source) or \
               (model_type == 'closed-source' and is_open_source):
                continue
            m = matches[model_id]
            w = wins[model_id]
            leaderboard.append({
                "id": model_id,
                "name": model['name'],
                "display": f"{model.get('provider')}: {model['name']}" if model.get('provider') else model['name'],
                "provider": model.get('provider') or '',
                "wins": w,
                "matches": m,
                "win_rate": round(w / m * 100, 2) if m > 0 else 0.0,
                "elo": round(personal_elo[model_id], 1),
                "open_source": is_open_source,
                "frozen": False
            })
        leaderboard.sort(key=lambda x: x['elo'], reverse=True)
        return jsonify({"leaderboard": leaderboard, "vote_count": len(rows)})
    except sqlite3.Error as e:
        print(f"Database error (personal leaderboard): {e}")
        return jsonify({"error": "Database error"}), 500
    except Exception as e:
        print(f"Error (personal leaderboard): {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


@app.route('/api/elo_history')
def get_elo_history():
    """Lekérdezi az ELO értékek időbeli változását a grafikonhoz."""
    try:
        db = get_db()
        cursor = db.execute("""
            SELECT model, elo, timestamp 
            FROM elo_history 
            ORDER BY timestamp ASC
        """)
        history_data = cursor.fetchall()
        
        # Adatok átalakítása a grafikonhoz megfelelő formátumba
        # { "Modell Neve": [{x: timestamp, y: elo}, ...], ... }
        chart_data_for_frontend = {}
        for row in history_data:
            model_id = row['model']
            
            # Biztosítjuk, hogy a model_id létezik a MODELS konfigurációban
            if model_id not in MODELS:
                print(f"Figyelem: a(z) {model_id} model_id az elo_history táblából nem található a MODELS konfigurációban. Kihagyva.")
                continue

            model_name = MODELS[model_id]['name'] # Modell nevének lekérése

            if model_name not in chart_data_for_frontend:
                chart_data_for_frontend[model_name] = []
            
            chart_data_for_frontend[model_name].append({
                'x': row['timestamp'], # A timestamp string formátumban van, amit a JS new Date() kezel
                'y': round(row['elo'], 1)
            })
            
        return jsonify(chart_data_for_frontend)
    except sqlite3.Error as e:
        print(f"Database error fetching ELO history: {e}")
        return jsonify({"error": "Database error while fetching ELO history"}), 500
    except Exception as e:
        print(f"Error fetching ELO history: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/elo_history_with_current_elo')
def get_elo_history_with_current_elo():
    """Lekérdezi az ELO értékek időbeli változását és az aktuális ELO pontszámokat."""
    try:
        db = get_db()
        
        # ELO History
        history_cursor = db.execute("""
            SELECT model, elo, timestamp 
            FROM elo_history 
            ORDER BY timestamp ASC
        """)
        history_data_rows = history_cursor.fetchall()
        
        chart_data_for_frontend = {}
        for row in history_data_rows:
            model_id = row['model']
            if model_id not in MODELS:
                print(f"Figyelem: a(z) {model_id} model_id az elo_history táblából nem található a MODELS konfigurációban. Kihagyva.")
                continue
            model_name = MODELS[model_id]['name']
            if model_name not in chart_data_for_frontend:
                chart_data_for_frontend[model_name] = []
            chart_data_for_frontend[model_name].append({
                'x': row['timestamp'],
                'y': round(row['elo'], 1)
            })

        # Current ELOs
        elo_cursor = db.execute('SELECT model, elo FROM model_elo')
        current_elos_raw = {row['model']: row['elo'] for row in elo_cursor.fetchall()}
        
        current_elos_for_frontend = {}
        for model_id, elo_score in current_elos_raw.items():
            if model_id in MODELS: # Ensure model_id is valid
                 current_elos_for_frontend[MODELS[model_id]['name']] = round(elo_score, 1)
            else:
                print(f"Figyelem: a(z) {model_id} model_id az model_elo táblából nem található a MODELS konfigurációban (current ELOs). Kihagyva.")


        return jsonify({
            "history": chart_data_for_frontend,
            "current_elos": current_elos_for_frontend
        })
    except sqlite3.Error as e:
        print(f"Database error fetching ELO history with current ELOs: {e}")
        return jsonify({"error": "Database error while fetching ELO history with current ELOs"}), 500
    except Exception as e:
        print(f"Error fetching ELO history with current ELOs: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/api/prompt_ids')
def get_prompt_ids_api():
    """Visszaadja az összes prompt ID-t (sorrendben)."""
    if not AVAILABLE_PROMPTS:
        update_available_prompts()
    return jsonify({"prompt_ids": AVAILABLE_PROMPTS})

@app.route('/api/prompt_text')
def get_prompt_text_api():
    """Visszaadja a prompt szövegét egy adott prompt_id-hoz."""
    prompt_id = request.args.get('prompt_id')
    if not prompt_id or prompt_id not in AVAILABLE_PROMPTS:
        return jsonify({"error": "Invalid or missing prompt_id"}), 400
    prompt_path = os.path.join(app.config['DATA_DIR'], prompt_id, 'prompt.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            prompt_text = f.read().strip()
        return jsonify({"prompt_text": prompt_text})
    except Exception as e:
        return jsonify({"error": f"Error reading prompt: {e}"}), 500


@app.route('/api/model_info')
def get_model_info():
    """Visszaadja egy vagy két modell konfigurációs adatait összehasonlításhoz."""
    model1_id = request.args.get('model1')
    model2_id = request.args.get('model2')

    if not model1_id:
        return jsonify({"error": "model1 parameter is required"}), 400
    if model1_id not in MODELS:
        return jsonify({"error": f"Invalid model1 key: {model1_id}"}), 400
    if model2_id and model2_id not in MODELS:
        return jsonify({"error": f"Invalid model2 key: {model2_id}"}), 400

    def build_model_info(model_id):
        m = MODELS[model_id]
        return {
            "id": model_id,
            "name": m['name'],
            "provider": m.get('provider', 'Unknown'),
            "open_source": m['open_source'],
            "release_date": m.get('release_date'),
            "type": m.get('type', 'image-generation'),
            "tags": m.get('tags', []),
            "max_resolution": m.get('max_resolution'),
            "pricing": m.get('pricing'),
            "api_available": m.get('api_available', False),
            "speed": m.get('speed'),
            "website": m.get('website'),
        }

    result = {"model1": build_model_info(model1_id)}
    if model2_id:
        result["model2"] = build_model_info(model2_id)
    return jsonify(result)


@app.route('/api/compare_stats')
def get_compare_stats():
    """Visszaadja két modell összehasonlító statisztikáit: prompt-szintű szavazatok és head-to-head eredmények."""
    model1_id = request.args.get('model1')
    model2_id = request.args.get('model2')

    if not model1_id or not model2_id:
        return jsonify({"error": "Both model1 and model2 parameters are required"}), 400
    if model1_id not in MODELS or model2_id not in MODELS:
        return jsonify({"error": "Invalid model key provided"}), 400

    try:
        db = get_db()

        # Aktuális ELO értékek
        elo1_row = db.execute('SELECT elo FROM model_elo WHERE model = ?', (model1_id,)).fetchone()
        elo2_row = db.execute('SELECT elo FROM model_elo WHERE model = ?', (model2_id,)).fetchone()
        elo1 = round(elo1_row['elo'], 1) if elo1_row else DEFAULT_ELO
        elo2 = round(elo2_row['elo'], 1) if elo2_row else DEFAULT_ELO

        # Globális győzelmek és meccsek
        def get_model_global_stats(model_id):
            wins = db.execute('SELECT COUNT(*) as c FROM votes WHERE winner = ?', (model_id,)).fetchone()['c']
            total = db.execute(
                'SELECT COUNT(*) as c FROM votes WHERE winner = ? OR loser = ?',
                (model_id, model_id)
            ).fetchone()['c']
            return {"wins": wins, "matches": total, "win_rate": round(wins / total * 100, 2) if total > 0 else 0}

        model1_global = get_model_global_stats(model1_id)
        model2_global = get_model_global_stats(model2_id)

        # Head-to-head statisztikák (egymás ellen)
        h2h_1_wins = db.execute(
            'SELECT COUNT(*) as c FROM votes WHERE winner = ? AND loser = ?',
            (model1_id, model2_id)
        ).fetchone()['c']
        h2h_2_wins = db.execute(
            'SELECT COUNT(*) as c FROM votes WHERE winner = ? AND loser = ?',
            (model2_id, model1_id)
        ).fetchone()['c']
        h2h_total = h2h_1_wins + h2h_2_wins

        # Prompt-szintű statisztikák: minden promptra mennyi szavazat esett az adott modellre és hányszor nyert
        prompt_stats = []
        if AVAILABLE_PROMPTS:
            for prompt_id in sorted(AVAILABLE_PROMPTS):
                # Prompt text
                prompt_path = os.path.join(app.config['DATA_DIR'], prompt_id, 'prompt.txt')
                try:
                    with open(prompt_path, 'r', encoding='utf-8') as f:
                        prompt_text = f.read().strip()
                except Exception:
                    prompt_text = prompt_id

                # Model 1 statisztikák ennél a promptnál
                m1_wins = db.execute(
                    'SELECT COUNT(*) as c FROM votes WHERE prompt_id = ? AND winner = ?',
                    (prompt_id, model1_id)
                ).fetchone()['c']
                m1_total = db.execute(
                    'SELECT COUNT(*) as c FROM votes WHERE prompt_id = ? AND (winner = ? OR loser = ?)',
                    (prompt_id, model1_id, model1_id)
                ).fetchone()['c']

                # Model 2 statisztikák ennél a promptnál
                m2_wins = db.execute(
                    'SELECT COUNT(*) as c FROM votes WHERE prompt_id = ? AND winner = ?',
                    (prompt_id, model2_id)
                ).fetchone()['c']
                m2_total = db.execute(
                    'SELECT COUNT(*) as c FROM votes WHERE prompt_id = ? AND (winner = ? OR loser = ?)',
                    (prompt_id, model2_id, model2_id)
                ).fetchone()['c']

                prompt_stats.append({
                    "prompt_id": prompt_id,
                    "prompt_text": prompt_text[:100] + ('...' if len(prompt_text) > 100 else ''),
                    "model1": {"wins": m1_wins, "matches": m1_total, "win_rate": round(m1_wins / m1_total * 100, 1) if m1_total > 0 else 0},
                    "model2": {"wins": m2_wins, "matches": m2_total, "win_rate": round(m2_wins / m2_total * 100, 1) if m2_total > 0 else 0},
                })

        return jsonify({
            "model1": {
                "id": model1_id,
                "name": MODELS[model1_id]['name'],
                "elo": elo1,
                **model1_global
            },
            "model2": {
                "id": model2_id,
                "name": MODELS[model2_id]['name'],
                "elo": elo2,
                **model2_global
            },
            "head_to_head": {
                "model1_wins": h2h_1_wins,
                "model2_wins": h2h_2_wins,
                "total": h2h_total,
            },
            "prompt_stats": prompt_stats,
        })
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return jsonify({"error": "Database error while fetching compare stats"}), 500
    except Exception as e:
        print(f"Error fetching compare stats: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500


if __name__ == '__main__':
    # Parancssori argumentumok kezelése
    if len(sys.argv) > 1 and sys.argv[1] == 'reset-votes':
        if reset_votes():
            print("A szavazatok sikeresen törölve!")
            sys.exit(0)
        else:
            print("Hiba történt a szavazatok törlése közben!")
            sys.exit(1)
    
    # Indítás előtt frissítjük a prompt listát
    update_available_prompts()
    # Debug mód fejlesztéshez, élesben False és használj pl. Gunicornt/Waitress-t
    app.run(debug=DEBUG_MODE, host='0.0.0.0')
