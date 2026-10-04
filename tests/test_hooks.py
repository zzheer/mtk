import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


MTK = str(Path(__file__).resolve().parents[1] / "bin/mtk")


class HookTests(unittest.TestCase):
    def test_other_hook_commands_still_reach_rtk(self):
        result = subprocess.run([MTK, "hook", "--help"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"Usage: mtk hook", result.stdout)

    def test_help_with_redirected_stdin(self):
        result = subprocess.run([MTK, "hook", "codex", "--help"],
            stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"Usage: mtk hook codex", result.stdout)

    def test_configuration_preserves_existing_hooks_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hooks.json"
            existing = {"hooks": {"PreToolUse": [{"matcher": "Other", "hooks": [
                {"type": "command", "command": "echo existing"}]}]}, "extra": True}
            path.write_text(json.dumps(existing))
            for _ in range(2):
                result = subprocess.run([MTK, "hook", "codex"],
                    env={**os.environ, "CODEX_HOME": directory},
                    stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(path.read_text())
            self.assertTrue(data["extra"])
            self.assertEqual(data["hooks"]["PreToolUse"][0], existing["hooks"]["PreToolUse"][0])
            self.assertEqual(len(data["hooks"]["PreToolUse"]), 2)


if __name__ == "__main__":
    unittest.main()
