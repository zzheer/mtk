"""Command-first MTK option parsing regressions."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MTK = str(ROOT / "bin/mtk")
spec = importlib.util.spec_from_file_location("mtk_output", ROOT / "libexec/mtk-output.py")
output = importlib.util.module_from_spec(spec)
spec.loader.exec_module(output)


class CommandOptionParsingTests(unittest.TestCase):
    def test_final_explicit_block_extracts_resource_aliases(self):
        command, lines, size, truncate = output.options([
            "mtk", "git", "diff", "--", "--time", "3s", "--memory", "64M",
            "--cpu", "25", "--root-only",
        ])
        self.assertEqual(command, ["mtk", "--time-limit", "3s", "--memory-limit", "64M",
                                  "--cpu-limit", "25", "--exclude-children", "git", "diff"])
        self.assertEqual((lines, size, truncate), (80, 32 * 1024, True))

    def test_later_explicit_values_override_prefix_values(self):
        command, *_ = output.options([
            "mtk", "--time-limit", "9s", "git", "diff", "--", "--time", "2s",
        ])
        self.assertEqual(command, ["mtk", "--time-limit", "9s", "--time-limit", "2s",
                                   "git", "diff"])

    def test_last_separator_preserves_child_native_separator(self):
        args = ["mtk", "python", "-c", "pass", "--", "--time", "child-value", "--",
                "--memory", "5M"]
        command, *_ = output.options(args)
        self.assertEqual(command, ["mtk", "--memory-limit", "5M", "python", "-c", "pass",
                                   "--", "--time", "child-value"])

    def test_non_option_tail_after_separator_remains_legacy_child_arguments(self):
        args = ["mtk", "git", "diff", "--", "ordinary", "--time", "2s"]
        command, *_ = output.options(args)
        self.assertEqual(command, args)

    def test_missing_value_unknown_option_and_stray_argument_are_rejected(self):
        for args in (
            ["mtk", "echo", "ok", "--", "--time"],
            ["mtk", "echo", "ok", "--", "--time", "2s", "--unknown"],
            ["mtk", "echo", "ok", "--", "--time", "2s", "unexpected"],
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                output.options(args)


class CommandOptionEndToEndTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.capture = self.folder / "args.json"
        stub = self.folder / "rtk"
        stub.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            f"open({str(self.capture)!r}, 'w').write(json.dumps(sys.argv[1:]))\n"
        )
        stub.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{self.folder}:{os.environ.get('PATH', '')}",
            "XDG_CONFIG_HOME": str(self.folder / "config"),
            "XDG_STATE_HOME": str(self.folder / "state"),
        }

    def invoke(self, args):
        return subprocess.run([MTK, *args], env=self.env, capture_output=True, timeout=10)

    def test_explicit_block_executes_command_with_resource_limits_removed(self):
        result = self.invoke(["git", "diff", "--", "--time", "3s", "--memory", "64M"])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.capture.read_text()), ["git", "diff"])

    def test_invalid_explicit_block_fails_before_workload_execution(self):
        for args in (["git", "diff", "--", "--time"],
                     ["git", "diff", "--", "--time", "2s", "--not-an-mtk-option"],
                     ["git", "diff", "--", "--time", "2s", "stray"]):
            self.capture.unlink(missing_ok=True)
            result = self.invoke(args)
            self.assertEqual(result.returncode, 2, (args, result.stderr))
            self.assertFalse(self.capture.exists(), args)


if __name__ == "__main__":
    unittest.main()
