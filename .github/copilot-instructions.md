# Copilot Instructions for Leaderboard-Image

## Project Overview
Flask-based web app for ranking AI image models via ELO scoring. Supports Arena Battle (blind voting), Side-by-Side, and Leaderboard modes.
- **Core:** `app.py` (Flask), `database.py` (SQLite + migrations), `ranking.py` (Bradley-Terry + bootstrap CI, numpy), `config.py` (Settings/Models).
- **Data:** `data/<prompt_id>/` stores `prompt.txt` and model images.

## Architecture & Patterns
- **Model Config:** Defined in `config.py` (`MODELS` dict). Keys (e.g., `model-001`) are DB IDs. `filename` maps to image files.
- **Image Resolution:** `find_model_file` in `app.py` resolves images by `filename` + `ALLOWED_EXTENSIONS` (.jpg, .png, .webp).
- **Database:** SQLite (`votes.db`, WAL). Tables: `votes` (with `outcome`, `left_model`, `battle_id`), `battles`, `model_elo`, `elo_history`, `users`. Schema version in `PRAGMA user_version`; add new migrations to `MIGRATIONS` in `database.py`. Timestamps are ISO 8601 UTC (`utc_now_iso()`).
- **Ranking:** The leaderboard uses Bradley-Terry (`get_global_ranking`, cached). Online ELO still updates `model_elo`/`elo_history` on every vote (history chart, frozen models). Ties/both-bad = 0.5.
- **Battles:** `/api/battle_data` issues a server-side battle (no model names); `/api/vote` takes `{battle_id, choice}`; `/api/battle/skip` reveals. Never send model identities before the vote.
- **Frozen Models:** Bottom `FROZEN_BOTTOM_COUNT` models (config.py) are excluded from Arena Battle but visible in Leaderboard.
- **Frontend:** `templates/index.html` + `static/js/` ES modules, hash router in `main.js` (`#/battle`, `#/leaderboard/matrix`, `#/compare?a=&b=` …). Config via `#app-config` JSON block. Use `requestJson`/`fetchData` (api.js) and `showToast` (no `alert`). Theme tokens in `static/css/style.css` (light/dark).

## Developer Workflows
- **Run Dev:** `python app.py` (debug + Dev Login) or `flask run --host=0.0.0.0` (needs `SECRET_KEY`).
- **Tests:** `python -m pytest tests` (backend), `npm test` (Playwright e2e, temp DB).
- **Reset Data:** `python app.py reset-votes` (Clears votes, history, resets ELO).
- **Init DB:** `python database.py` (Auto-runs on app start).
- **Add Model:**
  1. Add to `MODELS` in `config.py`.
  2. Add images to ALL `data/<prompt_id>/` folders matching `filename`.
- **Add Prompt:** Create `data/<id>/` with `prompt.txt` and images.

## Key Conventions
- **File Serving:** Use `send_from_directory` for security.
- **Prompt Caching:** `AVAILABLE_PROMPTS` cached in `app.py`. Refreshes on debug reload or restart.
- **Maintenance:** Use scripts in `fix/` for manual DB corrections (e.g., fixing IDs).
- **Docs:** Keep `docs/index.html` and `README.md` updated with new models/features.

## Common Tasks
- **Fixing ELO:** If IDs change, use `fix/` scripts or SQL to migrate data.
- **UI Config:** `REVEAL_DELAY_MS` in `config.py` controls vote reveal timing; anti-abuse limits (`MIN_VOTE_DELAY_MS`, `DAILY_VOTE_LIMIT`, …) and BT settings are also in `config.py`.
- **Images on R2:** `DATA_MODE` serves images via content-addressed keys from `data/manifest.json` (`img/<git blob sha>`), generated and synced by CI (`generate_manifest.py`, `sync_changed_data.py`).
- **Changelog:** Add a bilingual (HU/EN) entry to `CHANGELOG.md` for every release.
