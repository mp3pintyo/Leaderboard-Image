# Képgenerátor Aréna

![AI képgenerátorok összehasonlítása](docs/images/arena-battle.png)

## 🚀 Áttekintés

A Képgenerátor Aréna egy webalkalmazás, amelyben AI képgenerátorok ugyanarra a promptra készült képeit lehet vakon összehasonlítani és rangsorolni. Öt nézete van:

- **Arena Battle:** két névtelen kép ugyanarra a promptra; a látogató szavaz (*A a jobb*, *B a jobb*, *Döntetlen*, *Mindkettő rossz* vagy *Kihagyás*), a modellek neve csak utána derül ki.
- **Side-by-Side:** 2–3 kiválasztott modell képei egymás mellett, promptonként lapozva.
- **Leaderboard:** Bradley-Terry rangsor 95%-os konfidenciaintervallummal, minőség–ár térkép és párharc-mátrix.
- **ELO fejlődés:** az online ELO időbeli alakulása a top modelleknél.
- **Összehasonlítás:** két modell adatlapja, pontszáma, egymás elleni eredménye és promptonkénti képei.

Minden nézet saját, megosztható linket kap (lásd [Útvonalak](#-útvonalak-megosztható-linkek)).

## ✨ Funkciók

- 🏆 **Bradley-Terry rangsor:** az összes szavazatra illesztett maximum likelihood becslés (mint az LMArena-n), bootstrap konfidenciaintervallummal, helyezéssávval és „Előzetes” jelöléssel a kevés adatú modelleknél.
- 🔒 **Manipuláció elleni védelem:** szerveroldali, egyszer felhasználható battle-ök; a modellek neve és a képfájl neve sem látszik szavazás előtt; minimális nézési idő, napi szavazatlimit és kéréskorlát.
- 🎯 **Célzott párosítás:** a legtöbb információt adó párok (közeli pontszám, bizonytalan helyezés), a ritkán látott párok és az új modellek gyakrabban kerülnek elő; csak olyan pár és prompt jön, amelyhez mindkét modellnek van képe.
- ⚖️ **Oldaltorzítás mérése:** minden szavazatnál rögzül, melyik modell volt balra; a leaderboard módszertani paneljén látszik a bal oldal nyerési aránya.
- 🧮 **Párharc-mátrix:** tényleges és várt győzelmi arány, meccsszám a top modellek között.
- 👤 **Saját toplista:** 30 saját szavazat után a saját ízlésed szerinti rangsor.
- 🔍 **Képnagyító:** teljes képernyő, görgős/csípéses nagyítás, húzás, lapozás.
- 🌗 **Sötét mód**, billentyűparancsok, akadálymentes vezérlők, mobilbarát elrendezés.
- 🖼️ **Több formátum:** JPG, JPEG, PNG és WEBP – a képek eredeti méretben és formátumban töltődnek.

## 🛠️ Telepítés

### Követelmények

- Python 3.10+
- pip
- (opcionális) Node.js a Playwright e2e tesztekhez

### Lépések

```bash
git clone https://github.com/mp3pintyo/Leaderboard-Image.git
cd Leaderboard-Image
pip install -r requirements.txt

# Fejlesztői indítás (debug mód, „Dev Login” bejelentkezéssel)
python app.py
# → http://localhost:5000
```

Az adatbázis és a sémamigrációk induláskor automatikusan létrejönnek/lefutnak.

### Környezeti változók

| Változó | Leírás |
| --- | --- |
| `SECRET_KEY` | **Kötelező éles környezetben** (a session és a CSRF aláírásához). |
| `DATABASE_PATH` | Az SQLite adatbázis helye (Renderen pl. `/var/data/votes.db` Persistent Diskkel). |
| `DATA_MODE` | A képek nyilvános alap-URL-je (Cloudflare R2). Ha be van állítva, a képek innen töltődnek a `data/manifest.json` alapján. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google bejelentkezés. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | GitHub bejelentkezés. |
| `WEB_CONCURRENCY`, `PORT` | Gunicorn beállítások (`gunicorn.conf.py`). |

Éles futtatás: `gunicorn app:app` (a `gunicorn.conf.py` automatikusan betöltődik).

## 📋 Használat

### Arena Battle

Két véletlenszerűen párosított modell képe jelenik meg ugyanarra a promptra. Szavazni bejelentkezve lehet.

| Művelet | Gomb | Billentyű |
| --- | --- | --- |
| A bal oldali kép a jobb | *A a jobb* | `1` vagy `←` |
| A jobb oldali kép a jobb | *B a jobb* | `2` vagy `→` |
| Egyformán jók | *Döntetlen* | `0` vagy `T` |
| Egyik sem jó | *Mindkettő rossz* | `X` |
| Új pár szavazat nélkül | *Kihagyás* | `S` |

Szavazás után megjelenik a két modell neve és az ELO-változás, közben már töltődik a következő pár. Bármelyik képre kattintva nagyítható.

### Side-by-Side

Válassz 2–3 modellt; a *Betöltés / Új prompt* véletlen közös promptot tölt be, a *Következő prompt* sorban lapoz. Csak olyan prompt jelenik meg, amelyhez minden kiválasztott modellnek van képe.

### Leaderboard

![Leaderboard](docs/images/leaderboard.png)

- **Rangsor:** pontszám, 95% CI, helyezéssáv, szavazatszám, győzelmi arány. Kereshető, szolgáltató szerint szűrhető, bármely oszlop szerint rendezhető; opcionális oszlopok: Gy/D/V, online ELO, megjelenés, felbontás, árazás, videó.
- **Minőség vs. ár:** pontszám és fix API-ár 1 000 képre, logaritmikus ártengely, Pareto élvonal.
- **Párharcok:** győzelmi arány / meccsszám / várt arány mátrix a top 8–20 modellre.
- **Saját toplista:** 30 saját szavazat után nyílik meg.

### ELO fejlődés

![ELO Fejlődés](docs/images/elo-history.png)

Az online ELO alakulása időtengelyen (1 hét – teljes időszak), a top 1–30 modellre. A jelmagyarázat fölé húzott egérrel egy modell kiemelhető.

### Összehasonlítás

Két modell adatlapja, Arena pontszáma CI-vel, győzelmi aránya, egymás elleni eredménye (döntetlenekkel), promptonkénti győzelmi aránya és – egy promptra kattintva – a két kép egymás mellett.

## 📐 Rangsorolási módszertan

- **Bradley-Terry modell** (`ranking.py`): minden modellnek van egy erőssége; annak esélye, hogy *i* legyőzi *j*-t: `p_i / (p_i + p_j)`. Az erősségeket az összes szavazatra egyszerre illesztjük (Newton-módszer), így – az online ELO-val ellentétben – az eredmény nem függ a szavazatok sorrendjétől. A pontszám ELO-skálán van: `1500 + 400 · log10(p)`.
- **Döntetlen és „mindkettő rossz”:** fél győzelem mindkét félnek.
- **Prior:** minden modell kap `BT_PRIOR_GAMES` virtuális döntetlent egy 1500-as ellenféllel – ez a kevés adatú modelleket az átlag felé húzza.
- **95% CI:** `BT_BOOTSTRAP_ROUNDS` (100) bootstrap újramintavételezés 2,5/97,5 percentilise.
- **Helyezés (#):** sorszám a pontszám szerinti listában. A **helyezéssáv** (tooltipben): legjobb helyezés = 1 + a statisztikailag biztosan jobb modellek száma; legrosszabb = az átfedő vagy jobb intervallumú modellek száma.
- **Célzott párosítás:** a pár súlya `(1 + TARGETED_PAIRING_STRENGTH · információ) / (1 + eddigi meccsek)`, ahol az információ a kimenet bizonytalanságából (közeli pontszám) és a két modell CI-szélességéből adódik.
- **Előzetes:** `PRELIMINARY_MATCH_THRESHOLD` (30) meccs alatt.
- Az **online ELO** (K = 32) továbbra is frissül minden szavazatnál – ez adja az ELO-történet grafikont és a befagyasztási logikát.

## ⚙️ Konfiguráció (`config.py`)

| Beállítás | Alapérték | Jelentés |
| --- | --- | --- |
| `REVEAL_DELAY_MS` | 2000 | Ennyi ideig látszik az eredmény szavazás után. |
| `MIN_VOTE_DELAY_MS` | 1200 | Minimális idő a battle kiadása és a szavazat között. |
| `DAILY_VOTE_LIMIT` | 500 | Napi szavazatlimit felhasználónként (UTC nap). |
| `BATTLE_RATE_LIMIT_PER_MINUTE` | 60 | Új battle-kérések percenként (felhasználó / session). |
| `MAX_OPEN_BATTLES` | 3 | Egyszerre nyitott battle-ök sessionönként (előtöltéshez). |
| `BATTLE_TTL_SECONDS` | 3600 | Ennyi ideig szavazható egy kiadott battle. |
| `NEW_MODEL_BOOST_THRESHOLD` / `_WEIGHT` | 50 / 20 | Új modellek párjainak extra esélye. |
| `TARGETED_PAIRING_STRENGTH` | 3.0 | Célzott párosítás: a közeli pontszámú, bizonytalan modellek párjai gyakrabban jönnek (0 = ki). |
| `FROZEN_BOTTOM_COUNT` | 0 | Az online ELO szerinti alsó N modell kimarad a Battle-ből. |
| `BT_BOOTSTRAP_ROUNDS` | 100 | Bootstrap körök a CI-hez. |
| `BT_PRIOR_GAMES` | 1.0 | Virtuális döntetlenek száma a priorban. |
| `PRELIMINARY_MATCH_THRESHOLD` | 30 | „Előzetes” jelölés határa. |
| `PERSONAL_LEADERBOARD_MIN_VOTES` | 30 | A saját toplista megnyitásához szükséges szavazatok. |

## 🔗 Útvonalak (megosztható linkek)

| Útvonal | Nézet |
| --- | --- |
| `#/battle` | Arena Battle |
| `#/side-by-side?m1=model-001&m2=model-002&m3=…&p=003` | Side-by-Side adott modellekkel és prompttal |
| `#/leaderboard`, `#/leaderboard/quality-price`, `#/leaderboard/matrix` | Leaderboard fülek |
| `#/elo-history` | ELO fejlődés |
| `#/compare?a=model-001&b=model-002` | Két modell összehasonlítása |

## 🖼️ Képek és Cloudflare R2

- Helyi futtatáskor a képek a `data/<prompt_id>/` mappából töltődnek (`/images/<prompt_id>/<fájl>`).
- Éles környezetben (`DATA_MODE`) a képek a Cloudflare R2-ről jönnek, **tartalom-alapú kulccsal**: `img/<git blob sha>`. Így az URL szavazás előtt nem árulja el a modell nevét, és a képek egy évig cache-elhetők (`immutable`). A képek eredeti méretben és formátumban töltődnek le.
- A `main` ágra történő push után a GitHub Actions (`.github/workflows/upload-to-r2.yml`):
  1. a Git fából (a képek letöltése nélkül) legenerálja a `data/manifest.json`-t a kulcsokkal,
  2. a változatlan képeket az R2-n szerveroldalon átmásolja az új kulcsra, a változottakat feltölti (`sync_changed_data.py`, párhuzamosan),
  3. csak ezután commitolja a manifestet – így a deploy-olt app sosem hivatkozik még fel nem töltött képre.
- A régi `<prompt>/<fájl>` kulcsú képek az átállás után is megmaradnak; ha már nincs rájuk szükség, a `python sync_changed_data.py … --prune-legacy-images` törli őket.
- A manifest helyben is generálható: `python generate_manifest.py` (vagy `--git-tree <ref>`).

**Megjegyzés:** a kulcs a kép tartalmából képzett hash. Aki a nyilvános repóból kiszámolja a képek hash-ét, összepárosíthatja őket – a cél az, hogy szavazás közben a modell ne legyen egyszerűen leolvasható, nem a tökéletes titkosság.

## ⚙️ Parancssori funkciók

### Szavazatok resetelése

```bash
python app.py reset-votes
```

Törli az összes szavazatot, battle-t és ELO-előzményt, és minden modellt 1500-ra állít vissza.

## 🧪 Tesztek

```bash
# Backend (pytest): szavazási folyamat, visszajátszás elleni védelem, limitek, rangsor, R2 szinkron terv
python -m pytest tests

# E2E (Playwright, asztali és mobil Chromium; ideiglenes adatbázissal)
npm install
npx playwright install chromium
npm test
```

## 📁 Rugalmas fájlkezelés

- ✅ Ugyanazon modell képei különböző kiterjesztésekkel szerepelhetnek különböző prompt mappákban
- ✅ Támogatott kiterjesztések: `.jpg`, `.jpeg`, `.png`, `.webp`
- ⚠️ A fájlnév alaprésze (kiterjesztés nélkül) meg kell egyezzen a `config.py`-ban megadott `filename` értékkel
- ℹ️ Nem kell minden modellnek minden prompthoz képpel rendelkeznie: a párosítás és a Side-by-Side csak közös promptokat használ

Új modell felvétele: add hozzá a `MODELS` szótárhoz a `config.py`-ban (egyedi `model-XXX` azonosítóval), és tedd a képeit a `data/<prompt_id>/` mappákba a `filename` alapnévvel.

### Modellenkénti YouTube-link

A `config.py` minden modelljénél a `video_url` mező szerkeszthető. Az alapértelmezett érték
`https://www.youtube.com/@pinterzsoltai` (`DEFAULT_VIDEO_URL`). Ha elkészült egy modell videója,
annak `video_url` értékét írd át a videó URL-jére; a hiányzó vagy üres érték az alapértelmezett csatornára mutat.

A Leaderboard **Opcionális oszlopok → Videó** kapcsolója megjeleníti a linkeket;
a választást a böngésző megjegyzi. Az Összehasonlítás modellkártyáin mindig látszik
a link. A szürke **YouTube-csatorna** az alapértelmezett cím, a piros **Egyedi videó**
az átírt cím.

## 🌟 Jelenleg támogatott modellek

- xAI: Grok
- Google: Gemini Flash 2.0
- Google: Imagen 3
- OpenAI: GPT Image 1
- Midjourney v6.1
- Midjourney v7
- Midjourney v7 20250501
- Reve AI: Reve v1
- HiDream-I1
- Lumina-Image-2.0
- ByteDance: Capcut Dreamina Image 2.0 Pro
- Juggernaut XI
- Fluxmania V
- Tengr.ai
- Tengr.ai Quantum
- Adobe: Firefly Image 4
- ByteDance: Seedream 3.0
- Ideogram 3.0
- Piclumen Realistic V2
- F Lite Standard
- Google Gemini Flash 2.0 Preview 0507
- Tencent: Hunyuan Image 2.0
- Google: Imagen 4
- Recraft V3 Raw
- ByteDance: BAGEL
- FLUX.1 Kontext [pro]
- Chroma v34
- Ernie 4.5 Turbo
- Google: Imagen 4 Ultra
- Alibaba: Qwen-Image
- Google Gemini 2.5 Flash Image Preview
- FLUX.1 Krea
- Tencent: Hunyuan Image 2.1
- ByteDance Seedream 4.0 4k
- Kling AI: KOLORS 2.1
- Tencent: HunyuanImage-3.0
- OpenAI: GPT-5 Image Mini High
- OpenAI: GPT-5 Image Mini Low
- OpenAI: GPT-5 Image Mini Medium
- Microsoft: MAI-Image-1
- Google: Nano Banana Pro (Gemini 3 Pro Image)
- Alibaba: Z Image Turbo
- Black Forest Labs: FLUX.2 [pro]
- Black Forest Labs: FLUX.2 [dev]
- Kling AI: Omni Image 1.0
- Black Forest Labs: FLUX.2 [flex]
- ByteDance: Seedream 4.5 4k
- OpenAI: GPT Image 1.5
- Alibaba: Qwen-Image-2512
- Z.ai: GLM-Image
- Black Forest Labs: FLUX.2 [klein base] 9B
- Black Forest Labs: FLUX.2 [klein distilled] 9B
- Black Forest Labs: FLUX.2 [klein base] 4B
- Black Forest Labs: FLUX.2 [klein distilled] 4B
- Alibaba: Z Image Base
- Grok Imagine Image 20260201
- Alibaba: Qwen Image 2.0
- ByteDance: BitDance
- Recraft V4
- ByteDance: Seedream 5.0 lite 3k
- Google: Nano Banana 2 4k
- Adobe: Firefly Image 5 preview
- Tencent: HunyuanImage-3.0 Instruct
- Black Forest Labs: FLUX.2 [max]
- Midjourney: v8 alpha
- Microsoft: MAI-Image-2
- Reve AI: Reve v1.5
- Luma AI: Uni-1
- Alibaba: Wan 2.7-Image Pro 2k
- Midjourney: v8.1 alpha
- Baidu: ERNIE-Image
- Baidu: ERNIE-Image Turbo
- ImagineArt: ImagineArt 2.0
- OpenAI: GPT Image 2 3k
- OpenAI: GPT Image 2 ChatGPT
- Luma AI: Uni-1.1
- Microsoft: Lens
- Krea.ai: Krea 2 Turbo (INT8)
- Luma AI: Uni-1.1 Max
- ByteDance: Seedream 5.0 Pro
- Microsoft: MAI-Image-2.5
- Microsoft: MAI-Image-2.5 Flash
- Microsoft: MAI-Image-2.5 Pro
- Alibaba: Qwen-Image 3.0
- Alibaba: Qwen-Image 3.0 Pro
- Microsoft: MAI-Image-2.6 Preview
- OpenAI: GPT Image 2.5 Sunburst 4k Max
- OpenAI: GPT Image 2.5 Sunburst 1k Low
- Alibaba: Qwen-Image-2.1

## 🗄️ Adatbázis

SQLite, WAL módban. A séma verzióját a `PRAGMA user_version` jelzi; a migrációk induláskor automatikusan lefutnak (`database.py`). Minden időbélyeg ISO 8601 UTC (`2026-09-30T12:34:56.789Z`).

| Tábla | Tartalom |
| --- | --- |
| `votes` | Szavazatok: `prompt_id`, `winner`, `loser`, `outcome` (`win` / `tie` / `both_bad`; döntetlennél winner = bal, loser = jobb), `left_model`, `battle_id`, `user_id`, `voted_at` |
| `battles` | Kiadott battle-ök: `id` (véletlen token), `session_key`, `user_id`, `prompt_id`, `model_a` (bal), `model_b` (jobb), `issued_at`, `resolved_at`, `outcome` |
| `model_elo` | Online ELO modellenként, `frozen` jelzővel |
| `elo_history` | Online ELO minden változása (az ELO-történet grafikonhoz) |
| `users` | OAuth felhasználók (`provider`, `provider_id`, `email`, `name`) |

## 🔌 API végpontok

| Végpont | Metódus | Leírás |
| --- | --- | --- |
| `/api/battle_data` | GET | Új vak battle: `battle_id`, prompt, két kép URL, `vote_delay_ms` (modellnév nélkül). |
| `/api/vote` | POST | Szavazat: `{battle_id, choice: a / b / tie / both_bad}` – bejelentkezés + CSRF token szükséges; a válasz felfedi a modelleket és az ELO-változást. |
| `/api/battle/skip` | POST | Battle kihagyása (CSRF): lezárja a párt és felfedi a modelleket. |
| `/api/side_by_side_data` | GET | `model1`, `model2`, [`model3`] + `prompt_id` / `after` / `previous_prompt_id`. |
| `/api/get_image` | GET | Egy modell képének URL-je egy prompthoz. |
| `/api/leaderboard` | GET | Rangsor (`model_type`: all / open-source / closed-source): `score`, `ci_lower`, `ci_upper`, `position`, `rank`, `rank_worst`, `preliminary`, `matches`, `win_rate`, `elo`, … |
| `/api/leaderboard/mine` | GET | Saját toplista (bejelentkezve): `unlocked`, `vote_count`, `min_votes`, `leaderboard`. |
| `/api/leaderboard/stats` | GET | Összesítők, oldaltorzítás, módszertani paraméterek. |
| `/api/leaderboard/matrix` | GET | Párharc-mátrix a top N modellre (`top`, `model_type`). |
| `/api/elo_history` | GET | Ritkított online ELO-történet (`range`: 1w / 2w / 1m / 3m / all, `top`). |
| `/api/compare_stats` | GET | Két modell statisztikái, egymás elleni és promptonkénti eredmények. |
| `/api/model_info` | GET | Modell-adatlap(ok). |
| `/api/prompt_ids`, `/api/prompt_text` | GET | Promptok listája és szövege. |
| `/api/auth/status` | GET | Bejelentkezési állapot. |

Hibák esetén a válasz `{"error": "...", "code": "..."}` formátumú (pl. `too_fast`, `daily_limit`, `battle_closed`, `login_required`).

## 🔐 Biztonság

- Szerveroldali, egyszer felhasználható battle-ök; a régi session cookie visszajátszása nem ad új szavazatot.
- CSRF token minden állapotváltoztató kéréshez, `HttpOnly` / `SameSite=Lax` (élesben `Secure`) session cookie.
- `Content-Security-Policy`, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` fejlécek.
- CDN könyvtárak fix verzióval és SRI integritás-hash-sel.

## 📝 Változásnapló

Lásd: [CHANGELOG.md](CHANGELOG.md) (magyar / angol).

## 📝 Licenc

[MIT](LICENSE)

## 📚 További dokumentáció

A részletes dokumentáció a `docs/index.html` fájlban található.
