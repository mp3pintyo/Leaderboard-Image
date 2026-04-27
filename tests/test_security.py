import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class SecurityRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_path = os.path.join(tempfile.gettempdir(), 'leaderboard-image-security-tests.db')
        if os.path.exists(cls.database_path):
            os.remove(cls.database_path)

        os.environ['FLASK_DEBUG'] = '1'
        os.environ['DATABASE_PATH'] = cls.database_path
        os.environ.pop('SECRET_KEY', None)

        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))

        sys.modules.pop('app', None)
        import app as app_module

        cls.app_module = app_module
        cls.client = app_module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.database_path):
            os.remove(cls.database_path)

    def setUp(self):
        with self.client.session_transaction() as sess:
            sess.clear()
            sess['user'] = {'id': 1, 'name': 'Tester', 'provider': 'dev'}

    def test_battle_data_stores_pending_battle_in_session(self):
        response = self.client.get('/api/battle_data')
        self.assertEqual(response.status_code, 200)
        battle_data = response.get_json()

        with self.client.session_transaction() as sess:
            self.assertEqual(sess['pending_battle']['prompt_id'], battle_data['prompt_id'])
            self.assertEqual(
                sess['pending_battle']['models'],
                sorted([battle_data['model1']['id'], battle_data['model2']['id']])
            )

    def test_vote_rejects_replay_and_invalid_model_pair(self):
        response = self.client.get('/api/battle_data')
        self.assertEqual(response.status_code, 200)
        battle_data = response.get_json()

        valid_payload = {
            'prompt_id': battle_data['prompt_id'],
            'winner': battle_data['model1']['id'],
            'loser': battle_data['model2']['id'],
        }
        valid_vote = self.client.post('/api/vote', json=valid_payload)
        self.assertEqual(valid_vote.status_code, 200)

        replay_vote = self.client.post('/api/vote', json=valid_payload)
        self.assertEqual(replay_vote.status_code, 400)
        self.assertEqual(replay_vote.get_json()['error'], 'Invalid or expired battle state')

        second_battle = self.client.get('/api/battle_data')
        self.assertEqual(second_battle.status_code, 200)
        second_data = second_battle.get_json()
        forged_vote = self.client.post('/api/vote', json={
            'prompt_id': second_data['prompt_id'],
            'winner': second_data['model1']['id'],
            'loser': second_data['model1']['id'],
        })
        self.assertEqual(forged_vote.status_code, 400)
        self.assertEqual(forged_vote.get_json()['error'], 'Winner and loser must be different models')

        third_battle = self.client.get('/api/battle_data')
        self.assertEqual(third_battle.status_code, 200)
        third_data = third_battle.get_json()
        wrong_models_vote = self.client.post('/api/vote', json={
            'prompt_id': third_data['prompt_id'],
            'winner': valid_payload['winner'],
            'loser': valid_payload['loser'],
        })
        self.assertEqual(wrong_models_vote.status_code, 400)
        self.assertEqual(wrong_models_vote.get_json()['error'], 'Invalid or expired battle state')

    def test_production_mode_requires_explicit_secret_key(self):
        result = subprocess.run(
            [sys.executable, '-c', 'import app'],
            cwd=REPO_ROOT,
            env={
                **os.environ,
                'PYTHONPATH': str(REPO_ROOT),
                'FLASK_DEBUG': '0',
                'FLASK_ENV': '',
                'SECRET_KEY': '',
                'DATABASE_PATH': os.path.join(tempfile.gettempdir(), 'leaderboard-image-prod-check.db'),
            },
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SECRET_KEY environment variable must be set', result.stderr)


if __name__ == '__main__':
    unittest.main()
