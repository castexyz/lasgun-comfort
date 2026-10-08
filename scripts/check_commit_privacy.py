"""Check the complete Git index for accidental private data; Python standard library only."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

PATTERNS = {
    'Windows absolute path': r'(?i)\b[A-Z]:[\\/]',
    'personal home path': r'(?i)(?:/home/|/Users/|\\Users\\)[A-Za-z0-9_.-]+(?:[/\\]|\b)',
    'Steam account identifier': r'\b7656119[0-9]{10}\b',
    'email address': r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b',
    'GitHub token': r'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
    'API key': r'\bsk-[A-Za-z0-9_-]{20,}\b',
    'AWS access key': r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'private key': r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----',
    'credential in URL': r'https?://[^/\s]+:[^@\s]+@',
}
COMPILED = {label: re.compile(pattern) for label, pattern in PATTERNS.items()}
MAX_BYTES = 1_000_000


def content_findings(data):
    if len(data) > MAX_BYTES:
        return ['oversized file']
    if b'\x00' in data:
        return ['binary file']
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        return ['non-UTF-8 file']
    return [label for label, pattern in COMPILED.items() if pattern.search(text)]


def git(*args, data=None, accepted=(0,)):
    result = subprocess.run(['git', *args], input=data, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=False)
    if result.returncode not in accepted:
        raise RuntimeError('Git check failed; details withheld to avoid exposing private data')
    return result


def check_index(check_identity=False):
    # Ensure the policy being executed agrees with the policy being committed.
    git('diff', '--quiet', '--', '.gitignore', 'scripts/check_commit_privacy.py',
        '.githooks/pre-commit')
    records = git('ls-files', '--stage', '-z').stdout.split(b'\x00')
    entries = []
    for record in filter(None, records):
        metadata, path = record.split(b'\t', 1)
        mode, _, stage = metadata.split()
        if mode not in (b'100644', b'100755') or stage != b'0':
            raise RuntimeError('Symlinks, submodules or unresolved index entries cannot be committed')
        entries.append(path)
    if not entries:
        raise RuntimeError('No indexed files to review')
    rejected = git('check-ignore', '--no-index', '-z', '--stdin',
                   data=b'\x00'.join(entries) + b'\x00', accepted=(0, 1)).stdout
    if rejected:
        raise RuntimeError('Indexed files are outside the reviewed .gitignore allowlist')
    findings = 0
    for path in entries:
        decoded_path = path.decode('utf-8')
        data = git('show', ':' + decoded_path).stdout
        labels = content_findings(data)
        if labels:
            findings += 1
            print('Blocked indexed file: ' + ', '.join(labels), file=sys.stderr)
    if findings:
        raise RuntimeError(f'{findings} indexed file(s) need privacy review; matched values were not printed')
    if check_identity:
        for role in ('AUTHOR', 'COMMITTER'):
            identity = git('var', 'GIT_' + role + '_IDENT').stdout.decode('utf-8')
            email = re.search(r'<([^<>]+)>', identity)
            if not email or not email[1].lower().endswith('@users.noreply.github.com'):
                raise RuntimeError('Set both Git author and committer to your GitHub noreply identity before committing')
    print(f'PASS: reviewed {len(entries)} indexed text files; no configured sensitive-data patterns found')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-identity', action='store_true')
    options = parser.parse_args()
    try:
        check_index(options.check_identity)
    except (RuntimeError, OSError, UnicodeError, ValueError) as error:
        print('Privacy check failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
