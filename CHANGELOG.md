# Changelog

Minden jelentős változás ebben a fájlban szerepel. / All notable changes are documented in this file.

## [1.1.0] – 2026-09-30

### 🇭🇺 Magyar

**Szavazat-integritás és biztonság**
- A kiadott battle-ök szerveroldali táblába kerültek (`battles`), a kliens csak egy véletlen `battle_id`-t kap. Egy battle-re pontosan egyszer lehet szavazni; a régi session cookie visszajátszása már nem ad újabb szavazatot.
- Szavazás előtt a válasz nem tartalmazza a modellek nevét: a kiléte csak szavazás vagy kihagyás után derül ki.
- Minimális nézési idő szavazás előtt (`MIN_VOTE_DELAY_MS`), napi szavazatlimit felhasználónként (`DAILY_VOTE_LIMIT`), percenkénti korlát az új battle-ök kérésére.
- Egy sessionhöz legfeljebb `MAX_OPEN_BATTLES` nyitott battle tartozhat, a battle-ök egy óra után lejárnak.
- Biztonsági HTTP fejlécek (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`), az API válaszok nem cache-elhetők.
- Megszakított vagy hibás OAuth bejelentkezés 500-as hiba helyett barátságos üzenettel tér vissza; bejelentkezés után az oldal ugyanarra a nézetre tér vissza. GitHub-nál csak ellenőrzött e-mail cím kerül mentésre.

**Szavazás és párosítás**
- Négy szavazati lehetőség: *A a jobb*, *B a jobb*, *Döntetlen*, *Mindkettő rossz* – plusz *Kihagyás*. A döntetlen és a „mindkettő rossz” fél győzelemnek számít az ELO-ban, és külön rögzítődik.
- Minden szavazatnál naplózzuk, melyik modell volt a bal oldalon (az oldaltorzítás későbbi méréséhez).
- Okosabb párosítás: a ritkán látott modellpárok nagyobb eséllyel kerülnek elő (súly: 1 / (1 + eddigi meccsek)), az új modellek boostja megmaradt. Csak olyan pár és prompt kerül kiválasztásra, amelyhez mindkét modellnek van képe.

**Arena Battle felület**
- Új elrendezés: szavazás után zöld keret és ✓ a győztesen, animált ELO-változás (+/−) mindkét modellnél, mai szavazatszámláló.
- A következő pár (és a képei) már az eredmény mutatása alatt letöltődik, így a váltás azonnali.
- Billentyűparancsok a felületen jelölve: `1`/`←` A, `2`/`→` B, `0` döntetlen, `X` mindkettő rossz, `S` kihagyás.
- A bejelentkezést kérő sávban közvetlen belépő gombok vannak.
- Blokkoló `alert()` ablakok helyett értesítések (toast); a betöltésjelző vékony sáv, nem tolja el a tartalmat; mobilon `100dvh` magasság.

**Teljesítmény**
- SQLite WAL mód és új indexek (`votes(prompt_id)`, `votes(user_id, voted_at)`, `votes(winner, loser)`).
- Az összehasonlító statisztika promptonkénti 4 lekérdezés helyett modellenként egyetlen `GROUP BY` lekérdezéssel készül; a prompt-szövegek és a képelérhetőség gyorsítótárazva.
- Side-by-Side: egyetlen API hívás tölti be a promptot és a képeket (előtöltéssel, villogás nélkül), és csak olyan promptot választ, amelyhez minden kiválasztott modellnek van képe.

**Hibajavítások**
- A `REVEAL_DELAY_MS` beállítás hatástalan volt (mindig 1500 ms-mal futott) – javítva.
- A Döntetlen gomb nem rögzített semmit, és dupla kattintással két párhuzamos betöltést indított – javítva.
- Egységes ISO 8601 UTC időbélyegek; a régi adatok migrációval át lettek alakítva (a Python 3.12-ben elavult sqlite datetime adapter már nincs használva).
- Az ELO frissítés írási zárral (`BEGIN IMMEDIATE`) fut, így párhuzamos szavazatoknál sem vész el frissítés.
- A befagyasztott modellek listája szavazás után is frissül, nem csak induláskor.
- A modelllista beágyazása a sablonba biztonságos JSON blokkal történik (idézőjel a névben nem töri el az oldalt).
- A `/api/get_image` ismeretlen prompt esetén nem olvassa újra a könyvtárat.
- A saját toplistából hiányzó mezők pótolva; a `python app.py reset-votes` parancs újra működik.
- `print` helyett `logging`, egységes magyar hibaüzenetek, hibakódok (`code`) az API válaszokban.

**Tesztek**
- Új backend tesztcsomag (`pytest`): szavazási folyamat, visszajátszás, idegen session, túl gyors szavazat, napi limit, döntetlenek, kihagyás, korlátozás, időbélyegek.
- Új e2e teszt az anonim battle folyamatra; az e2e tesztek ideiglenes adatbázist használnak.

**Adatbázis migráció:** automatikus induláskor (`PRAGMA user_version` = 1). Új tábla: `battles`; új oszlopok a `votes` táblában: `outcome`, `left_model`, `battle_id`.

### 🇬🇧 English

**Vote integrity and security**
- Issued battles are stored server-side (`battles` table); the client only receives a random `battle_id`. Each battle can be voted on exactly once; replaying an old session cookie no longer yields extra votes.
- Model names are no longer sent before voting; identities are revealed only after a vote or skip.
- Minimum viewing time before voting (`MIN_VOTE_DELAY_MS`), per-user daily vote limit (`DAILY_VOTE_LIMIT`), per-minute rate limit for requesting new battles.
- At most `MAX_OPEN_BATTLES` open battles per session; battles expire after one hour.
- Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`); API responses are `no-store`.
- Cancelled/failed OAuth logins return a friendly message instead of HTTP 500; after login the user returns to the same view. Only verified GitHub e-mail addresses are stored.

**Voting and pairing**
- Four vote options: *A is better*, *B is better*, *Tie*, *Both bad* – plus *Skip*. Ties and "both bad" count as half a win in ELO and are stored separately.
- Every vote records which model was on the left (to measure position bias).
- Smarter pairing: rarely seen model pairs are sampled more often (weight 1 / (1 + previous matches)); the new-model boost is kept. Only pairs/prompts where both models have an image are chosen.

**Arena Battle UI**
- New layout: after voting the winner gets a green frame and ✓, animated ELO change (+/−) for both models, daily vote counter.
- The next pair (and its images) is prefetched while the result is shown, so switching is instant.
- Keyboard shortcuts shown in the UI: `1`/`←` A, `2`/`→` B, `0` tie, `X` both bad, `S` skip.
- The login prompt contains direct login buttons.
- Non-blocking toast notifications instead of `alert()`; a thin loading bar that does not shift the layout; `100dvh` height on mobile.

**Performance**
- SQLite WAL mode and new indexes (`votes(prompt_id)`, `votes(user_id, voted_at)`, `votes(winner, loser)`).
- Comparison stats use one `GROUP BY` query per model instead of 4 queries per prompt; prompt texts and image availability are cached.
- Side-by-Side loads the prompt and all images with a single API call (with preloading, no flicker) and only picks prompts that have images for every selected model.

**Bug fixes**
- `REVEAL_DELAY_MS` had no effect (always 1500 ms) – fixed.
- The Tie button recorded nothing and a double click started two parallel loads – fixed.
- Consistent ISO 8601 UTC timestamps; existing data is migrated (the sqlite datetime adapter deprecated in Python 3.12 is no longer used).
- ELO updates run under a write lock (`BEGIN IMMEDIATE`), so concurrent votes cannot lose updates.
- Frozen models are refreshed after votes, not only at startup.
- The model list is embedded via a safe JSON block (quotes in names no longer break the page).
- `/api/get_image` no longer rescans the data directory for unknown prompts.
- Missing fields in the personal leaderboard added; `python app.py reset-votes` works again.
- `logging` instead of `print`, consistent Hungarian error messages, machine-readable error `code` in API responses.

**Tests**
- New backend test suite (`pytest`): vote flow, replay, foreign session, too-fast vote, daily limit, draws, skip, rate limiting, timestamps.
- New e2e test for the anonymous battle flow; e2e tests use a temporary database.

**Database migration:** runs automatically on startup (`PRAGMA user_version` = 1). New table: `battles`; new `votes` columns: `outcome`, `left_model`, `battle_id`.
