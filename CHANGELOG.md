# Changelog

Minden jelentős változás ebben a fájlban szerepel. / All notable changes are documented in this file.

## [1.4.0] – 2026-09-30

### 🇭🇺 Magyar

**Tartalom-alapú képkulcsok a Cloudflare R2-n**
- A képek nyilvános URL-je már nem tartalmazza a fájlnevet (pl. `…/001/nanobanana-2-4k.png`), hanem a kép tartalmából képzett kulcsot: `…/img/<git blob sha>`. Így szavazás előtt a böngésző hálózati lapján sem olvasható le egyszerűen a modell neve.
- A képek eredeti méretben és formátumban töltődnek, a helyes `Content-Type`-pal.
- Mivel a kulcs a tartalomtól függ, egy kép cseréjekor új URL keletkezik – ezért a képek egy évig cache-elhetők (`Cache-Control: immutable`), az ismételt megjelenéseknél a böngésző gyorsítótárából jönnek.
- `generate_manifest.py`: a manifest bejegyzései `{"file": ..., "key": "img/<sha>"}` formájúak; a SHA-t a Git fából vagy az indexből veszi (a képeket nem kell letölteni vagy újra hash-elni). A régi (csak fájlnév) formátumot az app továbbra is kezeli.
- `sync_changed_data.py`: a hiányzó kulcsokat a változatlan képeknél **szerveroldali R2 másolással** hozza létre (nincs le- és feltöltés), a változott képeket Gitből tölti fel; párhuzamos végrehajtás, `--dry-run` mód, opcionális `--prune-legacy-images` a régi kulcsok törlésére.
- A GitHub Actions munkafolyamat sorrendje megváltozott: a manifest csak a sikeres R2 szinkron **után** kerül commitolásra, így a deploy-olt app sosem hivatkozik még fel nem töltött képre. Hiba esetén az app a régi URL-eket használja tovább.
- Megjegyzés: a kulcs a tartalom hash-e; aki a nyilvános repó képeinek hash-ét kiszámolja, összepárosíthatja őket. A cél a modell egyszerű leolvashatóságának megszüntetése szavazás közben.

**Dokumentáció**
- Teljesen frissített README: módszertan, konfiguráció, útvonalak, R2 folyamat, tesztek, API, adatbázis, biztonság.
- Frissített fejlesztői útmutató (`.github/copilot-instructions.md`).

### 🇬🇧 English

**Content-addressed image keys on Cloudflare R2**
- Public image URLs no longer contain the file name (e.g. `…/001/nanobanana-2-4k.png`) but a key derived from the image content: `…/img/<git blob sha>`. The model name can no longer be read from the browser's network tab before voting.
- Images are still delivered in their original size and format, with the correct `Content-Type`.
- Because the key depends on the content, replacing an image creates a new URL – so images can be cached for a year (`Cache-Control: immutable`) and repeat appearances come from the browser cache.
- `generate_manifest.py`: manifest entries are `{"file": ..., "key": "img/<sha>"}`; the SHA comes from the Git tree or index (no image download or re-hashing needed). The legacy (file name only) format is still supported by the app.
- `sync_changed_data.py`: missing keys for unchanged images are created with a **server-side R2 copy** (no download/upload), changed images are uploaded from Git; parallel execution, `--dry-run` mode, optional `--prune-legacy-images` to delete legacy keys.
- The GitHub Actions workflow order changed: the manifest is committed only **after** a successful R2 sync, so the deployed app never references an image that is not uploaded yet. On failure the app keeps using the legacy URLs.
- Note: the key is a content hash; someone hashing the images of the public repository could still match them. The goal is that the model is not trivially readable while voting.

**Documentation**
- Fully updated README: methodology, configuration, routes, R2 pipeline, tests, API, database, security.
- Updated developer guide (`.github/copilot-instructions.md`).

## [1.3.0] – 2026-09-30

### 🇭🇺 Magyar

**Navigáció és megosztható linkek**
- Hash-alapú útvonalak minden nézethez: `#/battle`, `#/side-by-side?m1=…&m2=…&p=…`, `#/leaderboard`, `#/leaderboard/quality-price`, `#/leaderboard/matrix`, `#/elo-history`, `#/compare?a=…&b=…`. A nézetek linkelhetők, a böngésző Vissza gombja működik, az oldal címe nézetenként változik.
- Az Arena Battle nézetre visszalépve a korábban látott pár megmarad (nem „ég el” egy új pár).
- Bejelentkezés után az oldal ugyanarra a nézetre (útvonalra) tér vissza.

**Sötét mód**
- Világos / sötét / rendszer szerinti téma a navigációs sávban; a választás megmarad, és villanás nélkül töltődik be.
- Minden felület design tokenekre (CSS változókra) épül; a diagramok (minőség–ár, ELO-történet, összehasonlítás) színei is a témához igazodnak, és témaváltáskor újrarajzolódnak.

**Képnagyító (lightbox)**
- Bármelyik képre (Battle, Side-by-Side, Összehasonlítás) kattintva teljes képernyős nézet nyílik: görgős és csípéses nagyítás a kurzor felé, húzással mozgatás, dupla kattintás (2,5×), `+`/`−`/`0` billentyűk, `←`/`→` lapozás a képek között, eredeti kép megnyitása új lapon.
- A Battle-ben a felirat szavazás előtt csak az oldalt mutatja („A oldali kép”), így a nagyító sem árulja el a modellt.

**Összehasonlítás oldal újratervezve**
- A félrevezető radardiagram helyett egymással szemben álló metrikasávok: Arena (Bradley-Terry) pontszám 95%-os CI-vel, győzelmi arány, meccsek, online ELO; a vezető érték jelölve, adat nélküli modellnél „nincs még adat”.
- Egymás elleni eredmény döntetlenekkel együtt, egy sávban.
- Modell-adatlapok teljes (szolgáltató + név) megjelenítéssel, magyar címkékkel; „⇄” gomb a modellek felcseréléséhez.
- A prompt-sorok billentyűzettel is nyithatók (`aria-expanded`), a képek nagyíthatók; a diagram példánya újratöltéskor megszűnik (nincs memóriaszivárgás).

**Keresőoptimalizálás és megosztás**
- `meta description`, Open Graph és Twitter kártya (1200×630-as megosztási kép), `canonical`, `theme-color`, SVG favicon és Apple touch ikon.

**Biztonság**
- `Content-Security-Policy` fejléc: csak saját és jsDelivr szkriptek futhatnak, a képek a saját szerverről vagy a `DATA_MODE` (R2) címről jöhetnek, `frame-ancestors 'none'`.
- Minden CDN könyvtár fix verzióval és SRI integritás-hash-sel töltődik be: Bootstrap 5.3.8, Chart.js 4.5.1, chartjs-adapter-date-fns 3.0.0 (korábban a Chart.js mindig a legfrissebb, ellenőrizetlen verzióval töltődött).

**Akadálymentesség és apróságok**
- „Ugrás a tartalomra” link, `<main>` tájékozódási pont, jól látható fókuszkeret, `aria-current` a menüben, nyilakkal bejárható leaderboard fülek.
- Side-by-Side: a képek közvetlenül a modellnév alatt kezdődnek; egységesebb gombok.

**Tesztek:** új e2e tesztek a mély linkekre, a Vissza gombra, a témaváltásra, a nagyítóra és a biztonsági fejlécekre.

### 🇬🇧 English

**Navigation and shareable links**
- Hash routes for every view: `#/battle`, `#/side-by-side?m1=…&m2=…&p=…`, `#/leaderboard`, `#/leaderboard/quality-price`, `#/leaderboard/matrix`, `#/elo-history`, `#/compare?a=…&b=…`. Views are linkable, the browser Back button works and the page title follows the view.
- Returning to Arena Battle keeps the pair you were looking at (no wasted battle).
- After login you return to the same view/route.

**Dark mode**
- Light / dark / system theme in the navbar; the choice is remembered and applied without a flash.
- All surfaces use design tokens (CSS variables); charts (quality–price, ELO history, comparison) follow the theme and redraw on theme change.

**Image lightbox**
- Clicking any image (Battle, Side-by-Side, Compare) opens a fullscreen viewer: wheel and pinch zoom towards the cursor, drag to pan, double click (2.5×), `+`/`−`/`0` keys, `←`/`→` to switch images, open original in a new tab.
- In Battle the caption only shows the side ("A oldali kép") before voting, so the viewer never reveals the model.

**Compare page redesigned**
- The misleading radar chart is replaced by opposing metric bars: Arena (Bradley-Terry) score with 95% CI, win rate, matches, online ELO; the leading value is marked, models without data show "no data yet".
- Head-to-head result including ties in a single bar.
- Model cards with full (provider + name) display names and Hungarian tag labels; "⇄" button to swap models.
- Prompt rows are keyboard accessible (`aria-expanded`), images are zoomable; chart instances are destroyed on reload (no memory leak).

**SEO and sharing**
- `meta description`, Open Graph and Twitter card (1200×630 share image), `canonical`, `theme-color`, SVG favicon and Apple touch icon.

**Security**
- `Content-Security-Policy` header: only own and jsDelivr scripts, images only from self or the `DATA_MODE` (R2) origin, `frame-ancestors 'none'`.
- All CDN libraries are pinned with SRI integrity hashes: Bootstrap 5.3.8, Chart.js 4.5.1, chartjs-adapter-date-fns 3.0.0 (previously Chart.js always loaded the latest, unverified version).

**Accessibility and polish**
- "Skip to content" link, `<main>` landmark, visible focus outline, `aria-current` in the menu, arrow-key navigation for leaderboard tabs.
- Side-by-Side: images start right below the model name; more consistent buttons.

**Tests:** new e2e tests for deep links, the Back button, theme switching, the lightbox and security headers.

## [1.2.0] – 2026-09-30

### 🇭🇺 Magyar

**Bradley-Terry rangsor**
- A leaderboard mostantól **Bradley-Terry** modellel rangsorol (mint az LMArena, az Artificial Analysis és a GenAI-Arena): az összes szavazatra egyszerre illesztett maximum likelihood becslés ELO-skálán, így az eredmény nem függ a szavazatok sorrendjétől és a K-faktortól. Az online ELO megmaradt (ELO-történet grafikon, opcionális oszlop).
- **95%-os konfidenciaintervallum** 100-szoros bootstrap újramintavételezésből, a táblázatban `+x / −y` formában és kis intervallumsávval.
- **Helyezéssáv** (pl. `2–5`): ha két modell intervalluma átfed, a sorrendjük nem biztos.
- **Szavazatszám** oszlop és **„Előzetes”** jelvény 30 meccs alatt (`PRELIMINARY_MATCH_THRESHOLD`).
- A döntetlen és a „mindkettő rossz” fél győzelemnek számít; a kevés adatú modelleket egy kis prior az átlag felé húzza (`BT_PRIOR_GAMES`).
- Gyors: 10 000 szavazat + 100 bootstrap kör ~0,2 s, 30 másodperces gyorsítótárral.

**Új nézetek és statisztikák**
- **Párharc-mátrix** (új leaderboard fül): tényleges győzelmi arány, meccsszám és a BT alapján várt arány a top 8–20 modell között, színezett hőtérképként.
- **Módszertan panel**: a számítás leírása, összesítők (szavazatok, döntetlenek, „mindkettő rossz”) és az **oldaltorzítás mérése** – a bal oldali kép nyerési aránya 95%-os Wilson-intervallummal.
- **Saját toplista** csak 30 saját szavazat után nyílik meg (`PERSONAL_LEADERBOARD_MIN_VOTES`), addig haladásjelző mutatja, mennyi van még hátra; a számítás szintén Bradley-Terry.

**Leaderboard felület**
- Minden oszlop szerint **rendezhető** táblázat (`aria-sort`), **kereső** modell- és szolgáltatónévre, **szolgáltató-szűrő**, „Előzetesek elrejtése” kapcsoló.
- Új opcionális oszlopok: *Gy / D / V* (győzelem / döntetlen / vereség) és *Online ELO*.
- Oszlop megjelenítése/elrejtése, keresés és rendezés nem kér le újra adatot; gyors szűrőváltásnál a régi kérés megszakad (`AbortController`), így nem írhatja felül az újat.
- A Minőség vs. ár diagram a Bradley-Terry pontszámot használja.
- Mobilon kompakt, háromoszlopos nézetváltó.

**ELO fejlődés grafikon**
- Új `/api/elo_history` végpont szerveroldali ritkítással és időszűréssel: a válasz ~900 KB helyett ~10 KB, és nem nő a szavazatok számával.
- Valódi időtengely (a korábbi, minden szavazatot külön címkének vevő kategóriatengely helyett), új 1 hónap / 3 hónap szűrők.
- Alapértelmezés: Top 10 modell (1–30 állítható), 20 jól megkülönböztethető szín, kiemelés a jelmagyarázat fölé húzott egérrel.

**Összehasonlítás API:** a `/api/compare_stats` válasza tartalmazza a Bradley-Terry pontszámot és a konfidenciaintervallumot.

**Függőség:** új Python függőség a `numpy`.

### 🇬🇧 English

**Bradley-Terry ranking**
- The leaderboard now ranks with a **Bradley-Terry** model (like LMArena, Artificial Analysis and GenAI-Arena): a maximum-likelihood fit over all votes at once on an ELO-like scale, independent of vote order and K-factor. Online ELO is kept (ELO history chart, optional column).
- **95% confidence intervals** from 100 bootstrap resamples, shown as `+x / −y` with a small interval bar.
- **Rank spread** (e.g. `2–5`): overlapping intervals mean the order is not certain.
- **Vote count** column and a **"Preliminary"** badge below 30 matches (`PRELIMINARY_MATCH_THRESHOLD`).
- Ties and "both bad" count as half a win; a small prior shrinks low-data models towards the mean (`BT_PRIOR_GAMES`).
- Fast: 10,000 votes + 100 bootstrap rounds in ~0.2 s, cached for 30 seconds.

**New views and statistics**
- **Head-to-head matrix** (new leaderboard tab): actual win rate, match counts and BT-expected win rate among the top 8–20 models as a coloured heatmap.
- **Methodology panel**: explanation, totals (votes, ties, "both bad") and **position-bias measurement** – the left image's win rate with a 95% Wilson interval.
- **Personal leaderboard** unlocks after 30 own votes (`PERSONAL_LEADERBOARD_MIN_VOTES`) with a progress bar until then; it also uses Bradley-Terry.

**Leaderboard UI**
- **Sortable** columns (`aria-sort`), **search** by model/provider name, **provider filter**, "Hide preliminary" switch.
- New optional columns: *W / T / L* (wins / ties / losses) and *Online ELO*.
- Toggling columns, searching and sorting no longer refetch data; quick filter changes abort stale requests (`AbortController`).
- The Quality vs. Price chart uses the Bradley-Terry score.
- Compact three-column view switcher on mobile.

**ELO history chart**
- New `/api/elo_history` endpoint with server-side downsampling and time filtering: ~10 KB instead of ~900 KB, independent of the number of votes.
- Real time axis (instead of a category axis with one label per vote), new 1 month / 3 months filters.
- Default Top 10 models (adjustable 1–30), 20 distinguishable colours, highlight on legend hover.

**Compare API:** `/api/compare_stats` now includes the Bradley-Terry score and confidence interval.

**Dependency:** new Python dependency `numpy`.

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
