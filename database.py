import sqlite3
import os
import math
import datetime
from config import DATABASE, DATA_DIR, MODELS, DEFAULT_ELO, K_FACTOR

# ELO rating számítás függvényei
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
    :param actual_score: A tényleges eredmény (1 győzelem, 0 vereség esetén)
    :param k_factor: K-faktor, amely befolyásolja a változás mértékét
    :return: Az új ELO érték
    """
    return rating + k_factor * (actual_score - expected_score)

def get_current_elo(db, model_id):
    """
    Lekérdezi a modell aktuális ELO értékét az adatbázisból az ID alapján.
    Ha még nincs ELO értéke, az alapértelmezett értéket adja vissza.
    """
    try:
        cur = db.execute('SELECT elo FROM model_elo WHERE model = ?', (model_id,))
        result = cur.fetchone()
        if result:
            return result['elo']
        else:
            db.execute('INSERT INTO model_elo (model, elo) VALUES (?, ?)', 
                      (model_id, DEFAULT_ELO))
            db.commit()
            return DEFAULT_ELO
    except Exception as e:
        print(f"Error getting ELO for {model_id}: {e}")
        return DEFAULT_ELO

def update_elo(db, winner_id, loser_id):
    """
    Frissíti a nyertes és vesztes modellek ELO értékét egy mérkőzés után,
    és rögzíti a változást a historikus táblában. Azonosítóval dolgozik.
    """
    winner_elo = get_current_elo(db, winner_id)
    loser_elo = get_current_elo(db, loser_id)
    winner_expected = calculate_expected_score(winner_elo, loser_elo)
    loser_expected = calculate_expected_score(loser_elo, winner_elo)
    winner_new_elo = calculate_new_elo(winner_elo, winner_expected, 1)
    loser_new_elo = calculate_new_elo(loser_elo, loser_expected, 0)
    current_timestamp = datetime.datetime.now()
    db.execute('UPDATE model_elo SET elo = ?, last_updated = ? WHERE model = ?', 
              (winner_new_elo, current_timestamp, winner_id))
    db.execute('UPDATE model_elo SET elo = ?, last_updated = ? WHERE model = ?', 
              (loser_new_elo, current_timestamp, loser_id))
    db.execute('INSERT INTO elo_history (model, elo, timestamp) VALUES (?, ?, ?)',
              (winner_id, winner_new_elo, current_timestamp))
    db.execute('INSERT INTO elo_history (model, elo, timestamp) VALUES (?, ?, ?)',
              (loser_id, loser_new_elo, current_timestamp))
    return winner_new_elo, loser_new_elo

def get_db():
    """Adatbázis kapcsolat létrehozása vagy visszaadása."""
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row # Sorok szótárként való eléréséhez
    return db

def ensure_frozen_column(db):
    """Ellenőrzi és hozzáadja a 'frozen' oszlopot a model_elo táblához, ha még nem létezik."""
    cur = db.execute("PRAGMA table_info('model_elo')")
    cols = [row['name'] for row in cur.fetchall()]
    if 'frozen' not in cols:
        print("Adding 'frozen' column to model_elo table...")
        db.execute("ALTER TABLE model_elo ADD COLUMN frozen INTEGER DEFAULT 0")
        db.commit()

def init_db():
    """Adatbázis séma inicializálása (ha még nem létezik)."""
    db = get_db()
    tables_exist = db.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name='votes' OR name='model_elo' OR name='elo_history')").fetchall()
    table_names = {row['name'] for row in tables_exist}

    with db:
        if 'votes' not in table_names:
            print("Creating votes table...")
            db.execute('''
                CREATE TABLE votes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_id TEXT NOT NULL,
                    winner TEXT NOT NULL,
                    loser TEXT NOT NULL,
                    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            db.execute('CREATE INDEX idx_winner ON votes (winner);')
            db.execute('CREATE INDEX idx_loser ON votes (loser);')

        if 'model_elo' not in table_names:
            print("Creating model_elo table...")
            db.execute('''
                CREATE TABLE model_elo (
                    model TEXT PRIMARY KEY,
                    elo REAL NOT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Kezdeti ELO értékek minden modellhez
            for model in MODELS.keys():
                db.execute('INSERT OR IGNORE INTO model_elo (model, elo) VALUES (?, ?)', 
                          (model, DEFAULT_ELO))
        else:
            # Biztosítjuk, hogy minden modell szerepeljen az ELO táblában
            for model in MODELS.keys():
                 db.execute('INSERT OR IGNORE INTO model_elo (model, elo) VALUES (?, ?)', 
                           (model, DEFAULT_ELO))
        
        # Frozen oszlop hozzáadása, ha még nem létezik
        ensure_frozen_column(db)

        if 'elo_history' not in table_names:
            print("Creating elo_history table...")
            db.execute('''
                CREATE TABLE elo_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model TEXT NOT NULL,
                    elo REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            db.execute('CREATE INDEX idx_history_model_time ON elo_history (model, timestamp);')
            # Kezdeti ELO értékek rögzítése a historikus táblában is
            for model in MODELS.keys():
                db.execute('INSERT INTO elo_history (model, elo) VALUES (?, ?)', 
                          (model, DEFAULT_ELO))
        else:
             # Biztosítjuk, hogy minden modellnek legyen legalább egy kezdeti bejegyzése a historikus táblában
             for model in MODELS.keys():
                 exists = db.execute('SELECT 1 FROM elo_history WHERE model = ? LIMIT 1', (model,)).fetchone()
                 if not exists:
                     db.execute('INSERT INTO elo_history (model, elo) VALUES (?, ?)', 
                               (model, DEFAULT_ELO))

    print("Database initialization check complete.")

def get_prompt_ids():
    """Visszaadja az érvényes prompt ID-k (mappa nevek) listáját."""
    prompt_ids = []
    if not os.path.isdir(DATA_DIR):
        print(f"Error: Data directory '{DATA_DIR}' not found.")
        return []
    for item in os.listdir(DATA_DIR):
        item_path = os.path.join(DATA_DIR, item)
        # Ellenőrzi, hogy mappa-e és tartalmazza-e a szükséges fájlokat
        if os.path.isdir(item_path):
            # Ellenőrizhetjük, hogy minden modell kép és prompt.txt megvan-e
            # Egyszerűsítésként most csak azt nézzük, van-e prompt.txt
            prompt_file = os.path.join(item_path, 'prompt.txt')
            if os.path.exists(prompt_file):
                 prompt_ids.append(item)
            # else:
            #     print(f"Warning: Skipping directory '{item}' - missing prompt.txt")

    prompt_ids.sort() # Sorba rendezés (opcionális, de szebb)
    print(f"Found prompts: {prompt_ids}")
    return prompt_ids

if __name__ == '__main__':
    init_db()
    get_prompt_ids() # Csak teszteléshez induláskor