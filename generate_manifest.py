"""
Generálja a data/manifest.json fájlt a képfájlok alapján.

Lokálisan a teljes data/ mappából dolgozik:
    python generate_manifest.py

GitHub Actions-ben a teljes képarchívum checkoutja nélkül is használható:
    python generate_manifest.py --git-tree "$GITHUB_SHA"

Ebben az esetben csak a Git tree metaadatait olvassa ki, a képek blob-jait nem
kell letölteni. A Render.com-on (DATA_MODE esetén) az app ebből a fájlból tudja
meg, melyik modellhez milyen fájl tartozik.

Formátum:
    {"<prompt_id>": {"<fájl alapnév>": {"file": "grok.png", "key": "img/<git blob sha>"}}}

A `key` a kép tartalmából képzett (Git blob SHA-1) objektumkulcs a Cloudflare R2-n.
Így a kép URL-je szavazás előtt nem árulja el a modell nevét, a tartalom változásakor
új kulcs keletkezik, ezért a képek „immutable” módon, hosszan cache-elhetők.
"""
import argparse
import hashlib
import json
import os
import subprocess


DATA_DIR = 'data'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
KEY_PREFIX = 'img/'


def image_key(blob_sha):
    return f'{KEY_PREFIX}{blob_sha}'


def manifest_from_entries(entries):
    """entries: (repó-relatív útvonal, git blob sha vagy None) párok."""
    manifest = {}
    total_files = 0

    for path, blob_sha in entries:
        normalized = path.replace('\\', '/')
        parts = normalized.split('/')
        if len(parts) != 3 or parts[0] != DATA_DIR:
            continue

        prompt_id, filename = parts[1], parts[2]
        base, ext = os.path.splitext(filename)
        if ext.lower() not in ALLOWED_EXTENSIONS:
            continue

        entry = {'file': filename}
        if blob_sha:
            entry['key'] = image_key(blob_sha)
        manifest.setdefault(prompt_id, {})[base] = entry
        total_files += 1

    return manifest, total_files


def git_blob_sha(path):
    """Ugyanaz az azonosító, amit a `git hash-object` adna (SHA-1 a "blob <méret>\\0" fejléccel)."""
    digest = hashlib.sha1()
    digest.update(f'blob {os.path.getsize(path)}\0'.encode())
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def local_entries():
    """A helyi data/ mappa képei. A Gitben változatlan fájlok SHA-ját az indexből vesszük (gyors),
    a módosított vagy új fájlokét kiszámoljuk."""
    indexed = {}
    try:
        output = subprocess.check_output(['git', 'ls-files', '-s', '--', DATA_DIR], text=True)
        for line in output.splitlines():
            meta, path = line.split('\t', 1)
            indexed[path] = meta.split()[1]
        modified = set(subprocess.check_output(
            ['git', 'diff', '--name-only', '--', DATA_DIR], text=True).splitlines())
    except (OSError, subprocess.CalledProcessError):
        indexed, modified = {}, set()

    entries = []
    for entry in sorted(os.listdir(DATA_DIR)):
        dirpath = os.path.join(DATA_DIR, entry)
        if not os.path.isdir(dirpath):
            continue
        try:
            names = sorted(os.listdir(dirpath))
        except PermissionError:
            print(f"Warning: Cannot read {dirpath}, skipping.")
            continue
        for fname in names:
            rel = f'{DATA_DIR}/{entry}/{fname}'
            if os.path.splitext(fname)[1].lower() not in ALLOWED_EXTENSIONS:
                continue
            sha = indexed.get(rel) if rel not in modified else None
            entries.append((rel, sha or git_blob_sha(os.path.join(DATA_DIR, entry, fname))))
    return entries


def git_tree_entries(ref):
    output = subprocess.check_output(['git', 'ls-tree', '-r', ref, '--', DATA_DIR], text=True)
    entries = []
    for line in output.splitlines():
        meta, path = line.split('\t', 1)
        _mode, object_type, sha = meta.split()
        if object_type == 'blob':
            entries.append((path, sha))
    return entries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--git-tree',
        metavar='REF',
        help='Build the manifest from a Git tree without checking out image blobs.',
    )
    parser.add_argument(
        '--no-keys',
        action='store_true',
        help='Omit the content-addressed R2 keys (legacy format: prompt/filename URLs).',
    )
    args = parser.parse_args()

    entries = git_tree_entries(args.git_tree) if args.git_tree else local_entries()
    if args.no_keys:
        entries = [(path, None) for path, _sha in entries]
    manifest, total_files = manifest_from_entries(entries)

    output_path = os.path.join(DATA_DIR, 'manifest.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write('\n')

    source = f'Git tree {args.git_tree}' if args.git_tree else 'local data folder'
    print(
        f"Manifest generated from {source}: {total_files} image files across "
        f"{len(manifest)} prompts -> {output_path}"
    )


if __name__ == '__main__':
    main()
