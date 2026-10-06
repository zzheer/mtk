import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AliasTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)
        stub = self.folder / "mtk"
        stub.write_text(f"#!{sys.executable}\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\n")
        stub.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.folder) + os.pathsep + os.environ["PATH"],
            "XDG_CONFIG_HOME": str(self.folder / "config")}

    def check_shells(self, aliases):
        names = ("mpf", "mpj", "mpn", "mssh", "mpp", "mp", "mr", "mgit", "mrg")
        commands = ("fd", "just", "node", "ssh", "python3", "proxy", "run", "git", "rg")
        arguments = ["space value", "", "--time-limit", "2s"]
        for shell in ("bash", "zsh"):
            with self.subTest(shell=shell):
                script = ("shopt -s expand_aliases\n" if shell == "bash" else "")
                script += 'source "$1"\n'
                script += "\n".join(f'eval \'{name} "space value" "" --time-limit 2s\'' for name in names)
                result = subprocess.run([shell, "-c", script, "aliases", str(aliases)],
                    env=self.env, capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual([json.loads(line) for line in result.stdout.splitlines()],
                    [[command, *arguments] for command in commands])

    def test_shared_aliases_use_automatic_dispatch_in_bash_and_zsh(self):
        self.check_shells(ROOT / "share/mtk/mtk-aliases.sh")

    def test_embedded_fallback_matches_shared_alias_behavior(self):
        # Minimal fixture exercises the fallback without a second Git checkout.
        (self.folder / "bin").mkdir()
        (self.folder / "libexec").mkdir()
        for path in ("bin/mtk", "libexec/mtk-output.py", "libexec/mtk-runner.py"):
            shutil.copy2(ROOT / path, self.folder / path)
        result = subprocess.run([str(self.folder / "bin/mtk"), "env"],
            env=self.env, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in result.stderr.splitlines():
            if path.startswith(b"/tmp/mtk-") and path.endswith(b".log"):
                self.addCleanup(Path(os.fsdecode(path)).unlink, missing_ok=True)
        aliases = self.folder / "aliases.sh"
        aliases.write_bytes(result.stdout)
        self.check_shells(aliases)

    def test_standalone_python_helper_preserves_arguments_without_proxy(self):
        result = subprocess.run([str(ROOT / "bin/mpp"), "space value", "", "--time-limit", "2s"],
            env=self.env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["python3", "space value", "", "--time-limit", "2s"])
