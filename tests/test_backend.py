"""Backend tesztek (pytest). Futtatás: python -m pytest tests"""
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
_tmpdir = tempfile.mkdtemp(prefix='arena-test-')
os.environ['DATABASE_PATH'] = os.path.join(_tmpdir, 'test.db')
os.environ['SECRET_KEY'] = 'test-secret'
os.environ.pop('DATA_MODE', None)

import app as arena  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    monkeypatch.setattr(arena, 'MIN_VOTE_DELAY_MS', 0)
    monkeypatch.setattr(arena, 'battle_rate_limiter', arena.SlidingWindowRateLimiter(1000, 60))
    monkeypatch.setattr(arena, 'ip_rate_limiter', arena.SlidingWindowRateLimiter(10000, 60))
    with arena.app.app_context():
        arena.reset_votes()
    yield


def login(client, user_id=1, name='Teszt'):
    with arena.app.app_context():
        db = arena.get_db()
        with db:
            user_id = arena.save_user(db, 'test', str(user_id), f'{user_id}@example.com', name)
    with client.session_transaction() as sess:
        sess['user'] = {'id': user_id, 'name': name, 'provider': 'test'}
    client.get('/')  # CSRF token létrehozása
    with client.session_transaction() as sess:
        return sess['_csrf_token']


def new_battle(client):
    response = client.get('/api/battle_data')
    assert response.status_code == 200, response.json
    return response.json


def vote(client, token, battle_id, choice='a'):
    return client.post('/api/vote', json={'battle_id': battle_id, 'choice': choice},
                       headers={'X-CSRF-Token': token})


def count_votes():
    with arena.app.app_context():
        return arena.get_db().execute('SELECT COUNT(*) FROM votes').fetchone()[0]


def test_battle_does_not_reveal_models():
    client = arena.app.test_client()
    battle = new_battle(client)
    body = str(battle)
    assert 'model_a' not in battle and 'model1' not in battle
    for model in arena.MODELS.values():
        assert f"'{model['name']}'" not in body


def test_vote_records_and_reveals():
    client = arena.app.test_client()
    token = login(client)
    battle = new_battle(client)
    response = vote(client, token, battle['battle_id'], 'a')
    assert response.status_code == 200, response.json
    data = response.json
    assert data['model_a']['elo_delta'] > 0 > data['model_b']['elo_delta']
    assert data['votes_today'] == 1
    with arena.app.app_context():
        row = arena.get_db().execute('SELECT * FROM votes').fetchone()
    assert row['winner'] == data['model_a']['id'] and row['outcome'] == 'win'
    assert row['left_model'] == data['model_a']['id']
    assert row['voted_at'].endswith('Z')


def test_same_battle_cannot_be_voted_twice():
    client = arena.app.test_client()
    token = login(client)
    battle = new_battle(client)
    assert vote(client, token, battle['battle_id']).status_code == 200
    assert vote(client, token, battle['battle_id']).status_code == 409
    assert count_votes() == 1


def test_replayed_session_cookie_is_rejected():
    """A régi (aláírt) session cookie visszajátszása sem ad újabb szavazatot."""
    client = arena.app.test_client()
    token = login(client)
    battle = new_battle(client)
    old_cookie = client.get_cookie('session').value
    assert vote(client, token, battle['battle_id']).status_code == 200
    client.set_cookie('session', old_cookie)
    assert vote(client, token, battle['battle_id']).status_code == 409
    assert count_votes() == 1


def test_battle_of_other_session_is_rejected():
    owner, attacker = arena.app.test_client(), arena.app.test_client()
    login(owner, user_id=1)
    token = login(attacker, user_id=2)
    battle = new_battle(owner)
    assert vote(attacker, token, battle['battle_id']).status_code == 409


def test_too_fast_vote_is_rejected(monkeypatch):
    monkeypatch.setattr(arena, 'MIN_VOTE_DELAY_MS', 60_000)
    client = arena.app.test_client()
    token = login(client)
    battle = new_battle(client)
    assert vote(client, token, battle['battle_id']).status_code == 429


def test_daily_limit(monkeypatch):
    monkeypatch.setattr(arena, 'DAILY_VOTE_LIMIT', 2)
    client = arena.app.test_client()
    token = login(client)
    for _ in range(2):
        assert vote(client, token, new_battle(client)['battle_id']).status_code == 200
    assert vote(client, token, new_battle(client)['battle_id']).status_code == 429


@pytest.mark.parametrize('choice', ['tie', 'both_bad'])
def test_draws_move_elo_towards_each_other(choice):
    client = arena.app.test_client()
    token = login(client)
    battle = new_battle(client)
    data = vote(client, token, battle['battle_id'], choice).json
    assert data['model_a']['elo_delta'] == 0 and data['model_b']['elo_delta'] == 0  # azonos ELO-ról indulnak
    with arena.app.app_context():
        row = arena.get_db().execute('SELECT outcome FROM votes').fetchone()
    assert row['outcome'] == choice


def test_vote_requires_login_and_csrf():
    client = arena.app.test_client()
    battle = new_battle(client)
    assert client.post('/api/vote', json={'battle_id': battle['battle_id'], 'choice': 'a'}).status_code == 401
    login(client)
    assert client.post('/api/vote', json={'battle_id': battle['battle_id'], 'choice': 'a'}).status_code == 403


def test_skip_reveals_and_closes_battle():
    client = arena.app.test_client()
    token = login(client)
    battle = new_battle(client)
    skipped = client.post('/api/battle/skip', json={'battle_id': battle['battle_id']},
                          headers={'X-CSRF-Token': token})
    assert skipped.status_code == 200 and skipped.json['model_a']['display']
    assert vote(client, token, battle['battle_id']).status_code == 409


def test_only_recent_battles_stay_open(monkeypatch):
    monkeypatch.setattr(arena, 'MAX_OPEN_BATTLES', 2)
    client = arena.app.test_client()
    token = login(client)
    first = new_battle(client)
    new_battle(client)
    new_battle(client)
    assert vote(client, token, first['battle_id']).status_code == 409


def test_battle_rate_limit_is_per_session(monkeypatch):
    monkeypatch.setattr(arena, 'battle_rate_limiter', arena.SlidingWindowRateLimiter(2, 60))
    client = arena.app.test_client()
    assert client.get('/api/battle_data').status_code == 200
    assert client.get('/api/battle_data').status_code == 200
    assert client.get('/api/battle_data').status_code == 429
    # Egy másik látogató (ugyanarról az IP-ről) nem esik bele ugyanabba a korlátba
    assert arena.app.test_client().get('/api/battle_data').status_code == 200


def test_battle_pairs_share_a_prompt():
    with arena.app.app_context():
        arena.update_available_prompts()
        for (a, b), prompts in arena._battle_candidate_pairs().items():
            for prompt_id in prompts:
                files = arena.get_prompt_model_files(prompt_id)
                assert a in files and b in files


def test_side_by_side_next_prompt_and_validation():
    client = arena.app.test_client()
    data = client.get('/api/side_by_side_data?model1=model-001&model2=model-002&after=001').json
    assert data['prompt_id'] > '001'
    assert data['model1']['display'] and data['model2']['image_url']
    assert client.get('/api/side_by_side_data?model1=model-001&model2=model-001').status_code == 400


def test_unknown_prompt_does_not_rescan(monkeypatch):
    calls = []
    monkeypatch.setattr(arena, 'update_available_prompts', lambda: calls.append(1))
    client = arena.app.test_client()
    assert client.get('/api/get_image?model=model-001&prompt_id=nope').status_code == 400
    assert not calls


def test_timestamp_normalization():
    from database import to_iso_utc
    assert to_iso_utc('2025-04-04 09:21:56') == '2025-04-04T09:21:56.000Z'
    assert to_iso_utc('2026-02-27 01:15:41.549679') == '2026-02-27T01:15:41.549Z'
    assert to_iso_utc('2026-02-27T01:15:41.549Z') == '2026-02-27T01:15:41.549Z'


# --- Rangsor (Bradley-Terry) ---

def test_bradley_terry_recovers_strengths():
    import numpy as np
    import ranking
    rng = np.random.default_rng(0)
    true = np.array([0.0, 1.0, 2.0, -1.0])
    pairs = []
    for _ in range(20000):
        i, j = rng.choice(4, 2, replace=False)
        pairs.append((i, j, 1.0 if rng.random() < 1 / (1 + np.exp(true[j] - true[i])) else 0.0))
    theta = ranking.fit_bradley_terry(ranking.build_win_matrix(pairs, 4), prior_games=0.0)
    assert np.allclose(theta - theta.mean(), true - true.mean(), atol=0.08)


def test_rank_spread_overlaps():
    import ranking
    best, worst = ranking.rank_spread([1600, 1550, 1400], [1700, 1650, 1450])
    assert list(best) == [1, 1, 3] and list(worst) == [2, 2, 3]


def test_leaderboard_has_ranking_fields():
    client = arena.app.test_client()
    token = login(client)
    for _ in range(3):
        vote(client, token, new_battle(client)['battle_id'], 'a')
    arena._ranking_cache['data'] = None
    rows = client.get('/api/leaderboard').json
    played = [r for r in rows if r['matches'] > 0]
    assert played and all(r['ci_lower'] <= r['score'] <= r['ci_upper'] for r in played)
    assert all(r['preliminary'] for r in played)
    assert all(r['rank'] is None for r in rows if r['matches'] == 0)
    scores = [r['score'] for r in played]
    assert scores == sorted(scores, reverse=True)


def test_personal_leaderboard_unlocks_after_min_votes(monkeypatch):
    monkeypatch.setattr(arena, 'PERSONAL_LEADERBOARD_MIN_VOTES', 3)
    client = arena.app.test_client()
    token = login(client)
    vote(client, token, new_battle(client)['battle_id'], 'a')
    locked = client.get('/api/leaderboard/mine').json
    assert locked['unlocked'] is False and locked['vote_count'] == 1 and locked['leaderboard'] == []
    for _ in range(2):
        vote(client, token, new_battle(client)['battle_id'], 'tie')
    unlocked = client.get('/api/leaderboard/mine').json
    assert unlocked['unlocked'] is True and unlocked['leaderboard']


def test_stats_matrix_and_history_endpoints():
    client = arena.app.test_client()
    token = login(client)
    for choice in ('a', 'a', 'b', 'tie', 'both_bad'):
        vote(client, token, new_battle(client)['battle_id'], choice)
    arena._ranking_cache['data'] = None
    stats = client.get('/api/leaderboard/stats').json
    assert stats['total_votes'] == 5 and stats['ties'] == 1 and stats['both_bad'] == 1
    assert stats['position_bias']['votes'] == 3
    assert abs(stats['position_bias']['left_win_rate'] - 66.7) < 0.1
    matrix = client.get('/api/leaderboard/matrix?top=5').json
    size = len(matrix['models'])
    assert size >= 2 and len(matrix['cells']) == size and matrix['cells'][0][0] is None
    history = client.get('/api/elo_history?range=all&top=3').json
    assert len(history['series']) == 3
    assert all(p['x'].endswith('Z') for s in history['series'] for p in s['points'])
