"""
Generálja a data/manifest.json fájlt a képfájlok alapján.

Lokálisan a teljes data/ mappából dolgozik:
    python generate_manifest.py

GitHub Actions-ben a teljes képarchívum checkoutja nélkül is használható:
    python generate_manifest.py --git-tree "$GITHUB_SHA"

Ebben az esetben csak a Git tree metaadatait olvassa ki, a képek blob-jait nem
kell letölteni. A Render.com-on (DATA_MODE esetén) az app ebből a fájlból tudja
meg, melyik modellhez milyen kiterjesztésű kép tartozik.
"""
import argparse
import json
import os
import subprocess


DATA_DIR = 'data'
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def manifest_from_paths(paths):
    """Build the manifest from paths relative to the repository root."""
    manifest = {}
    total_files = 0

    for path in paths:
        normalized = path.replace('\\', '/')
        parts = normalized.split('/')
        if len(parts) != 3 or parts[0] != DATA_DIR:
            continue

        prompt_id, filename = parts[1], parts[2]
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue

        base = os.path.splitext(filename)[0]
        manifest.setdefault(prompt_id, {})[base] = filename
        total_files += 1

    return manifest, total_files


def local_data_paths():
    paths = []
    for entry in sorted(os.listdir(DATA_DIR)):
        dirpath = os.path.join(DATA_DIR, entry)
        if not os.path.isdir(dirpath):
            continue
        try:
            for fname in os.listdir(dirpath):
                paths.append(os.path.join(DATA_DIR, entry, fname))
        except PermissionError:
            print(f"Warning: Cannot read {dirpath}, skipping.")
    return paths


def git_data_paths(ref):
    output = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', ref, '--', DATA_DIR],
        text=True,
    )
    return output.splitlines()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--git-tree',
        metavar='REF',
        help='Build the manifest from a Git tree without checking out image blobs.',
    )
    args = parser.parse_args()

    paths = git_data_paths(args.git_tree) if args.git_tree else local_data_paths()
    manifest, total_files = manifest_from_paths(paths)

    output_path = os.path.join(DATA_DIR, 'manifest.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, sort_keys=True)

    source = f'Git tree {args.git_tree}' if args.git_tree else 'local data folder'
    print(
        f"Manifest generated from {source}: {total_files} image files across "
        f"{len(manifest)} prompts -> {output_path}"
    )


if __name__ == '__main__':
    main()
