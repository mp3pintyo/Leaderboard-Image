# Képgenerátor Aréna

![AI képgenerátorok összehasonlítása](docs/images/arena-battle.png)

## 🚀 Áttekintés

A Képgenerátor Aréna egy web-alapú alkalmazás, amely lehetővé teszi különböző AI képgenerátorok által létrehozott képek összehasonlítását és értékelését. A rendszer négy fő módot kínál:

- **Arena Battle:** Két kép közvetlen összehasonlítása, ahol a felhasználók a jobbnak ítélt képre szavazhatnak
- **Side-by-Side:** Két kiválasztott modell képeinek összehasonlítása egymás mellett
- **Leaderboard:** A modellek ranglistája az ELO pontszámok és egyéb statisztikák alapján
- **ELO Fejlődés:** Grafikon, amely az egyes modellek ELO pontszámának időbeli változását mutatja

## ✨ Funkciók

- 🏆 **ELO Rating:** Fejlett pontrendszer, amely figyelembe veszi az ellenfelek erősségét
- 🖼️ **Több formátum támogatása:** JPG, JPEG, PNG és WEBP
- ⚙️ **Konfigurálhatóság:** Modellek, fájlformátumok és alapbeállítások külön konfigurációs fájlban
- 👁️‍🗨️ **Vak szavazás:** Arena Battle módban a modellek nevei csak a szavazás után jelennek meg
- 📊 **Részletes statisztikák:** ELO pontszámok, győzelmek, mérkőzések száma és győzelmi arányok
- 🔍 **Modell típus szűrés:** Leaderboard nézeten szűrhetők a modellek open source/zárt forrás szerint

## 🛠️ Telepítés

### Követelmények

- Python 3.6+
- pip (Python csomagkezelő)
- Git (opcionális)

### Telepítési lépések

```bash
# 1. Klónozd vagy töltsd le a repository-t
git clone https://github.com/yourusername/image-leaderboard.git
cd image-leaderboard

# 2. Függőségek telepítése
pip install -r requirements.txt

# 3. Adatbázis inicializálása
python database.py

# 4. Alkalmazás indítása
flask run --host=0.0.0.0

# Az alkalmazás alapértelmezetten a következő címen érhető el:
# http://localhost:5000
```

## 📋 Használat

### 1. Arena Battle

Az Arena Battle a rendszer fő módja, ahol két véletlenszerűen kiválasztott modell által generált kép jelenik meg egymás mellett. A felhasználók kiválaszthatják, melyik kép tetszik jobban, vagy döntetlen/kihagyás opciót választhatnak.

A modellek nevei csak a szavazás után jelennek meg, így biztosítva az elfogulatlan értékelést.

### 2. Side-by-Side

A Side-by-Side módban a felhasználók maguk választhatják ki, melyik két modellt szeretnék összehasonlítani. Ez a mód elsősorban vizuális összehasonlításra szolgál, nincs szavazás.

### 3. Leaderboard

A Leaderboard a modellek ranglistáját mutatja ELO pontszám szerint csökkenő sorrendben. A táblázat tartalmazza az ELO értékeket, a győzelmek számát, az összes mérkőzés számát és a győzelmi arányt.

![Leaderboard](docs/images/leaderboard.png)

### 4. ELO Fejlődés

Az ELO Fejlődés nézet egy interaktív vonaldiagramot kínál, amely megjeleníti a modellek ELO pontszámának változását az idő múlásával. Ez lehetővé teszi a felhasználók számára, hogy nyomon kövessék, hogyan teljesítenek a modellek hosszabb időtávon.

Főbb jellemzők:
- Minden modellhez külön színezett vonal
- Interaktív információs dobozok a pontos értékek megjelenítésére
- Időalapú x-tengely a fejlődés kronológiai nyomon követéséhez
- Frissítési lehetőség a legfrissebb adatok betöltéséhez
- Új interaktív funkció: ha az egeret lenyomva tartjuk a legendában egy modell nevére vagy jelölőjére, a többi modell grafikonja és jelölői 10%-os átlátszóságúvá halványulnak, felengedéskor visszaáll az eredeti állapot

![ELO Fejlődés](docs/images/elo-history.png)

## ⚙️ Parancssori funkciók

### Szavazatok resetelése

```bash
python app.py reset-votes
```

Ez a parancs törli az összes eddigi szavazatot és visszaállítja az ELO pontszámokat az alapértelmezett értékre. Ezt akkor érdemes használni, ha:
- Teljesen új versenyt akarsz indítani
- Tesztadatok után szeretnéd az éles adatgyűjtést elkezdeni
- Problémás szavazatok kerültek a rendszerbe

**Fontos:** A parancs az `elo_history` tábla tartalmát is törli, így a grafikon is tiszta lappal indul újra. Az ELO fejlődés grafikonon minden modell újra az alapértelmezett ELO pontszámról (1500) fog indulni.


## 📁 Rugalmas fájlkezelés

A rendszer képes rugalmasan kezelni a képfájlok kiterjesztéseit. Ez azt jelenti, hogy:

- ✅ Ugyanazon modell képei különböző kiterjesztésekkel szerepelhetnek különböző prompt mappákban
- ✅ Támogatott kiterjesztések: `.jpg`, `.jpeg`, `.png`, `.webp`
- ⚠️ A fájlnév alaprésze (kiterjesztés nélkül) mindig meg kell hogy egyezzen a konfigurációban beállítottal

Példa konfiguráció:
```python
# Modell nevek és a hozzájuk tartozó adatok
# Minden modell egy szótár, ami tartalmazza:
# - 'filename': A fájlnév alaprésze kiterjesztés nélkül
# - 'open_source': Boolean érték, True ha letölthető/open source modell, False ha zárt/nem letölthető
MODELS = {
    'model-001': {'name': 'Grok', 'filename': 'grok', 'open_source': False},
    'model-002': {'name': 'Google Gemini Flash 2.0', 'filename': 'gemini-flash', 'open_source': False},
    'model-003': {'name': 'Google Imagen 3', 'filename': 'imagen3', 'open_source': False},
    # ... további modellek a config.py alapján ...
}
```

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

## 🗄️ Adatbázis struktúra

A rendszer három fő táblát használ:

1.  **votes** - A felhasználói szavazatok tárolására
    ```sql
    CREATE TABLE votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt_id TEXT NOT NULL,
        winner TEXT NOT NULL, -- Modell azonosító (pl. 'model-001')
        loser TEXT NOT NULL,  -- Modell azonosító (pl. 'model-002')
        voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```

2.  **model_elo** - A modellek aktuális ELO pontszámainak tárolására
    ```sql
    CREATE TABLE model_elo (
        model TEXT PRIMARY KEY, -- Modell azonosító (pl. 'model-001')
        elo REAL NOT NULL,
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```

3.  **elo_history** - Az ELO pontszámok változásának történeti nyomon követésére
    ```sql
    CREATE TABLE elo_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        model TEXT NOT NULL, -- Modell azonosító (pl. 'model-001')
        elo REAL NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ```

## 🔌 API végpontok

A rendszer a következő API végpontokat biztosítja:

| Végpont                                 | Metódus | Leírás                                                                                                                               |
| --------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `/`                                     | GET     | A főoldal megjelenítése.                                                                                                             |
| `/images/<prompt_id>/<filename>`        | GET     | Képfájlok kiszolgálása a `data` mappából.                                                                                            |
| `/api/battle_data`                      | GET     | Adatokat ad vissza az Arena Battle módhoz (prompt, két véletlenszerű modell képei és nevei).                                          |
| `/api/side_by_side_data`                | GET     | Adatokat ad vissza a Side-by-Side módhoz (prompt, két kiválasztott modell képei és nevei).                                            |
| `/api/get_image`                        | GET     | Visszaadja egy adott modell képének URL-jét egy adott prompt ID-hoz (Side-by-Side módhoz használt).                                   |
| `/api/vote`                             | POST    | Rögzíti a felhasználó szavazatát (győztes, vesztes) és frissíti az ELO értékeket.                                                      |
| `/api/leaderboard`                      | GET     | Visszaadja az aktuális Leaderboard adatokat (modellek neve, ELO, győzelmek, meccsek, győzelmi arány, open source státusz).             |
| `/api/elo_history`                      | GET     | (Elavult lehet) Visszaadja az ELO értékek időbeli változásait a modellek grafikonos megjelenítéséhez.                                  |
| `/api/elo_history_with_current_elo`     | GET     | Visszaadja az ELO értékek időbeli változásait (`history`) és az aktuális ELO pontszámokat (`current_elos`) a grafikonhoz és szűréshez. |
| `/api/prompt_ids`                       | GET     | Visszaadja az összes elérhető prompt ID-t.                                                                                           |
| `/api/prompt_text`                      | GET     | Visszaadja a prompt szövegét egy adott prompt_id-hoz.                                                                                |

## 📝 Licenc

[MIT](LICENSE)

## 📚 További dokumentáció

A részletes dokumentáció a `docs/index.html` fájlban található.