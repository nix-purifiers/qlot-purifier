"""Activate immutable Quicklisp sources and FASLs for normal commands."""

import json
import os
from pathlib import Path
import sys

from .common import HERE, clean_env, load, native, run


def realize(root, companion, snapshot, target="environment"):
    state = root / ".qlot-purifier"
    state.mkdir(exist_ok=True)
    link = state / target
    run(
        [
            "nix",
            "build",
            "--impure",
            "--file",
            HERE / "nix/realize.nix",
            "--argstr",
            "project",
            root,
            "--argstr",
            "companion",
            companion,
            "--argstr",
            "snapshot",
            snapshot,
            "--argstr",
            "target",
            target,
            "--out-link",
            link,
        ],
        stdout=sys.stderr,
    )
    run(
        [
            "nix-store",
            "--add-root",
            state / "sdk",
            "--indirect",
            "--realise",
            os.environ["QLOT_PURIFIER_SDK"],
        ],
        stdout=sys.stderr,
    )
    return link.resolve()


def lisp_arguments(args, setup):
    # SBCL requires its runtime options before any Lisp options.
    values = {
        "--core",
        "--dynamic-space-size",
        "--control-stack-size",
        "--tls-limit",
        "--thread-stack-size",
    }
    flags = {
        "--noinform",
        "--help",
        "--version",
        "--disable-ldb",
        "--lose-on-corruption",
        "--end-runtime-options",
    }
    index = 0
    while index < len(args):
        if args[index] in values:
            index += 2
        elif args[index] in flags:
            index += 1
        else:
            break
    preloaded = any(
        args[i] == "--load" and Path(args[i + 1]).resolve() == setup
        for i in range(len(args) - 1)
    )
    injected = ["--no-userinit", "--no-sysinit"]
    if not preloaded:
        injected += ["--load", str(setup)]
    return args[:index] + injected + args[index:]


def execute(root, companion, snapshot, args, tool=None):
    if not companion.exists():
        print(
            "warning: no qlot-purifier lockfile; using ordinary impure resolution",
            file=sys.stderr,
        )
        command = [native(tool), *args] if tool else args
        os.execvpe(str(command[0]), [str(x) for x in command], os.environ.copy())
    load(root, companion, snapshot)
    environment = realize(root, companion, snapshot)
    state = root / ".qlot-purifier/session"
    env = clean_env(state)
    quicklisp = environment / "quicklisp"
    setup = quicklisp / "setup.lisp"
    string = lambda path: json.dumps(str(path) + "/", ensure_ascii=False)
    env["ASDF_OUTPUT_TRANSLATIONS"] = (
        f"(:output-translations ({string(quicklisp)} {string(environment / 'fasl')}) "
        f"(t ({string(state / 'cache')} :implementation)) :ignore-inherited-configuration)"
    )
    env["CL_SOURCE_REGISTRY"] = (
        '(:source-registry (:also-exclude ".qlot") (:also-exclude ".qlot-purifier") '
        f'(:also-exclude ".bundle-libs") (:tree {string(root)}) :ignore-inherited-configuration)'
    )
    env.update(
        {
            "QUICKLISP_HOME": str(quicklisp) + "/",
            "QLOT_PURIFIER_HOME": str(quicklisp) + "/",
            "QLOT_PURIFIER_SETUP": str(setup),
            "QLOT_PURIFIER_NATIVE_LOCK": str(environment / "qlfile.lock"),
            "QLOT_PURIFIER_FROZEN": "1",
            "QLOT_PURIFIER_PROJECT": str(root),
            "QLOT_PURIFIER_LOCK": str(companion),
            "QLOT_PURIFIER_SNAPSHOT": str(snapshot),
        }
    )
    env["PATH"] = os.environ["QLOT_PURIFIER_SDK"] + "/bin:" + env["PATH"]
    if (
        tool == "qlot"
        and args
        and args[0] in ("init", "add", "remove", "update", "outdated")
    ):
        raise ValueError(
            "This command changes resolution; edit qlfile and run qlot-purifier lock --update"
        )
    if tool == "sbcl":
        args = lisp_arguments(args, setup)
    command = [native(tool), *args] if tool else args
    os.execvpe(str(command[0]), [str(x) for x in command], env)
