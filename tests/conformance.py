"""Installed Qlot/SBCL wrappers, native tests, source lookup, and publication."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

repo = Path(__file__).resolve().parent.parent


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


run(["nix", "build", ".", "--out-link", "sdk"], cwd=repo)
sdk = (repo / "sdk").resolve()
with tempfile.TemporaryDirectory(prefix="qlot-conformance-") as temp:
    temp = Path(temp)
    root = temp / "project"
    shutil.copytree(
        repo / "examples/minimal",
        root,
        ignore=shutil.ignore_patterns(".qlot-purifier", ".qlot"),
    )
    # An existing ordinary Qlot installation must remain untouched.
    (root / ".qlot").mkdir()
    (root / ".qlot/preserve").write_text("ordinary installation")
    env = os.environ.copy()
    env["PATH"] = str(sdk / "bin") + ":" + env["PATH"]
    poison = temp / "poison"
    poison.mkdir()
    (poison / "yason.asd").write_text('(error "AMBIENT SOURCE USED")\n')
    env["CL_SOURCE_REGISTRY"] = str(poison) + "//"
    env["ASDF_OUTPUT_TRANSLATIONS"] = "/:" + str(poison)
    run(["qlot-purifier", "prefetch"], cwd=root, env=env)
    run(["qlot", "install"], cwd=root, env=env)
    run(["qlot", "check"], cwd=root, env=env)
    test = [
        "sbcl",
        "--noinform",
        "--non-interactive",
        "--eval",
        '(asdf:test-system "purifier-example")',
    ]
    run(test, cwd=root, env=env)
    child = run(
        ["qlot", "exec", *test], cwd=root, env=env, capture_output=True, text=True
    )
    assert "AMBIENT SOURCE USED" not in child.stderr
    native = run(
        ["qlot-purifier", "exec", "--", "env"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    active = dict(
        line.split("=", 1) for line in native.stdout.splitlines() if "=" in line
    )
    environment = Path(active["QLOT_PURIFIER_HOME"]).parent
    assert str(environment).startswith("/nix/store/")
    fasls = list((root / ".qlot-purifier/session/cache").rglob("*.fasl"))
    assert fasls and all(path.name == "example.fasl" for path in fasls), fasls
    assert list((environment / "fasl").rglob("*.fasl"))
    # SBCL's native definition source is what Lisp editors use for navigation.
    source = run(
        [
            "sbcl",
            "--noinform",
            "--non-interactive",
            "--eval",
            '(ql:quickload "yason" :silent t)',
            "--eval",
            "(require :sb-introspect)",
            "--eval",
            "(write-line (namestring (sb-introspect:definition-source-pathname (sb-introspect:find-definition-source (fdefinition (quote yason:encode))))))",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert str(environment / "quicklisp") in source.stdout, source
    app = root / "example.lisp"
    original = app.read_text()
    app.write_text(original.replace("42", "43"))
    os.utime(app, (time.time() + 2, time.time() + 2))
    failed = subprocess.run(test, cwd=root, env=env, capture_output=True, text=True)
    assert failed.returncode != 0 and "round trip failed" in failed.stderr, failed
    app.write_text(original)
    os.utime(app, (time.time() + 4, time.time() + 4))
    run(test, cwd=root, env=env)
    companion = root / "qlot-purifier.lock.json"
    snapshot = root / "qlfile.lock"
    before = companion.read_bytes(), snapshot.read_bytes()
    run(["qlot-purifier", "lock"], cwd=root, env=env)
    assert (companion.read_bytes(), snapshot.read_bytes()) == before
    external, external_native = temp / "external.json", temp / "qlfile.lock"
    companion.rename(external)
    snapshot.rename(external_native)
    selected = env | {
        "QLOT_PURIFIER_PROJECT": str(root),
        "QLOT_PURIFIER_LOCK": str(external),
        "QLOT_PURIFIER_SNAPSHOT": str(external_native),
    }
    run(["qlot", "exec", *test], cwd=root, env=selected)
    assert not companion.exists() and not snapshot.exists()
    external.rename(companion)
    external_native.rename(snapshot)
    extra = root / "new-system.asd"
    extra.write_text('(asdf:defsystem "new-system")\n')
    stale = subprocess.run(test, cwd=root, env=env, capture_output=True, text=True)
    assert stale.returncode != 0 and "inventory changed" in stale.stderr, stale
    extra.unlink()
    # Consume the published source with ordinary SBCL and the prepared repository.
    release = run(
        ["qlot-purifier", "release"], cwd=root, env=env, capture_output=True, text=True
    )
    artifact = Path(release.stdout.strip()) / "source.tar.gz"
    consumer = temp / "consumer"
    consumer.mkdir()
    with tarfile.open(artifact) as archive:
        archive.extractall(consumer, filter="data")
    ordinary = active.copy()
    ordinary["CL_SOURCE_REGISTRY"] = (
        f"(:source-registry (:tree {json.dumps(str(consumer / 'source') + '/')}) :ignore-inherited-configuration)"
    )
    result = run(
        [
            active["QLOT_PURIFIER_NATIVE_SBCL"],
            "--noinform",
            "--no-userinit",
            "--no-sysinit",
            "--non-interactive",
            "--load",
            environment / "quicklisp/setup.lisp",
            "--eval",
            '(asdf:test-system "purifier-example")',
        ],
        cwd=consumer,
        env=ordinary,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    fake = temp / "gh"
    fake.write_text(
        "#!/usr/bin/env python3\nimport os,pathlib,shutil,sys\n"
        "if sys.argv[1:3]==['release','view']:sys.exit(int(os.environ['FAKE_VIEW']))\n"
        "for a in sys.argv[3:]:\n p=pathlib.Path(a)\n if p.name=='source.tar.gz':shutil.copyfile(p,os.environ['FAKE_ARTIFACT'])\n"
    )
    fake.chmod(0o755)
    for exists in (False, True):
        copied = temp / ("uploaded.tgz" if exists else "created.tgz")
        run(
            ["qlot-purifier", "publish", "--repo", "fixture/project", "--tag", "v1"],
            cwd=root,
            env=env
            | {
                "QLOT_PURIFIER_GH": str(fake),
                "FAKE_VIEW": "0" if exists else "1",
                "FAKE_ARTIFACT": str(copied),
            },
        )
        assert copied.read_bytes() == artifact.read_bytes()
    assert (root / ".qlot/preserve").read_text() == "ordinary installation"
    assert list((root / ".qlot").iterdir()) == [root / ".qlot/preserve"]
    unlocked = temp / "unlocked"
    unlocked.mkdir()
    for tool, args in (
        ("qlot", ["--version"]),
        (
            "sbcl",
            [
                "--noinform",
                "--non-interactive",
                "--eval",
                "(write-line (read-line));",
                "--eval",
                "(sb-ext:exit :code 7)",
            ],
        ),
    ):
        baseline = subprocess.run(
            [active["QLOT_PURIFIER_NATIVE_" + tool.upper()], *args],
            cwd=unlocked,
            env=env,
            input=b"stdin survives\n",
            capture_output=True,
        )
        wrapped = subprocess.run(
            [tool, *args],
            cwd=unlocked,
            env=env,
            input=b"stdin survives\n",
            capture_output=True,
        )
        assert wrapped.returncode == baseline.returncode
        assert wrapped.stdout == baseline.stdout
        assert (
            wrapped.stderr
            == b"warning: no qlot-purifier lockfile; using ordinary impure resolution\n"
            + baseline.stderr
        )
print("Qlot/SBCL conformance passed")
