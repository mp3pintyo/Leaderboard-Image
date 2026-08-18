"""Upload only data files changed by the current push to Cloudflare R2."""
import argparse
import json
import os
from pathlib import PurePosixPath
import subprocess
import tempfile


DATA_DIR = 'data'
CACHE_CONTROL = 'public,max-age=604800,stale-while-revalidate=86400'
ZERO_SHA = '0' * 40


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


def run_aws(args):
    subprocess.run(['aws', *args], check=True)


def aws_output(args):
    return subprocess.check_output(['aws', *args], text=True)


def s3_key(path):
    relative = PurePosixPath(path).relative_to(DATA_DIR)
    return relative.as_posix()


def git_data_files(ref):
    output = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', ref, '--', DATA_DIR],
        text=True,
    )
    return [path for path in output.splitlines() if path.startswith(f'{DATA_DIR}/')]


def existing_r2_keys(bucket, endpoint_url):
    payload = json.loads(aws_output([
        's3api', 'list-objects-v2',
        '--bucket', bucket,
        '--endpoint-url', endpoint_url,
        '--output', 'json',
    ]))
    return {item['Key'] for item in payload.get('Contents', [])}


def missing_r2_files(ref, existing_keys, changed_paths):
    return [
        path for path in git_data_files(ref)
        if s3_key(path) not in existing_keys and path not in changed_paths
    ]


def upload_file(after, path, bucket, endpoint_url):
    key = s3_key(path)
    suffix = os.path.splitext(path)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix) as temp_file:
        subprocess.run(
            ['git', 'show', f'{after}:{path}'],
            stdout=temp_file,
            check=True,
        )
        temp_file.flush()
        run_aws([
            's3', 'cp', temp_file.name, f's3://{bucket}/{key}',
            '--endpoint-url', endpoint_url,
            '--cache-control', CACHE_CONTROL,
            '--only-show-errors',
        ])


def delete_file(path, bucket, endpoint_url):
    key = s3_key(path)
    run_aws([
        's3', 'rm', f's3://{bucket}/{key}',
        '--endpoint-url', endpoint_url,
        '--only-show-errors',
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--before', required=True)
    parser.add_argument('--after', required=True)
    parser.add_argument('--bucket', required=True)
    parser.add_argument('--endpoint-url', required=True)
    args = parser.parse_args()

    changes = changed_files(args.before, args.after)
    changed_paths = {path for _, path in changes}
    existing_keys = existing_r2_keys(args.bucket, args.endpoint_url)
    missing = missing_r2_files(args.after, existing_keys, changed_paths)
    print(
        f'Found {len(changes)} changed data file(s) and '
        f'{len(missing)} missing R2 file(s).'
    )

    for status, path in changes:
        if status[0] in {'A', 'M', 'T'}:
            print(f'Uploading {path}')
            upload_file(args.after, path, args.bucket, args.endpoint_url)
        elif status[0] == 'D':
            print(f'Deleting {path}')
            delete_file(path, args.bucket, args.endpoint_url)
        else:
            raise RuntimeError(f'Unsupported Git change status {status!r} for {path!r}')

    for path in missing:
        print(f'Uploading missing {path}')
        upload_file(args.after, path, args.bucket, args.endpoint_url)


if __name__ == '__main__':
    main()
