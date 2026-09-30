"""Sync data files changed by the current push to Cloudflare R2.

Images are stored under content-addressed keys (``img/<git blob sha>``, see
generate_manifest.py), so the public image URL does not reveal the model name
before voting, and objects can be cached as immutable.

For every image referenced by data/manifest.json whose key is missing from R2:
- if the file did not change in this push and the legacy object ``<prompt>/<file>``
  exists, it is copied server-side (no download/upload);
- otherwise the file is uploaded from the Git object database.

Non-image files (e.g. prompt.txt) keep their legacy ``<prompt>/<file>`` keys.
Legacy image objects are left in place unless --prune-legacy-images is given.
"""
import argparse
import json
import mimetypes
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import PurePosixPath
import subprocess
import tempfile
import threading
from urllib.parse import quote


DATA_DIR = 'data'
MANIFEST_PATH = os.path.join(DATA_DIR, 'manifest.json')
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
CACHE_CONTROL = 'public,max-age=604800,stale-while-revalidate=86400'
IMMUTABLE_CACHE_CONTROL = 'public,max-age=31536000,immutable'
ZERO_SHA = '0' * 40
_print_lock = threading.Lock()


def log(message):
    with _print_lock:
        print(message, flush=True)


def is_image(path):
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def content_type(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.webp':
        return 'image/webp'
    return mimetypes.types_map.get(ext, 'application/octet-stream')


def changed_files(before, after):
    if before == ZERO_SHA:
        raise RuntimeError('The first push cannot be uploaded incrementally; run a full sync once.')

    output = subprocess.check_output(
        [
            'git', 'diff', '--name-status', '--no-renames', '-z',
            before, after, '--', DATA_DIR,
        ]
    )
    fields = output.split(b'\0')
    changes = []
    index = 0
    while index + 1 < len(fields) and fields[index]:
        status = fields[index].decode('utf-8')
        path = fields[index + 1].decode('utf-8')
        changes.append((status, path))
        index += 2
    return changes


class R2:
    """Vékony réteg az AWS CLI körül (dry-run módban csak kiírja a műveleteket)."""

    def __init__(self, bucket, endpoint_url, dry_run=False):
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.dry_run = dry_run

    def _run(self, args):
        if self.dry_run:
            log('DRY-RUN aws ' + ' '.join(args))
            return
        subprocess.run(['aws', *args, '--endpoint-url', self.endpoint_url], check=True)

    def list_keys(self):
        payload = json.loads(subprocess.check_output([
            'aws', 's3api', 'list-objects-v2',
            '--bucket', self.bucket,
            '--endpoint-url', self.endpoint_url,
            '--output', 'json',
        ], text=True) or '{}')
        return {item['Key'] for item in payload.get('Contents', [])}

    def upload_from_git(self, ref, path, key, cache_control):
        suffix = os.path.splitext(path)[1]
        if self.dry_run:
            log(f'DRY-RUN upload {ref}:{path} -> {key}')
            return
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
            temp_name = temp_file.name
        try:
            with open(temp_name, 'wb') as out:
                subprocess.run(['git', 'show', f'{ref}:{path}'], stdout=out, check=True)
            self._run([
                's3', 'cp', temp_name, f's3://{self.bucket}/{key}',
                '--content-type', content_type(path),
                '--cache-control', cache_control,
                '--only-show-errors',
            ])
        finally:
            os.unlink(temp_name)

    def copy(self, source_key, key, path):
        self._run([
            's3api', 'copy-object',
            '--bucket', self.bucket,
            '--copy-source', quote(f'{self.bucket}/{source_key}'),
            '--key', key,
            '--metadata-directive', 'REPLACE',
            '--content-type', content_type(path),
            '--cache-control', IMMUTABLE_CACHE_CONTROL,
            '--output', 'text',
        ])

    def delete(self, key):
        self._run(['s3', 'rm', f's3://{self.bucket}/{key}', '--only-show-errors'])


def legacy_key(path):
    return PurePosixPath(path).relative_to(DATA_DIR).as_posix()


def manifest_images(manifest):
    """{kulcs: repó-relatív útvonal} a manifestben kulccsal rendelkező képekhez."""
    images = {}
    for prompt_id, files in manifest.items():
        for entry in files.values():
            if isinstance(entry, dict) and entry.get('key'):
                images[entry['key']] = f'{DATA_DIR}/{prompt_id}/{entry["file"]}'
    return images


def git_data_files(ref):
    output = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', ref, '--', DATA_DIR],
        text=True,
    )
    return [path for path in output.splitlines() if path.startswith(f'{DATA_DIR}/')]


def plan(changes, existing_keys, images, data_files):
    """A szükséges R2 műveletek listája (tesztelhető, mellékhatás nélkül)."""
    changed = {path for status, path in changes if status[0] in {'A', 'M', 'T'}}
    actions = []

    for key, path in sorted(images.items()):
        if key in existing_keys:
            continue
        source = legacy_key(path)
        if path not in changed and source in existing_keys:
            actions.append(('copy', source, key, path))
        else:
            actions.append(('upload', path, key, IMMUTABLE_CACHE_CONTROL))

    for status, path in changes:
        if status[0] == 'D':
            if legacy_key(path) in existing_keys:
                actions.append(('delete', legacy_key(path)))
        elif status[0] in {'A', 'M', 'T'}:
            if not is_image(path):
                actions.append(('upload', path, legacy_key(path), CACHE_CONTROL))
        else:
            raise RuntimeError(f'Unsupported Git change status {status!r} for {path!r}')

    # Hiányzó nem-kép fájlok (pl. prompt.txt) pótlása
    for path in data_files:
        if not is_image(path) and path not in changed and legacy_key(path) not in existing_keys:
            actions.append(('upload', path, legacy_key(path), CACHE_CONTROL))
    return actions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--endpoint-url', required=True)
    parser.add_argument('--manifest', default=MANIFEST_PATH)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--dry-run', action='store_true', help='Only print the planned operations.')
    parser.add_argument('--existing-keys-file', help='JSON list of existing keys (for --dry-run testing).')
    parser.add_argument('--prune-legacy-images', action='store_true',
                        help='Delete legacy <prompt>/<file> image objects whose content-addressed copy exists.')
    args = parser.parse_args()

    r2 = R2(args.bucket, args.endpoint_url, dry_run=args.dry_run)
    changes = changed_files(args.before, args.after)
    if args.existing_keys_file:
        with open(args.existing_keys_file, encoding='utf-8') as f:
            existing_keys = set(json.load(f))
    else:
        existing_keys = r2.list_keys()
    with open(args.manifest, encoding='utf-8') as f:
        images = manifest_images(json.load(f))

    actions = plan(changes, existing_keys, images, git_data_files(args.after))
    counts = {}
    for action in actions:
        counts[action[0]] = counts.get(action[0], 0) + 1
    print(f'{len(changes)} changed data file(s); planned R2 operations: {counts or "none"}')

    def execute(action):
        kind = action[0]
        if kind == 'copy':
            _, source, key, path = action
            r2.copy(source, key, path)
        elif kind == 'upload':
            _, path, key, cache_control = action
            r2.upload_from_git(args.after, path, key, cache_control)
        elif kind == 'delete':
            r2.delete(action[1])
        return action

    failures = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [pool.submit(execute, action) for action in actions]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as error:  # noqa: BLE001 - összegyűjtjük, a végén hibával lépünk ki
                failures.append(error)
                log(f'ERROR: {error}')
    if failures:
        raise SystemExit(f'{len(failures)} R2 operation(s) failed.')

    if args.prune_legacy_images:
        final_keys = existing_keys | set(images)
        for key, path in images.items():
            legacy = legacy_key(path)
            if key in final_keys and legacy in existing_keys:
                r2.delete(legacy)


if __name__ == '__main__':
    main()
