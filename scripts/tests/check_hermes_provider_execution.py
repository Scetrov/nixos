"""Bounded live provider/tool acceptance inside the gateway container.

Run on stdin as the native runtime user; selects each provider explicitly and
prints only booleans/counts, never raw model output, prompts, logs or credentials.
Requires prior operator approval for the two inference calls. CLI history is
retained with source=tool; no configuration or credential state is rewritten.
"""

import argparse
import json
import subprocess
import sys


MARKER = "opsx-hermes-provider-ok"
COMMAND = "printf '" + MARKER + "\\n'"


def check(provider, model):
    prompt = (
        "Acceptance test: call the terminal tool exactly once with command " + COMMAND + ". "
        "Do not read files or environment variables, use network, or change state. "
        "After the tool returns, reply exactly " + MARKER + "."
    )
    try:
        result = subprocess.run([
            "hermes", "chat", "--oneshot", "--format", "stream-json",
            "--max-turns", "3", "--run-budget", "90", "--ignore-rules", "--source", "tool",
            "--provider", provider, "--model", model, "--toolsets", "terminal", "--query", prompt,
        ], capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print(json.dumps({"provider": provider, "model": model, "passed": False, "timeout": True}))
        return False
    events = []
    for line in result.stdout.splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                events.append(value)
        except ValueError:
            pass
    uses = [event for event in events if event.get("type") == "tool_use"]
    outputs = [event for event in events if event.get("type") == "tool_result"]
    finals = [event for event in events if event.get("type") == "result"]
    one_safe_call = (len(uses) == 1 and uses[0].get("name") == "terminal"
                     and isinstance(uses[0].get("input"), dict)
                     and uses[0]["input"].get("command") == COMMAND)
    tool_ok = len(outputs) == 1 and outputs[0].get("is_error") is False and MARKER in str(outputs[0].get("output", ""))
    final_ok = (len(finals) == 1 and finals[0].get("exit_code") == 0
                and isinstance(finals[0].get("text"), str) and finals[0]["text"].strip() == MARKER)
    passed = result.returncode == 0 and one_safe_call and tool_ok and final_ok
    print(json.dumps({"provider": provider, "model": model, "passed": passed,
                      "single_expected_terminal_call": one_safe_call, "tool_result_ok": tool_ok,
                      "final_marker_ok": final_ok, "exit": result.returncode}))
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex-model", required=True, help="Exact model from native enrollment/discovery")
    arguments = parser.parse_args()
    # Evaluate both checks rather than short-circuiting the second one.
    results = [check(provider, model) for provider, model in [
        ("custom:local-qwen", "qwen3.8-27b"), ("openai-codex", arguments.codex_model),
    ]]
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
