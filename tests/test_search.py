import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SearchTests(unittest.TestCase):
    def run_provider(self, snippet, json_mode=False, status=0):
        with tempfile.TemporaryDirectory() as tmp:
            provider = Path(tmp) / "duckduckgo-tools"
            envelope = {"contract": "search-cli/v1", "tool": "duckduckgo-tools", "query": "query", "results": [{"rank": 1, "title": "Example", "url": "https://example.invalid", "snippet": snippet}]}
            # Fixture replaces only external network provider; wrapper formatting is real.
            provider.write_text("#!/bin/bash\n[[ \u0024* == \u0027search --query query --limit 5 --json\u0027 ]] || exit 99\nprintf \u0027%s\\n\u0027 " + __import__("shlex").quote(json.dumps(envelope)) + "\nexit " + str(status) + "\n")
            provider.chmod(0o755)
            return subprocess.run([str(ROOT / "libexec/mtk-search"), "query", *(["--json"] if json_mode else [])], env={**os.environ, "PATH": tmp + ":" + os.environ["PATH"]}, capture_output=True, timeout=10)

    def test_null_snippet_is_safe(self):
        result = self.run_provider(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"Example", result.stdout)

    def test_json_preserves_provider_contract(self):
        result = self.run_provider(None, json_mode=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["tool"], "duckduckgo-tools")

    def test_provider_failure_is_not_hidden_by_fallback(self):
        result = self.run_provider("snippet", status=9)
        self.assertEqual(result.returncode, 9)

    def test_limit_validation(self):
        result = subprocess.run([str(ROOT / "libexec/mtk-search"), "query", "--limit", "0"], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)

if __name__ == "__main__":
    unittest.main()
