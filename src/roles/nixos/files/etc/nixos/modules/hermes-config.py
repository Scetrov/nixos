"""Reconcile only deployment-owned Hermes model fields and the local provider.

Inputs contain no resolved secrets. Credentials stay in the runtime environment;
this program never writes them to config.yaml or reports input values in errors.
"""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import urlsplit

import yaml


PROVIDER = "local-qwen"


def environment(path):
    values = {}
    if path is not None:
        for line in Path(path).read_text().splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise ValueError("invalid environment file")
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key] = value
    return values


def model_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:/+-]+", value):
        raise ValueError("invalid model id")
    return value


def endpoint(value):
    if not isinstance(value, str) or any(char.isspace() for char in value):
        raise ValueError("invalid endpoint")
    url = urlsplit(value)
    if (url.scheme not in {"http", "https"} or not url.hostname or url.username
            or url.password or url.query or url.fragment):
        raise ValueError("endpoint must be an HTTP(S) URL without credentials or query")
    # Validate the port without exposing the URL on failure.
    url.port
    return value


def atomic_write(path, content, uid, gid):
    fd, name = tempfile.mkstemp(prefix=".hermes-config-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            os.fchmod(stream.fileno(), 0o600)
            os.fchown(stream.fileno(), uid, gid)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def reconcile(home, webui_env, settings, env, uid, gid):
    config_path = home / "config.yaml"
    ownership_path = home / ".nixos-managed-providers.json"
    # Refuse indirection into unrelated state, including native credential files.
    for path in (config_path, ownership_path, webui_env):
        if path.is_symlink():
            raise ValueError("managed output must not be a symlink")
    config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
    if not isinstance(config, dict):
        raise ValueError("config.yaml must be a mapping")
    model = config.get("model", {})
    providers = config.get("providers", {})
    if not isinstance(model, dict) or not isinstance(providers, dict):
        raise ValueError("model and providers must be mappings")
    previous = json.loads(ownership_path.read_text()) if ownership_path.exists() else {}
    if not isinstance(previous, dict) or set(previous) - {PROVIDER}:
        raise ValueError("invalid managed-provider ownership record")

    default = model_id(env.get(settings["modelEnvVar"]) or settings["defaultModel"])
    provider = model_id(settings["provider"])
    base_url = settings["baseUrl"]
    if base_url:
        endpoint(base_url)
    local = settings["localQwen"]
    desired = {}
    if local["enable"]:
        entry = {
            "api": endpoint(local["baseUrl"]),
            "default_model": model_id(local["model"]),
            "models": {model_id(local["model"]): {}},
            "transport": "chat_completions",
        }
        context = local["contextLength"]
        if context is not None:
            if type(context) is not int or context <= 0:
                raise ValueError("context length must be a positive integer")
            entry["models"][local["model"]]["context_length"] = context
        if local["requireApiKey"]:
            if not env.get("HERMES_LOCAL_QWEN_API_KEY", "").strip():
                raise ValueError("local Qwen requires HERMES_LOCAL_QWEN_API_KEY in the runtime environment file")
            entry["key_env"] = "HERMES_LOCAL_QWEN_API_KEY"
        desired[PROVIDER] = entry

    current = providers.get(PROVIDER)
    # Identical desired data can be adopted after an interrupted sidecar write.
    if current is not None and current != previous.get(PROVIDER) and current != desired.get(PROVIDER):
        raise ValueError("local-qwen conflicts with unmanaged or edited provider; resolve ownership before retrying")
    if provider in {PROVIDER, "custom:" + PROVIDER} and not local["enable"]:
        raise ValueError("cannot select disabled local Qwen as default")
    if PROVIDER in previous or PROVIDER in desired:
        providers.pop(PROVIDER, None)
    providers.update(desired)
    if providers or "providers" in config:
        config["providers"] = providers
    model.update(default=default, provider=provider, base_url=base_url)
    config["model"] = model
    initial_model = default if provider == "openrouter" else f"@{provider}:{default}"
    # Serialize and validate everything before replacing any existing file.
    serialized = yaml.safe_dump(config, sort_keys=False)
    if yaml.safe_load(serialized) != config:
        raise ValueError("configuration did not round trip")
    outputs = (
        (config_path, serialized),
        (ownership_path, json.dumps(desired, sort_keys=True) + "\n"),
        (webui_env, "HERMES_WEBUI_DEFAULT_MODEL=" + initial_model + "\n"),
    )
    for path, content in outputs:
        # Podman reads webui.env as the host service user (namespace root in
        # rootless setup), not as the container's mapped runtime UID.
        owner, group = (os.geteuid(), os.getegid()) if path == webui_env else (uid, gid)
        atomic_write(path, content, owner, group)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--settings", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--webui-env", type=Path, required=True)
    parser.add_argument("--environment", type=Path)
    parser.add_argument("--uid", type=int, required=True)
    parser.add_argument("--gid", type=int, required=True)
    args = parser.parse_args()
    try:
        reconcile(args.home, args.webui_env, json.loads(args.settings.read_text()),
                  environment(args.environment), args.uid, args.gid)
    except (OSError, ValueError, TypeError, KeyError, yaml.YAMLError):
        print("Hermes configuration reconciliation failed: check YAML mappings, managed-provider ownership, "
              "endpoint/model settings, required runtime key and output permissions. Input values redacted.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
