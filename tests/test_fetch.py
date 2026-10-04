import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class FetchTests(unittest.TestCase):
    def run_fetch(self, body, status=0, output=False):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake = tmp / 'bin'
            fake.mkdir()
            # Only stubbed tools are discoverable, so these tests never access network.
            for name in ('bash', 'dirname', 'mktemp', 'mv', 'rm'):
                import shutil
                source = shutil.which(name)
                if source:
                    (fake / name).symlink_to(source)
            (fake / 'curl').write_text('#!/bin/bash\nprintf "%s" "$FETCH_BODY"\nexit "$FETCH_STATUS"\n')
            (fake / 'curl').chmod(0o755)
            destination = tmp / 'result.md'
            destination.write_text('existing content')
            args = ['/bin/bash', str(ROOT / 'libexec/mtk-fetch'), 'https://example.invalid']
            if output:
                args += ['-o', str(destination)]
            proc = subprocess.run(args, env={**os.environ, 'PATH': str(fake), 'FETCH_BODY': body,
                                           'FETCH_STATUS': str(status)}, capture_output=True, text=True, timeout=5)
            return proc, destination.read_text()

    def test_rejects_short_final_fallback(self):
        proc, _ = self.run_fetch('error')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, '')

    def test_rejects_challenge_and_preserves_destination(self):
        proc, destination = self.run_fetch('Just a moment...' + 'x' * 100, output=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(destination, 'existing content')

    def test_rejects_http_failure_body(self):
        proc, _ = self.run_fetch('server failure ' * 20, status=22)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, '')

    def test_accepts_valid_final_fallback(self):
        body = '# Useful article\n' + 'Useful article content with many words. ' * 5
        proc, destination = self.run_fetch(body, output=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(destination, body + '\n')

    def test_missing_output_argument_is_usage_error(self):
        proc = subprocess.run(['/bin/bash', str(ROOT / 'libexec/mtk-fetch'), '-o'],
                              capture_output=True, text=True, timeout=5)
        self.assertEqual(proc.returncode, 2)
        self.assertIn('requires', proc.stderr)
