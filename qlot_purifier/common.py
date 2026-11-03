"""Project identity and native SDK helpers."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

LOCK = "qlot-purifier.lock.json"
HERE = Path(__file__).resolve().parent.parent


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def native(tool):
    return os.environ["QLOT_PURIFIER_NATIVE_" + tool.upper()]


def versions():
    return {
        key.lower(): os.environ["QLOT_PURIFIER_" + key + "_VERSION"]
        for key in ("SDK", "SBCL", "QLOT", "GCC")
    }


def clean_env(home):
    env = os.environ.copy()
    for key in list(env):
        if key.startswith(
            ("CL_SOURCE_REGISTRY", "ASDF", "SBCL_HOME", "QUICKLISP", "QLOT_CALLER_")
        ) or key in (
            "QLOT_PURIFIER_HOME",
            "QLOT_PURIFIER_SETUP",
            "QLOT_PURIFIER_FROZEN",
            "QLOT_PURIFIER_NATIVE_LOCK",
            "QLOT_PURIFIER_CAPTURE",
            "QLOT_PURIFIER_PROJECT",
            "QLOT_PURIFIER_LOCK",
            "QLOT_PURIFIER_SNAPSHOT",
        ):
            env.pop(key)
    for key, leaf in (
        ("HOME", "home"),
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_CACHE_HOME", "cache"),
    ):
        path = home / leaf
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    return env


def input_files(root, extra=()):
    result = {"qlfile"}
    for path in root.rglob("*.asd"):
        relative = path.relative_to(root)
        if not any(
            part.startswith(".") or part in ("result", "__pycache__")
            for part in relative.parts
        ):
            result.add(str(relative))
    result.update(extra)
    for name in result:
        path = root / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.resolve() != path
            or not path.is_file()
        ):
            raise ValueError("Inputs must be regular files inside the project: " + name)
    return sorted(result)


def validate(root, data, snapshot):
    if data.get("version") != 1 or data.get("purifier") != "qlot":
        raise ValueError("Invalid qlot-purifier lock")
    if data.get("toolVersions") != versions():
        raise ValueError("Common Lisp SDK changed; run qlot-purifier lock --update")
    files = input_files(root, data.get("extraInputs", []))
    if files != sorted(data["inputs"]):
        raise ValueError(
            "ASDF system inventory changed; run qlot-purifier lock --update"
        )
    for name in files:
        value = data["inputs"][name]
        blob = (root / name).read_bytes()
        if (
            hashlib.sha256(blob).hexdigest() != value["sha256"]
            or blob.decode() != value["content"]
        ):
            raise ValueError(name + " changed; run qlot-purifier lock --update")
    if (
        not snapshot.is_file()
        or hashlib.sha256(snapshot.read_bytes()).hexdigest()
        != data["nativeLock"]["sha256"]
    ):
        raise ValueError(
            "qlfile.lock changed or is missing; run qlot-purifier lock --update"
        )


def locate():
    selected = os.environ.get("QLOT_PURIFIER_LOCK")
    if selected:
        companion = Path(selected).resolve()
        root = Path(os.environ.get("QLOT_PURIFIER_PROJECT", companion.parent)).resolve()
    else:
        root = next(
            (p for p in (Path.cwd(), *Path.cwd().parents) if (p / LOCK).exists()),
            Path.cwd(),
        )
        companion = root / LOCK
    snapshot = Path(
        os.environ.get("QLOT_PURIFIER_SNAPSHOT", root / "qlfile.lock")
    ).resolve()
    return root, companion, snapshot


def load(root, companion, snapshot):
    data = json.loads(companion.read_text())
    validate(root, data, snapshot)
    return data
