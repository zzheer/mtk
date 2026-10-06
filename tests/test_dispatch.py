"""Resource and display option normalization regressions."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('output', ROOT / 'libexec/mtk-output.py')
output = importlib.util.module_from_spec(spec)
spec.loader.exec_module(output)


class DispatchRegressions(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        patch = mock.patch.dict(os.environ, {'XDG_CONFIG_HOME': folder.name})
        patch.start()
        self.addCleanup(patch.stop)

    def test_prefix_limits_after_native_globals_still_precede_dispatch(self):
        command, *_ = output.options(['mtk', '--verbose', '--time-limit', '3s', 'git', 'diff'])
        self.assertEqual(command, ['mtk', '--time-limit', '3s', '--verbose', 'git', 'diff'])

    def test_suffix_wins_over_prefix_after_native_globals(self):
        command, *_ = output.options(['mtk', '--verbose', '--time-limit', '3s',
                                     'git', 'diff', '--time-limit', '1s'])
        self.assertEqual(command, ['mtk', '--time-limit', '3s', '--time-limit', '1s',
                                   '--verbose', 'git', 'diff'])

    def test_trailing_display_limits_are_extracted(self):
        command, lines, size, truncate = output.options(['mtk', 'python3', 'worker.py',
            '--max-lines', '4', '--max-bytes=1KiB', '--no-truncate'])
        self.assertEqual(command, ['mtk', 'python3', 'worker.py'])
        self.assertEqual((lines, size, truncate), (4, 1024, False))


if __name__ == '__main__':
    unittest.main()
