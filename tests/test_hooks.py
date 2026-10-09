import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import unittest


MTK = str(Path(__file__).resolve().parents[1] / "bin/mtk")
ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "libexec/mtk-codex-hook.py"


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

    def test_configuration_installs_private_adapter_and_migrates_old_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hooks.json"
            old_command = "rtk hook codex --ultra-compact --skip-env"
            old_handler = {"type": "command", "command": old_command}
            existing = {"hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [old_handler, old_handler,
                                                    {"type": "command", "command": "echo keep"}]},
                {"matcher": "Other", "hooks": [{"type": "command", "command": "echo keep"}]},
            ]}}
            path.write_text(json.dumps(existing))
            result = subprocess.run([MTK, "hook", "codex"],
                env={**os.environ, "CODEX_HOME": directory}, stdin=subprocess.DEVNULL,
                capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(path.read_text())
            entries = data["hooks"]["PreToolUse"]
            preserved = [h for entry in entries for h in entry.get("hooks", [])
                         if h.get("command") == "echo keep"]
            self.assertEqual(len(preserved), 2)
            self.assertEqual(sum(h.get("command") == old_handler["command"]
                                 for entry in entries for h in entry.get("hooks", [])), 0)
            owned = [h for entry in entries for h in entry.get("hooks", [])
                     if "mtk-codex-hook.py" in h.get("command", "")]
            self.assertEqual(len(owned), 1)
            self.assertTrue(Path(owned[0]["command"].split()[0]).is_absolute())
            self.assertIn(str(ADAPTER), owned[0]["command"])
            self.assertEqual(shlex.split(owned[0]["command"])[-2:],
                             ["--ultra-compact", "--skip-env"])


class CodexHookAdapterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.seen = self.folder / "rtk-input.json"
        fake_rtk = self.folder / "rtk"
        fake_rtk.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            f"payload = json.load(sys.stdin); open({str(self.seen)!r}, 'w').write(json.dumps(payload))\n"
            "if payload.get('tool_name') != 'Bash': sys.exit(0)\n"
            "command = payload['tool_input']['command']\n"
            "if command.startswith('mtk '): sys.exit(0)\n"
            "rewrites = {'git status': 'rtk git status', "
            "'env -u SOME_VAR git status': 'env -u SOME_VAR rtk git status', "
            "'env -u SOME_VAR  git status': 'env -u SOME_VAR rtk git status', "
            "'nice -n 5 git status': 'nice -n 5 rtk git status', "
            "'nice -n 5  git status': 'nice -n 5 rtk git status', "
            "\"git status && echo 'rtk git status'\": \"rtk git status && echo 'rtk git status'\", "
            "'git status && diff': 'rtk git status && rtk diff'}\n"
            "updated = rewrites.get(command, command)\n"
            "tool_input = dict(payload['tool_input']); tool_input['command'] = updated\n"
            "print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PreToolUse', "
            "'permissionDecision': 'allow', 'permissionDecisionReason': 'RTK auto-rewrite', "
            "'updatedInput': tool_input}}))\n"
        )
        fake_rtk.chmod(0o755)
        self.env = {**os.environ, "PATH": f"{self.folder}:{os.environ.get('PATH', '')}"}

    def invoke(self, payload):
        return subprocess.run([sys.executable, str(ADAPTER)], input=json.dumps(payload),
            text=True, env=self.env, capture_output=True, timeout=10)

    def test_rewrites_command_position_and_preserves_other_fields(self):
        payload = {"session_id": "s1", "tool_name": "Bash",
                   "permission_mode": "default",
                   "tool_input": {"command": "git status", "description": "keep",
                                  "workdir": str(ROOT), "timeout_ms": 1000}}
        result = self.invoke(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        delegated = json.loads(self.seen.read_text())
        self.assertEqual(delegated["tool_input"]["command"], "git status")
        response = json.loads(result.stdout)
        updated = response["hookSpecificOutput"]["updatedInput"]
        self.assertEqual(updated["command"], "mtk git status")
        self.assertEqual(updated["description"], "keep")
        self.assertEqual(updated["workdir"], str(ROOT))
        self.assertEqual(updated["timeout_ms"], 1000)

    def test_rewrites_rtk_command_tokens_but_not_quoted_text_or_mtk(self):
        for command, expected in (
            ("rtk git status", "mtk git status"),
            ("git status && echo 'rtk git status'", "mtk git status && echo 'rtk git status'"),
            ("git status && rtk diff", "mtk git status && mtk diff"),
        ):
            with self.subTest(command=command):
                result = self.invoke({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertTrue(result.stdout.strip(), (command, result.stderr))
                self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]["command"], expected)
        result = self.invoke({"tool_name": "Bash", "tool_input": {"command": "mtk git status"}})
        self.assertEqual(result.stdout, "")

    def test_rewrites_wrapped_and_already_prefixed_commands(self):
        cases = (
            ("env -u SOME_VAR git status", "env -u SOME_VAR mtk git status"),
            ("env -u SOME_VAR rtk git status", "env -u SOME_VAR mtk git status"),
            ("nice -n 5 git status", "nice -n 5 mtk git status"),
            ("nice -n 5 rtk git status", "nice -n 5 mtk git status"),
        )
        for command, expected in cases:
            with self.subTest(command=command):
                result = self.invoke({"tool_name": "Bash", "tool_input": {"command": command}})
                self.assertTrue(result.stdout.strip(), (command, result.stderr))
                updated = json.loads(result.stdout)["hookSpecificOutput"]["updatedInput"]["command"]
                self.assertEqual(updated, expected)

    def test_malformed_and_unsupported_events_emit_no_stdout(self):
        for raw in (b"{bad json", json.dumps({"tool_name": "Read", "tool_input": {"command": "git status"}}).encode()):
            result = subprocess.run([sys.executable, str(ADAPTER)], input=raw,
                env=self.env, capture_output=True, timeout=10)
            self.assertEqual(result.stdout, b"")

    @unittest.skipUnless(shutil.which("rtk"), "RTK is unavailable")
    def test_real_rtk_rewrite_is_adapted_to_mtk(self):
        cases = (
            ("git status", "mtk git status"),
            ("rtk git status", "mtk git status"),
            ("env FOO=bar git status", "env FOO=bar mtk git status"),
            ("env FOO=bar rtk git status", "env FOO=bar mtk git status"),
            ("nice -n 5 git status", "nice -n 5 mtk git status"),
            ("nice -n 5 rtk git status", "nice -n 5 mtk git status"),
            ("timeout 10 git status", "timeout 10 mtk git status"),
            ("timeout -k 2 10 rtk git status", "timeout -k 2 10 mtk git status"),
            ('git status -- "rtk git status"', 'mtk git status -- "rtk git status"'),
            ("git status -- literal-rtk", "mtk git status -- literal-rtk"),
            ("git status\ngit diff --stat", "mtk git status\nmtk git diff --stat"),
            ('git status\necho "rtk git status"', 'mtk git status\necho "rtk git status"'),
        )
        for command, expected in cases:
            with self.subTest(command=command):
                event = {"hook_event_name": "PreToolUse", "permission_mode": "default",
                         "tool_name": "Bash", "tool_input": {"command": command,
                         "workdir": str(ROOT), "timeout_ms": 1000}}
                result = subprocess.run([sys.executable, str(ADAPTER)], input=json.dumps(event),
                    text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                hook = json.loads(result.stdout)["hookSpecificOutput"]
                self.assertEqual(hook["updatedInput"]["command"], expected)
                self.assertEqual(hook["permissionDecisionReason"], "MTK auto-rewrite")

    @unittest.skipUnless(shutil.which("rtk"), "RTK is unavailable")
    def test_real_rtk_skips_existing_mtk_and_unsupported_events(self):
        events = (
            {"tool_name": "Bash", "tool_input": {"command": "mtk git status"}},
            {"tool_name": "Read", "tool_input": {"command": "git status"}},
        )
        for event in events:
            with self.subTest(event=event):
                event.update({"hook_event_name": "PreToolUse", "permission_mode": "default"})
                result = subprocess.run([sys.executable, str(ADAPTER)], input=json.dumps(event),
                    text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
