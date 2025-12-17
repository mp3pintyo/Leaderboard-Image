# Copilot Instructions for Leaderboard-Image

## Project Overview
Flask-based web app for ranking AI image models via ELO scoring. Supports Arena Battle (blind voting), Side-by-Side, and Leaderboard modes.
- **Core:** `app.py` (Flask), `database.py` (SQLite), `config.py` (Settings/Models).
- **Data:** `data/<prompt_id>/` stores `prompt.txt` and model images.

## Architecture & Patterns
- **Model Config:** Defined in `config.py` (`MODELS` dict). Keys (e.g., `model-001`) are DB IDs. `filename` maps to image files.
- **Image Resolution:** `find_model_file` in `app.py` resolves images by `filename` + `ALLOWED_EXTENSIONS` (.jpg, .png, .webp).
- **Database:** SQLite (`votes.db`). Tables: `votes`, `model_elo`, `elo_history`.
- **ELO System:** Updates `model_elo` and `elo_history` on every vote.
- **Frozen Models:** Bottom `FROZEN_BOTTOM_COUNT` models (config.py) are excluded from Arena Battle but visible in Leaderboard.
- **Frontend:** `templates/index.html` + `static/js/`. API-driven (`/api/*`).

## Developer Workflows
- **Run Dev:** `python app.py` or `flask run --host=0.0.0.0`.
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
- **UI Config:** `REVEAL_DELAY_MS` in `config.py` controls vote reveal timing.
