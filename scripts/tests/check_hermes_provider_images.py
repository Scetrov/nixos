"""Check generated provider discovery/routing in the pinned images.

Uses synthetic state, credentials and endpoint only. WebUI startup needs network
access for its existing dependency bootstrap. No host ports or production state
are exposed. Disposable containers and the test-owned volume are always removed.
This is not a real inference, OAuth enrollment, or browser acceptance test.
"""

from pathlib import Path
import re
import subprocess
import time
import uuid


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "src/roles/nixos/files/etc/nixos/modules"


def run(arguments, **kwargs):
    return subprocess.run(["podman", *arguments], capture_output=True, text=True, check=True, **kwargs)


def fixture(authenticated=True):
    source = (MODULE / "hermes-config.py").read_text()
    # Source only is passed on stdin; no directory or operator credential mounts.
    return f"""
import os, types
from pathlib import Path
module = types.ModuleType('hermes_config')
exec(compile({source!r}, 'hermes-config.py', 'exec'), module.__dict__)
home = Path(os.environ['HERMES_HOME'])
home.mkdir(parents=True, exist_ok=True)
settings = {{
    'defaultModel': 'existing/model', 'modelEnvVar': 'HERMES_DEFAULT_MODEL',
    'provider': 'openrouter', 'baseUrl': 'https://openrouter.ai/api/v1',
    'localQwen': {{'enable': True, 'baseUrl': 'http://qwen.invalid:8000/v1',
                   'model': 'synthetic-qwen', 'contextLength': 65536, 'requireApiKey': {authenticated!r}}},
}}
if {authenticated!r}:
    os.environ['HERMES_LOCAL_QWEN_API_KEY'] = 'synthetic-local-key'
else:
    os.environ.pop('HERMES_LOCAL_QWEN_API_KEY', None)
module.reconcile(home, home / 'fixture-webui.env', settings, dict(os.environ), os.getuid(), os.getgid())
from hermes_cli.runtime_provider import resolve_runtime_provider
rt = resolve_runtime_provider(requested='custom:local-qwen', target_model='synthetic-qwen')
assert rt['base_url'] == settings['localQwen']['baseUrl']
if {authenticated!r}:
    assert rt['api_key'] == 'synthetic-local-key'
else:
    assert 'key_env' not in (module.yaml.safe_load((home / 'config.yaml').read_text())['providers']['local-qwen'])
    assert rt['api_key'] != 'synthetic-local-key'
assert 'synthetic-local-key' not in (home / 'config.yaml').read_text()
print('PASS: generated named-provider route and environment credential')
if os.environ.get('CHECK_WEBUI'):
    import api.config as c
    key, url = c.resolve_custom_provider_connection('custom:local-qwen')
    assert url == settings['localQwen']['baseUrl']
    assert key == 'synthetic-local-key' if {authenticated!r} else not key
    assert c.model_with_provider_context('synthetic-qwen', 'custom:local-qwen') == '@custom:local-qwen:synthetic-qwen'
    assert 'synthetic-qwen' in str(c.get_available_models())
    assert c.model_with_provider_context('synthetic-codex-model', 'openai-codex') == '@openai-codex:synthetic-codex-model'
    print('PASS: WebUI catalog, explicit local selection and Codex provider context')
"""


def main():
    host = (ROOT / "src/roles/nixos/files/device-configuration/habiki.nix").read_text()
    module = (MODULE / "hermes.nix").read_text()
    agent = re.search(r'agentImage = "([^"]+)"', host).group(1)
    webui = re.search(r'default = "(ghcr.io/nesquena/hermes-webui:[^"]+)"', module).group(1)
    for image in (agent, webui):
        if "@sha256:" not in image:
            raise ValueError("Provider image checks require digest pins")
    name = "hermes-provider-check-" + uuid.uuid4().hex
    volume = name + "-source"
    try:
        run(["volume", "create", volume])
        result = run([
            "run", "--rm", "--network=none", "--cap-drop=ALL", "--security-opt=no-new-privileges",
            "--env", "HERMES_HOME=/tmp/provider-check", "--volume", volume + ":/opt/hermes",
            "--entrypoint", "python", "-i", agent, "-",
        ], input=fixture(), timeout=90)
        print(result.stdout.strip())
        run([
            "run", "-d", "--name", name, "--security-opt=no-new-privileges",
            "--volume", volume + ":/home/hermeswebui/.hermes/hermes-agent:ro",
            "--env", "WANTED_UID=1000", "--env", "WANTED_GID=1000",
            "--env", "HERMES_WEBUI_HOST=127.0.0.1",
            "--env", "HERMES_WEBUI_STATE_DIR=/home/hermeswebui/.hermes/webui", webui,
        ])
        for _ in range(90):
            time.sleep(3)
            health = subprocess.run([
                "podman", "exec", name, "/app/venv/bin/python", "-c",
                'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8787/health", timeout=2)',
            ], capture_output=True, timeout=10)
            if health.returncode == 0:
                break
            if run(["inspect", "--format", "{{.State.Running}}", name]).stdout.strip() != "true":
                raise RuntimeError("Disposable WebUI exited during bootstrap")
        else:
            raise RuntimeError("Disposable WebUI bootstrap timed out")
        result = run([
            "exec", "-i", "--user", "1000:1000", "--workdir", "/app",
            "--env", "CHECK_WEBUI=1", "--env", "HERMES_HOME=/home/hermeswebui/.hermes",
            name, "/app/venv/bin/python", "-",
        ], input=fixture(), timeout=90)
        print(result.stdout.strip())
        result = run([
            "exec", "-i", "--user", "1000:1000", "--workdir", "/app",
            "--env", "CHECK_WEBUI=1", "--env", "HERMES_HOME=/home/hermeswebui/.hermes",
            name, "/app/venv/bin/python", "-",
        ], input=fixture(authenticated=False), timeout=90)
        print("Keyless endpoint:")
        print(result.stdout.strip())
    finally:
        subprocess.run(["podman", "rm", "-f", name], capture_output=True, check=False)
        subprocess.run(["podman", "volume", "rm", volume], capture_output=True, check=False)


if __name__ == "__main__":
    main()
