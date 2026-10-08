"""Repository privacy and distribution regression checks; Python standard library only."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('privacy', ROOT / 'scripts/check_commit_privacy.py')
PRIVACY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRIVACY)


class RepositoryTests(unittest.TestCase):
    def test_sensitive_content(self):
        samples = [
            'C' + ':' + '\\Users\\someone\\console.log',
            '/home/' + 'someone/private',
            '7656119' + '1' * 10,
            'someone' + '@' + 'example.com',
            'gh' + 'p_' + 'A' * 36,
            'github_' + 'pat_' + 'A' * 40,
            'sk' + '-' + 'A' * 32,
            'AK' + 'IA' + 'A' * 16,
            '-----BEGIN ' + 'RSA PRIVATE KEY-----',
            'https://' + 'user:password' + '@' + 'example.com/repo',
        ]
        for sample in samples:
            with self.subTest(sample=samples.index(sample)):
                self.assertTrue(PRIVACY.content_findings(sample.encode()))
        self.assertTrue(PRIVACY.content_findings(b'\x00binary'))
        self.assertTrue(PRIVACY.content_findings(b'\xff'))
        self.assertFalse(PRIVACY.content_findings(b'https://github.com/owner/repo\ncontent/fx/beam'))

    def test_index_and_identity_enforcement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env = dict(os.environ, GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
            for key in ('GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_COMMITTER_NAME',
                        'GIT_COMMITTER_EMAIL', 'GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
                env.pop(key, None)
            def run(*args):
                return subprocess.run(args, cwd=root, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, check=False)
            self.assertEqual(run('git', 'init', '--initial-branch=main').returncode, 0)
            (root / '.gitignore').write_text('*\n!/.gitignore\n!/README.md\n!/.githooks/\n!/.githooks/pre-commit\n!/scripts/\n!/scripts/check_commit_privacy.py\n')
            (root / 'README.md').write_text('Public mod information\n')
            shutil.copytree(ROOT / 'scripts', root / 'scripts')
            shutil.copytree(ROOT / '.githooks', root / '.githooks')
            run('git', 'config', '--local', 'core.hooksPath', '.githooks')
            run('git', 'add', '.gitignore', 'README.md', '.githooks', 'scripts')
            checker = str(root / 'scripts/check_commit_privacy.py')
            first_check = run(sys.executable, checker)
            self.assertEqual(first_check.returncode, 0, first_check.stderr.decode())
            run('git', 'config', '--local', 'user.name', 'PublicHandle')
            run('git', 'config', '--local', 'user.email', 'private' + '@' + 'example.com')
            self.assertNotEqual(run(sys.executable, checker, '--check-identity').returncode, 0)
            run('git', 'config', '--local', 'user.email', '123+public' + '@' + 'users.noreply.github.com')
            self.assertEqual(run(sys.executable, checker, '--check-identity').returncode, 0)
            (root / '.env').write_text('local configuration')
            self.assertEqual(run('git', 'check-ignore', '.env').returncode, 0)
            run('git', 'add', '--force', '.env')
            self.assertNotEqual(run(sys.executable, checker).returncode, 0)
            run('git', 'rm', '--cached', '.env')
            (root / 'README.md').write_text('gh' + 'p_' + 'A' * 36)
            run('git', 'add', 'README.md')
            # Staged secrets must still fail after the working file is cleaned.
            (root / 'README.md').write_text('Clean working copy')
            result = run(sys.executable, checker)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(('gh' + 'p_' + 'A' * 36).encode(), result.stderr)
            self.assertNotEqual(run('git', 'commit', '-m', 'Must be blocked').returncode, 0)
            run('git', 'add', 'README.md')
            self.assertEqual(run('git', 'commit', '-m', 'Reviewed public snapshot').returncode, 0)

    def test_install_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / 'lasgun_comfort', root / 'lasgun_comfort')
            (root / 'release_support').mkdir()
            shutil.copyfile(ROOT / 'release_support/build_release.py', root / 'release_support/build_release.py')
            subprocess.run([sys.executable, str(root / 'release_support/build_release.py')], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            version = json.loads((root / 'lasgun_comfort/info.json').read_text())['version']
            archive = root / 'dist' / f'lasgun_comfort-{version}.zip'
            with zipfile.ZipFile(archive) as zipped:
                self.assertEqual(len(zipped.namelist()), 5)
                self.assertIsNone(zipped.testzip())
                for name in zipped.namelist():
                    self.assertEqual(zipped.read(name), (root / name).read_bytes())
            self.assertTrue(archive.with_suffix('.zip.sha256').is_file())
            (root / 'lasgun_comfort/console.log').write_text('must never ship')
            self.assertNotEqual(subprocess.run([sys.executable, str(root / 'release_support/build_release.py')],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode, 0)


if __name__ == '__main__':
    unittest.main()
