#!/usr/bin/env python3
"""Adapt RTK Codex hook rewrites to MTK without altering hook JSON semantics."""

import json
import re
import subprocess
import sys


# Keep shell spelling intact, including quoted arguments and environment values.
TOKENS = re.compile(r"(?:\\[\s\S]|'[^']*'|\"(?:\\[\s\S]|[^\"\\])*\"|[^\s'\"\\;&|()])+|[;&|()]+")
ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")
WRAPPERS = {"env", "command", "nohup", "nice", "time", "timeout", "sudo", "doas"}
VALUE_OPTIONS = {"-n", "--adjustment", "-u", "--unset", "-C", "--chdir",
                 "-g", "--group", "--user", "-f", "--format", "-o", "--output",
                 "-k", "--kill-after", "-s", "--signal"}


def replace_prefixes(command, replacement):
    result = []
    position = 0
    command_start = True
    skip_value = False
    duration_pending = False
    for token in TOKENS.finditer(command):
        word = token.group()
        gap = command[position:token.start()]
        if "\n" in gap:
            command_start = True
            skip_value = duration_pending = False
        result.append(gap)
        position = token.end()
        if command_start and not skip_value and not duration_pending and word == "rtk":
            result.append(replacement)
            command_start = bool(not replacement)
            if not replacement:
                while position < len(command) and command[position] in " \t":
                    position += 1
        else:
            result.append(word)
            if word in {"&&", "||", ";", "|", "(", ")", "&"}:
                command_start = True
                skip_value = duration_pending = False
            elif command_start and skip_value:
                skip_value = False
            elif command_start and word.startswith("-"):
                skip_value = word in VALUE_OPTIONS
            elif command_start and word == "timeout":
                duration_pending = True
            elif command_start and duration_pending:
                duration_pending = False
            elif not (command_start and (ASSIGNMENT.match(word) or word in WRAPPERS)):
                command_start = False
    result.append(command[position:])
    return "".join(result)


def main():
    raw = sys.stdin.buffer.read(1_048_577)
    if len(raw) > 1_048_576:
        return
    try:
        payload = json.loads(raw)
        tool_input = payload.get("tool_input")
        if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
            return
        # RTK normally skips already-prefixed commands. Let its usual decision
        # pipeline inspect the underlying command before changing its wrapper.
        tool_input["command"] = replace_prefixes(tool_input["command"], "").lstrip()
        process = subprocess.run(["rtk", "hook", "codex", *sys.argv[1:]], input=json.dumps(payload),
            capture_output=True, text=True, timeout=5)
        if process.returncode or not process.stdout.strip():
            return
        response = json.loads(process.stdout)
        hook = response.get("hookSpecificOutput", {})
        updated = hook.get("updatedInput", {})
        command = updated.get("command")
        if not isinstance(command, str):
            return
        updated["command"] = replace_prefixes(command, "mtk")
        hook["permissionDecisionReason"] = "MTK auto-rewrite"
        print(json.dumps(response))
    except (ValueError, AttributeError, OSError, subprocess.TimeoutExpired):
        # Match RTK's fail-open behavior for invalid input or unavailable hooks.
        return


if __name__ == "__main__":
    main()
