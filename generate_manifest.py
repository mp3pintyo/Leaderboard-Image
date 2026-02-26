"""
Generálja a data/manifest.json fájlt a helyi data/ mappában lévő képfájlok alapján.

Futtasd a lokális gépen (ahol a képek megvannak), majd commitold a manifest.json-t gitbe:
    python generate_manifest.py
    git add data/manifest.json
    git commit -m "Update image manifest"
    git push

A Render.com-on (DATA_MODE esetén) az app ebből a fájlból tudja meg, melyik
modellhez milyen kiterjesztésű kép tartozik, anélkül hogy a képek ott lennének.
"""
import os
import json

DATA_DIR = 'data'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

manifest = {}
total_files = 0

for entry in sorted(os.listdir(DATA_DIR)):
    dirpath = os.path.join(DATA_DIR, entry)
    if not os.path.isdir(dirpath):
        continue

    prompt_files = {}
    try:
        for fname in os.listdir(dirpath):
            ext = os.path.splitext(fname)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                base = os.path.splitext(fname)[0]
                prompt_files[base] = fname
                total_files += 1
    except PermissionError:
        print(f"Warning: Cannot read {dirpath}, skipping.")
        continue

    if prompt_files:
        manifest[entry] = prompt_files

output_path = os.path.join(DATA_DIR, 'manifest.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)

print(f"Manifest generated: {total_files} image files across {len(manifest)} prompts → {output_path}")
