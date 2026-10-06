import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


MTK = str(Path(__file__).resolve().parents[1] / 'bin/mtk')


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'mtk/config.json'
        self.config.parent.mkdir()
        self.env = {**os.environ, 'XDG_CONFIG_HOME': self.temp.name}

    def run_mtk(self, flags=()):
        result = subprocess.run([MTK, *flags, sys.executable, '-c',
                                 "print('one\\ntwo\\nthree')"],
                                env=self.env, capture_output=True, timeout=10)
        match = re.search(rb'(?m)^(/tmp/mtk-[^\r\n]+\.log)$', result.stderr)
        if match:
            path = Path(os.fsdecode(match[1]))
            self.addCleanup(path.unlink, missing_ok=True)
            self.assertEqual(path.read_bytes(), b'one\ntwo\nthree\n')
        return result

    def test_config_limits_display_and_cli_overrides(self):
        self.config.write_text(json.dumps({'max_lines': 1, 'max_bytes': '32KiB'}))
        result = self.run_mtk()
        self.assertEqual(result.stdout, b'one\n[truncated by mtk]\n')
        result = self.run_mtk(['--max-lines', '3'])
        self.assertEqual(result.stdout, b'one\ntwo\nthree\n')
        result = self.run_mtk(['--no-truncate'])
        self.assertEqual(result.stdout, b'one\ntwo\nthree\n')

    def test_byte_limit_and_truncate_false(self):
        self.config.write_text(json.dumps({'max_bytes': 3}))
        self.assertEqual(self.run_mtk().stdout, b'one\n[truncated by mtk]\n')
        self.assertEqual(self.run_mtk(['--max-bytes', '32KiB']).stdout,
                         b'one\ntwo\nthree\n')
        self.config.write_text(json.dumps({'max_bytes': 3, 'truncate': False}))
        self.assertEqual(self.run_mtk().stdout, b'one\ntwo\nthree\n')

    def test_missing_config_keeps_defaults(self):
        self.assertEqual(self.run_mtk().stdout, b'one\ntwo\nthree\n')

    def test_invalid_config_never_runs_command(self):
        for contents in ('{', '[]', '{"max_lines":0}', '{"max_lines":true}',
                         '{"max_lines":1.5}', '{"max_bytes":"0"}',
                         '{"max_bytes":false}', '{"truncate":"false"}',
                         '{"typo":1}'):
            with self.subTest(contents=contents):
                self.config.write_text(contents)
                result = self.run_mtk()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b'')
                self.assertIn(b'config', result.stderr)

    def test_home_fallback(self):
        self.env.pop('XDG_CONFIG_HOME')
        self.env['HOME'] = self.temp.name
        self.config = Path(self.temp.name) / '.config/mtk/config.json'
        self.config.parent.mkdir(parents=True)
        self.config.write_text('{"max_lines":1}')
        self.assertEqual(self.run_mtk().stdout, b'one\n[truncated by mtk]\n')

    def test_config_read_is_bounded(self):
        self.config.write_text('{}' + ' ' * 65536)
        result = self.run_mtk()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b'config', result.stderr)

    def test_fifo_config_fails_without_blocking_before_governor(self):
        os.mkfifo(self.config)
        result = subprocess.run([MTK, '--time-limit', '1s', 'echo',
                                 'must-not-run'], env=self.env,
                                capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b'expected a regular JSON file', result.stderr)

    def test_symlink_to_regular_config_loads(self):
        target = self.config.parent / 'config.target.json'
        target.write_text(json.dumps({'max_lines': 1}))
        os.symlink(target, self.config)
        self.assertEqual(self.run_mtk().stdout, b'one\n[truncated by mtk]\n')

    def test_dangling_symlink_config_keeps_defaults(self):
        os.symlink(self.config.parent / 'missing.json', self.config)
        self.assertEqual(self.run_mtk().stdout, b'one\ntwo\nthree\n')

    def test_device_config_fails_before_governor(self):
        os.symlink('/dev/null', self.config)
        result = subprocess.run([MTK, '--time-limit', '1s', 'echo',
                                 'must-not-run'], env=self.env,
                                capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b'expected a regular JSON file', result.stderr)

    def test_directory_config_fails_before_governor(self):
        self.config.mkdir()
        result = subprocess.run([MTK, '--time-limit', '1s', 'echo',
                                 'must-not-run'], env=self.env,
                                capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b'expected a regular JSON file', result.stderr)

    def test_invalid_utf8_config_fails_before_governor(self):
        self.config.write_bytes(b'{"max_lines": 1}\xff')
        result = subprocess.run([MTK, '--time-limit', '1s', 'echo',
                                 'must-not-run'], env=self.env,
                                capture_output=True, timeout=3)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertIn(b"codec can't decode", result.stderr)


if __name__ == '__main__':
    unittest.main()
