import sqlite3
import os
import math
import datetime
import logging
from contextlib import contextmanager
from flask import g
from config import DATABASE, DATA_DIR, MODELS, DEFAULT_ELO, K_FACTOR

logger = logging.getLogger(__name__)

# A séma verziója (PRAGMA user_version). Minden új migráció eggyel növeli.
SCHEMA_VERSION = 1

# Szavazat kimenetelek a votes táblában.
# 'win': winner nyert loser ellen; 'tie' / 'both_bad': döntetlen (winner = bal, loser = jobb oldali modell).
OUTCOME_WIN = 'win'
OUTCOME_TIE = 'tie'
OUTCOME_BOTH_BAD = 'both_bad'
DRAW_OUTCOMES = (OUTCOME_TIE, OUTCOME_BOTH_BAD)


# --- Időbélyegek ---

def utc_now_naive():
    """Aktuális UTC idő időzóna nélküli datetime-ként."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def utc_now_iso():
    """Aktuális UTC idő ISO 8601 formátumban, milliszekundum pontossággal: 2026-09-30T12:34:56.789Z"""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.strftime('%Y-%m-%dT%H:%M:%S.') + f'{now.microsecond // 1000:03d}Z'


def to_iso_utc(value):
    """Régi ('2025-04-04 09:21:56[.ffffff]') vagy ISO időbélyeget egységes ISO UTC formára alakít.
    Az időzóna nélküli régi értékeket UTC-nek tekintjük (a szerver UTC-ben fut)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace(' ', 'T')
    if text.endswith('Z'):
        text = text[:-1]
    elif '+' in text[10:]:
        text = text[:10] + text[10:].split('+', 1)[0]
    try:
        parsed = datetime.datetime.fromisoformat(text)
    except ValueError:
        return str(value)
    return parsed.strftime('%Y-%m-%dT%H:%M:%S.') + f'{parsed.microsecond // 1000:03d}Z'


def utc_iso_from_datetime(value):
    """datetime objektumot (naiv = UTC) ISO UTC szöveggé alakít."""
    if value.tzinfo is not None:
        value = value.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return value.strftime('%Y-%m-%dT%H:%M:%S.') + f'{value.microsecond // 1000:03d}Z'


# --- ELO rating számítás ---

def calculate_expected_score(rating_a, rating_b):
    """
    Kiszámítja az A játékos várható eredményét B játékossal szemben.
    A várható eredmény 0-1 közötti szám, ahol 1 a biztos győzelem, 0 a biztos vereség.
    """
    return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))

def calculate_new_elo(rating, expected_score, actual_score, k_factor=K_FACTOR):
    """
    Kiszámítja az új ELO értéket a régi értékből és az eredményekből.

    :param rating: A jelenlegi ELO értéke a játékosnak
    :param expected_score: A várható eredmény (0-1 közötti szám)
    :param actual_score: A tényleges eredmény (1 győzelem, 0.5 döntetlen, 0 vereség)
    :param k_factor: K-faktor, amely befolyásolja a változás mértékét
    :return: Az új ELO érték
    """
    return rating + k_factor * (actual_score - expected_score)

def get_current_elo(db, model_id):
    """
    Lekérdezi a modell aktuális ELO értékét az adatbázisból az ID alapján.
    Ha még nincs ELO értéke, létrehozza az alapértelmezett értékkel.
    """
    result = db.execute('SELECT elo FROM model_elo WHERE model = ?', (model_id,)).fetchone()
    if result:
        return result['elo']
    db.execute('INSERT INTO model_elo (model, elo, last_updated) VALUES (?, ?, ?)',
               (model_id, DEFAULT_ELO, utc_now_iso()))
    return DEFAULT_ELO

def update_elo(db, model_a, model_b, score_a):
    """
    Frissíti két modell online ELO értékét egy mérkőzés után, és rögzíti a historikus táblában.

    :param score_a: A modell_a eredménye: 1 győzelem, 0.5 döntetlen, 0 vereség
    :return: {model_a: (régi, új), model_b: (régi, új)}
    """
    elo_a = get_current_elo(db, model_a)
    elo_b = get_current_elo(db, model_b)
    new_a = calculate_new_elo(elo_a, calculate_expected_score(elo_a, elo_b), score_a)
    new_b = calculate_new_elo(elo_b, calculate_expected_score(elo_b, elo_a), 1 - score_a)
    timestamp = utc_now_iso()
    for model_id, new_elo in ((model_a, new_a), (model_b, new_b)):
        db.execute('UPDATE model_elo SET elo = ?, last_updated = ? WHERE model = ?',
                   (new_elo, timestamp, model_id))
        db.execute('INSERT INTO elo_history (model, elo, timestamp) VALUES (?, ?, ?)',
                   (model_id, new_elo, timestamp))
    return {model_a: (elo_a, new_a), model_b: (elo_b, new_b)}


# --- Kapcsolatkezelés ---

def connect(path=None):
    db = sqlite3.connect(path or DATABASE, timeout=10)
    db.row_factory = sqlite3.Row  # Sorok szótárként való eléréséhez
    return db

def get_db():
    """Adatbázis kapcsolat létrehozása vagy visszaadása."""
    db = g.get('db')
    if db is None:
        db = connect()
        g.db = db
    return db


def close_db(_error=None):
    """Lezárja az aktuális kéréshez tartozó adatbázis kapcsolatot."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


@contextmanager
def immediate_transaction(db):
    """Írási zárral induló tranzakció: az olvasás-módosítás-írás lépések (pl. ELO frissítés)
    párhuzamos kérések mellett sem veszítenek el frissítést."""
    if db.in_transaction:
        db.commit()
    db.execute('BEGIN IMMEDIATE')
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    else:
        db.commit()


# --- Séma és migrációk ---

def _columns(db, table):
    return {row['name'] for row in db.execute(f"PRAGMA table_info('{table}')").fetchall()}

def _add_column_if_missing(db, table, column, definition):
    if column not in _columns(db, table):
        logger.info("Adding '%s' column to %s table...", column, table)
        db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')

def _normalize_timestamps(db, table, column, key='rowid'):
    rows = db.execute(
        f"SELECT {key} AS k, {column} AS v FROM {table} WHERE {column} IS NOT NULL AND {column} NOT LIKE '%Z'"
    ).fetchall()
    for row in rows:
        db.execute(f'UPDATE {table} SET {column} = ? WHERE {key} = ?', (to_iso_utc(row['v']), row['k']))
    if rows:
        logger.info('Normalized %d timestamps in %s.%s', len(rows), table, column)

def _migrate_v1(db):
    """Szerveroldali battle-ök, döntetlenek, oldalnaplózás, indexek, ISO UTC időbélyegek."""
    _add_column_if_missing(db, 'votes', 'outcome', f"TEXT NOT NULL DEFAULT '{OUTCOME_WIN}'")
    _add_column_if_missing(db, 'votes', 'left_model', 'TEXT')
    _add_column_if_missing(db, 'votes', 'battle_id', 'TEXT')
    db.execute('''
        CREATE TABLE IF NOT EXISTS battles (
            id TEXT PRIMARY KEY,
            session_key TEXT NOT NULL,
            user_id INTEGER,
            prompt_id TEXT NOT NULL,
            model_a TEXT NOT NULL,
            model_b TEXT NOT NULL,
            issued_at TEXT NOT NULL,
            resolved_at TEXT,
            outcome TEXT
        )
    ''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_battles_session ON battles (session_key, issued_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_battles_issued ON battles (issued_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_votes_prompt ON votes (prompt_id)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_votes_user_time ON votes (user_id, voted_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_votes_pair ON votes (winner, loser)')
    _normalize_timestamps(db, 'votes', 'voted_at')
    _normalize_timestamps(db, 'elo_history', 'timestamp')
    _normalize_timestamps(db, 'model_elo', 'last_updated')
    _normalize_timestamps(db, 'users', 'created_at')
    _normalize_timestamps(db, 'users', 'last_login')

MIGRATIONS = {1: _migrate_v1}


def init_db():
    """Adatbázis séma inicializálása és migrálása (ha szükséges)."""
    global DATABASE
    # Ha a DATABASE mappa nem létezik (pl. Render Persistent Disk), létrehozzuk
    db_dir = os.path.dirname(DATABASE)
    if db_dir:
        try:
            os.makedirs(db_dir, exist_ok=True)
        except OSError as e:
            logger.warning("Could not create database directory '%s': %s. Falling back to 'votes.db'", db_dir, e)
            DATABASE = 'votes.db'
    db = get_db()
    # A WAL mód tartós beállítás: az olvasások nem blokkolják az írást
    db.execute('PRAGMA journal_mode=WAL')
    table_names = {row['name'] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    now = utc_now_iso()

    with db:
        if 'votes' not in table_names:
            logger.info("Creating votes table...")
            db.execute('''
                CREATE TABLE votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_id TEXT NOT NULL,
                    winner TEXT NOT NULL,
                    loser TEXT NOT NULL,
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER
                )
            ''')
            db.execute('CREATE INDEX idx_winner ON votes (winner);')
            db.execute('CREATE INDEX idx_loser ON votes (loser);')

        if 'model_elo' not in table_names:
            logger.info("Creating model_elo table...")
            db.execute('''
                CREATE TABLE model_elo (
                    model TEXT PRIMARY KEY,
                    elo REAL NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

        # Frozen oszlop és user_id oszlop régebbi adatbázisokhoz
        _add_column_if_missing(db, 'model_elo', 'frozen', 'INTEGER DEFAULT 0')
        _add_column_if_missing(db, 'votes', 'user_id', 'INTEGER')

        # Biztosítjuk, hogy minden modell szerepeljen az ELO táblában
        for model in MODELS.keys():
            db.execute('INSERT OR IGNORE INTO model_elo (model, elo, last_updated) VALUES (?, ?, ?)',
                       (model, DEFAULT_ELO, now))

        if 'elo_history' not in table_names:
            logger.info("Creating elo_history table...")
            db.execute('''
                CREATE TABLE elo_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT NOT NULL,
                    elo REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            db.execute('CREATE INDEX idx_history_model_time ON elo_history (model, timestamp);')

        # Biztosítjuk, hogy minden modellnek legyen legalább egy kezdeti bejegyzése a historikus táblában
        for model in MODELS.keys():
            exists = db.execute('SELECT 1 FROM elo_history WHERE model = ? LIMIT 1', (model,)).fetchone()
            if not exists:
                db.execute('INSERT INTO elo_history (model, elo, timestamp) VALUES (?, ?, ?)',
                           (model, DEFAULT_ELO, now))

        if 'users' not in table_names:
            logger.info("Creating users table...")
            db.execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    email TEXT,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(provider, provider_id)
                )
            ''')

        version = db.execute('PRAGMA user_version').fetchone()[0]
        for target in sorted(MIGRATIONS):
            if version < target:
                logger.info('Running database migration v%d...', target)
                MIGRATIONS[target](db)
                db.execute(f'PRAGMA user_version = {int(target)}')
                version = target

    logger.info("Database initialization check complete (schema v%d).", SCHEMA_VERSION)

def get_prompt_ids():
    """Visszaadja az érvényes prompt ID-k (mappa nevek) listáját."""
    prompt_ids = []
    if not os.path.isdir(DATA_DIR):
        logger.error("Data directory '%s' not found.", DATA_DIR)
        return []
    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        # Érvényes prompt: mappa, amelyben van prompt.txt
        if os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, 'prompt.txt')):
            prompt_ids.append(item)

    prompt_ids.sort()
    logger.info("Found prompts: %s", prompt_ids)
    return prompt_ids

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    from app import app
    with app.app_context():
        init_db()
        get_prompt_ids()
