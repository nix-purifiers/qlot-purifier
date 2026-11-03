"""Native Qlot pinning, updates, and empty dependency graphs."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
subprocess.run(["nix", "build", ".", "--out-link", "sdk"], cwd=repo, check=True)
sdk = (repo / "sdk").resolve()
env = os.environ.copy()
env["PATH"] = str(sdk / "bin") + ":" + env["PATH"]


def command(root, *args):
    subprocess.run(
        [str(sdk / "bin/qlot-purifier"), "--project", str(root), *args],
        check=True,
        env=env,
    )


with tempfile.TemporaryDirectory(prefix="qlot-native-capture-") as temp:
    root = Path(temp) / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".qlot", ".qlot-purifier"),
    )
    qlfile = root / "qlfile"
    qlfile.write_text("ql yason 2024-10-12\n")
    command(root, "lock", "--update")
    companion = root / "qlot-purifier.lock.json"
    data = json.loads(companion.read_text())
    old_version = next(d["version"] for d in data["dists"] if d["name"] == "yason")
    assert old_version == "ql-2024-10-12", data
    snapshot = root / "qlfile.lock"
    existing_native = snapshot.read_bytes()
    companion.unlink()
    command(root, "lock")
    assert snapshot.read_bytes() == existing_native
    assert (
        next(
            d["version"]
            for d in json.loads(companion.read_text())["dists"]
            if d["name"] == "yason"
        )
        == old_version
    )
    command(root, "prefetch")
    subprocess.run(
        [
            "sbcl",
            "--noinform",
            "--non-interactive",
            "--eval",
            '(asdf:test-system "purifier-example")',
        ],
        cwd=root,
        env=env,
        check=True,
    )
    qlfile.write_text("ql yason\n")
    command(root, "lock", "--update")
    updated = json.loads(companion.read_text())
    assert (
        next(d["version"] for d in updated["dists"] if d["name"] == "yason")
        != old_version
    )
    command(root, "prefetch")
    # Track definition helpers explicitly and preserve them on subsequent locks.
    (root / "version.txt").write_text("0.1.0\n")
    command(root, "lock", "--update", "--input", "version.txt")
    assert json.loads(companion.read_text())["extraInputs"] == ["version.txt"]
    command(root, "lock")
    qlfile.write_text("")
    definition = root / "purifier-example.asd"
    definition.write_text(
        definition.read_text().replace(':depends-on ("yason")', ":depends-on ()")
    )
    command(root, "lock", "--update")
    empty = json.loads(companion.read_text())
    assert empty["releases"] == [] and empty["systems"] == []
    command(root, "prefetch")
    subprocess.run(
        [
            "sbcl",
            "--noinform",
            "--non-interactive",
            "--eval",
            "(assert (find-package :asdf))",
        ],
        cwd=root,
        env=env,
        check=True,
    )
    missing = subprocess.run(
        [
            "sbcl",
            "--noinform",
            "--non-interactive",
            "--eval",
            '(ql:quickload "cl-ppcre" :silent t)',
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing.returncode != 0, missing
print("Native Qlot pin/update, explicit inputs, and empty graph passed")
