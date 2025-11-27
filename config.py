# Konfigurációs beállítások a képkereső alkalmazáshoz

# Adatbázis fájl neve
DATABASE = 'votes.db'

# Az adatmappák elérési útja
DATA_DIR = 'data'

# Modell nevek és a hozzájuk tartozó adatok
# Minden modell egy szótár, ami tartalmazza:
# - 'filename': A fájlnév alaprésze kiterjesztés nélkül
# - 'open_source': Boolean érték, True ha letölthető/open source modell, False ha zárt/nem letölthető
MODELS = {
    'model-001': {'name': 'Grok', 'filename': 'grok', 'open_source': False},
    'model-002': {'name': 'Google Gemini Flash 2.0', 'filename': 'gemini-flash', 'open_source': False},
    'model-003': {'name': 'Google Imagen 3', 'filename': 'imagen3', 'open_source': False},
    'model-004': {'name': 'GPT Image 1', 'filename': 'gpt-image-1', 'open_source': False},
    'model-005': {'name': 'Midjourney v6.1', 'filename': 'midjourneyv61', 'open_source': False},
    'model-006': {'name': 'Midjourney v7', 'filename': 'midjourneyv7', 'open_source': False},
    'model-007': {'name': 'Reve', 'filename': 'reve', 'open_source': False},
    'model-008': {'name': 'HiDream-I1', 'filename': 'hidreami1', 'open_source': True},
    'model-009': {'name': 'Lumina-Image-2.0', 'filename': 'lumina2', 'open_source': True},
    'model-010': {'name': 'Capcut Dreamina Image 2.0 Pro', 'filename': 'dreamina-image20pro', 'open_source': False},
    'model-011': {'name': 'Juggernaut XI', 'filename': 'juggernautxl', 'open_source': True},
    'model-012': {'name': 'Fluxmania V', 'filename': 'fluxmaniaV', 'open_source': True},
    'model-013': {'name': 'Tengr.ai', 'filename': 'tengrai', 'open_source': False},
    'model-014': {'name': 'Tengr.ai Quantum', 'filename': 'tengrai-q', 'open_source': False},
    'model-015': {'name': 'Adobe Firefly Image 4', 'filename': 'firefly4', 'open_source': False},
    'model-016': {'name': 'Dreamina Seedream 3.0', 'filename': 'dreamina-image3', 'open_source': False},
    'model-017': {'name': 'Ideogram 3.0', 'filename': 'ideogram3', 'open_source': False},
    'model-018': {'name': 'Piclumen Realistic V2', 'filename': 'piclumen-realistic-v2', 'open_source': False},
    'model-019': {'name': 'F Lite Standard', 'filename': 'f-lite-standard', 'open_source': True},
    'model-020': {'name': 'Google Gemini Flash 2.0 Preview 0507', 'filename': 'gemini-2.0-flash-0507', 'open_source': False},
    'model-021': {'name': 'Midjourney v7 20250501', 'filename': 'midjourneyv7-20250501', 'open_source': False},
    'model-022': {'name': 'Tencent Hunyuan Image 2.0', 'filename': 'hunyuan-image-2.0', 'open_source': False},
    'model-023': {'name': 'Google Imagen 4', 'filename': 'imagen4', 'open_source': False},
    'model-024': {'name': 'Recraft V3 Raw', 'filename': 'recraft-v3-raw', 'open_source': False},
    'model-025': {'name': 'ByteDance BAGEL', 'filename': 'bagel', 'open_source': True},
    'model-026': {'name': 'FLUX.1 Kontext [pro]', 'filename': 'flux1-kontext-pro', 'open_source': False},
    'model-027': {'name': 'Chroma v34', 'filename': 'chroma-34', 'open_source': True},
    'model-028': {'name': 'Ernie 4.5 Turbo', 'filename': 'ernie-45turbo', 'open_source': False},
    'model-029': {'name': 'Google Imagen 4 Ultra', 'filename': 'imagen4ultra', 'open_source': False},
    'model-030': {'name': 'Qwen-Image', 'filename': 'qwen-image', 'open_source': True},
    'model-031': {'name': 'Gemini 2.5 Flash Image Preview', 'filename': 'gemini25flashimagepreview', 'open_source': False},
    'model-032': {'name': 'FLUX.1 Krea', 'filename': 'flux1-krea', 'open_source': True},
    'model-033': {'name': 'Tencent Hunyuan Image 2.1', 'filename': 'hunyuan-image-2.1', 'open_source': True},
    'model-034': {'name': 'ByteDance Seedream 4.0 4k', 'filename': 'seedream-4.0-4k', 'open_source': False},
    'model-035': {'name': 'Kling AI KOLORS 2.1', 'filename': 'klingai-kolors-2.1', 'open_source': False},
    'model-036': {'name': 'Tencent HunyuanImage-3.0', 'filename': 'hunyuan-image-3.0', 'open_source': True},
    'model-037': {'name': 'OpenAI: GPT-5 Image Mini High', 'filename': 'gpt-5-image-mini-high', 'open_source': False},
    'model-038': {'name': 'OpenAI: GPT-5 Image Mini Low', 'filename': 'gpt-5-image-mini-low', 'open_source': False},
    'model-039': {'name': 'OpenAI: GPT-5 Image Mini Medium', 'filename': 'gpt-5-image-mini-medium', 'open_source': False},
    'model-040': {'name': 'Microsoft: MAI-Image-1', 'filename': 'mai-image-1', 'open_source': False},
    'model-041': {'name': 'Google Nano Banana Pro (Nano Banana 2, Gemini 3 Pro Image)', 'filename': 'nanobananapro-4k', 'open_source': False},
    'model-042': {'name': 'Z Image Turbo', 'filename': 'z-image-turbo', 'open_source': True},
    'model-043': {'name': 'Black Forest Labs FLUX.2 [pro]', 'filename': 'flux2-pro-2k', 'open_source': False},
    'model-044': {'name': 'Black Forest Labs FLUX.2 [dev]', 'filename': 'flux2-dev', 'open_source': True}
}

# Engedélyezett képkiterjesztések listája
ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']

# ELO Rating beállítások
DEFAULT_ELO = 1500  # Alapértelmezett ELO érték új modellekhez
K_FACTOR = 32       # K-faktor - a magasabb érték nagyobb változást eredményez győzelemkor/vereségkor

# Felhasználói élmény beállítások
REVEAL_DELAY_MS = 2500  # Szavazás után a modellek neveinek megjelenítési ideje milliszekundumban

# Befagyasztott modellek beállítások
# Az alkalmazás indításakor a leaderboard alsó N modellje "befagyasztásra" kerül.
# A befagyasztott modellek nem vesznek részt az Arena Battle-ben, de a Side-by-Side-ban láthatók.
FROZEN_BOTTOM_COUNT = 10  # Hány modellt fagyasszunk be az aljáról (0 = kikapcsolva)