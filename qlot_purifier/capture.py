"""Capture Qlot and ASDF's native dependency selection."""

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile

from .common import HERE, clean_env, input_files, load, native, run, versions


def sri(blob):
    return "sha256-" + base64.b64encode(hashlib.sha256(blob).digest()).decode()


def safe(value):
    if not re.fullmatch(r"[A-Za-z0-9_.+-]+", value) or value in (".", ".."):
        raise ValueError("Unsupported distribution name: " + value)
    return value


def capture(root, companion, snapshot, update=False, extra=()):
    previous = json.loads(companion.read_text()) if companion.exists() else None
    extra = list(extra or (previous or {}).get("extraInputs", []))
    if previous and not update:
        load(root, companion, snapshot)
        print("Retained " + str(companion))
        return
    names = input_files(root, extra)
    if companion == snapshot or any(
        path in {companion, snapshot} for path in (root / name for name in names)
    ):
        raise ValueError("Lock output paths must be distinct from project inputs")
    inputs = {
        name: {
            "content": (root / name).read_text(),
            "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest(),
        }
        for name in names
    }
    with tempfile.TemporaryDirectory(prefix="qlot-purifier-") as temp:
        temp = Path(temp)
        project = temp / "project"
        shutil.copytree(
            root,
            project,
            ignore=shutil.ignore_patterns(
                ".git",
                ".qlot",
                ".qlot-purifier",
                ".bundle-libs",
                "result*",
                "__pycache__",
            ),
        )
        local_lock = project / "qlfile.lock"
        if local_lock.exists():
            local_lock.unlink()
        if snapshot.exists():
            local_lock.write_bytes(snapshot.read_bytes())
        env = clean_env(temp)
        env["PATH"] = os.environ["QLOT_PURIFIER_TOOLCHAIN"] + "/bin:" + env["PATH"]
        env["QLOT_NO_TERMINAL"] = "1"
        graph = temp / "systems.txt"
        env["QLOT_PURIFIER_CAPTURE"] = str(graph)
        cache = temp / "native-cache"
        cache.mkdir()
        if update and snapshot.exists():
            run(
                [native("qlot"), "install", "--no-deps", "--cache", cache],
                cwd=project,
                env=env,
            )
            run([native("qlot"), "update", "--cache", cache], cwd=project, env=env)
        else:
            run([native("qlot"), "install", "--cache", cache], cwd=project, env=env)
        systems = sorted(set(graph.read_text().splitlines()))
        if any(not value or any(ord(c) < 32 for c in value) for value in systems):
            raise ValueError("Invalid native ASDF dependency name")
        exported = run(
            [
                native("sbcl"),
                "--noinform",
                "--no-userinit",
                "--no-sysinit",
                "--non-interactive",
                "--load",
                project / ".qlot/setup.lisp",
                "--load",
                HERE / "qlot_purifier/export.lisp",
            ],
            cwd=project,
            env=env,
            capture_output=True,
            text=True,
        )
        entries, dists, releases = [], [], []
        for line in exported.stdout.splitlines():
            fields = line.split("\t")
            if fields[0] == "DIST":
                _, name, version, directory = fields
                safe(name)
                directory = Path(directory)
                config = dict(
                    line.split(": ", 1)
                    for line in (directory / "distinfo.txt").read_text().splitlines()
                    if ": " in line
                )
                files = {}
                for filename, urlkey in (
                    ("distinfo.txt", "canonical-distinfo-url"),
                    ("releases.txt", "release-index-url"),
                    ("systems.txt", "system-index-url"),
                ):
                    blob = (directory / filename).read_bytes()
                    url = config.get(urlkey, "").replace("http://", "https://", 1)
                    if url.startswith("https://"):
                        path = f"metadata/{name}/{filename}"
                        entries.append(
                            {"path": path, "url": url, "hash": sri(blob), "mirrors": []}
                        )
                        files[filename] = {"path": path}
                    else:
                        files[filename] = {
                            "content": blob.decode(),
                            "sha256": hashlib.sha256(blob).hexdigest(),
                        }
                dists.append({"name": name, "version": version, "files": files})
            elif fields[0] == "CAPTURE":
                _, dist, name, url, archive = fields
                safe(dist)
                safe(name)
                archive = Path(archive)
                safe(archive.name)
                url = url.replace("http://", "https://", 1)
                if not url.startswith("https://"):
                    raise ValueError(
                        "This adapter currently supports HTTPS release archives: " + url
                    )
                path = f"archives/{dist}/{archive.name}"
                entries.append(
                    {
                        "path": path,
                        "url": url,
                        "hash": sri(archive.read_bytes()),
                        "mirrors": [],
                    }
                )
                releases.append(
                    {
                        "dist": dist,
                        "name": name,
                        "filename": archive.name,
                        "path": path,
                        "url": url,
                    }
                )
        native_text = local_lock.read_text()
        data = {
            "version": 1,
            "purifier": "qlot",
            "toolVersions": versions(),
            "inputs": inputs,
            "extraInputs": extra,
            "nativeLock": {
                "content": native_text,
                "sha256": hashlib.sha256(native_text.encode()).hexdigest(),
            },
            "dists": dists,
            "releases": releases,
            "systems": systems,
            "entries": sorted(entries, key=lambda item: item["path"]),
        }
        if (
            snapshot.resolve() in [root / name for name in names]
            or companion == snapshot
        ):
            raise ValueError("Lock output paths must be distinct from project inputs")
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        companion.parent.mkdir(parents=True, exist_ok=True)
        native_pending = snapshot.with_name(snapshot.name + ".tmp")
        pending = companion.with_name(companion.name + ".tmp")
        native_pending.write_text(native_text)
        pending.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        native_pending.replace(snapshot)
        pending.replace(companion)
    print(f"Locked {len(releases)} releases and {len(systems)} ASDF systems")
