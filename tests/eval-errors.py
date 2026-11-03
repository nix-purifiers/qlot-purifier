"""Evaluation rejects stale and malformed locks without IFD."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory(prefix="qlot-evaluation-") as temp:
    root = Path(temp) / "project"
    shutil.copytree(repo / "examples/minimal", root)
    lock = root / "qlot-purifier.lock.json"
    original = lock.read_text()
    expression = (
        f"let flake = builtins.getFlake {json.dumps('path:' + str(repo))}; "
        f"in (flake.lib.qlot-purifier.readLock {{ src = /. + {json.dumps(str(root))}; }}).problems"
    )

    def problems():
        result = subprocess.run(
            [
                "nix",
                "eval",
                "--impure",
                "--option",
                "allow-import-from-derivation",
                "false",
                "--json",
                "--expr",
                expression,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    assert problems() == []
    for change in (
        lambda d: d.update(version=99),
        lambda d: d["entries"][0].update(path="../escape"),
        lambda d: d["entries"][0].update(hash="unhashed"),
        lambda d: d["nativeLock"].update(content="changed"),
        lambda d: d["inputs"]["qlfile"].update(content="changed"),
        lambda d: d["releases"][0].update(filename="../outside"),
    ):
        data = json.loads(original)
        change(data)
        lock.write_text(json.dumps(data))
        assert problems()
    lock.write_text(original)
    extra = root / "new-system.asd"
    extra.write_text('(asdf:defsystem "new-system")\n')
    assert problems()
    extra.unlink()
    (root / "qlfile.lock").write_text("changed")
    assert problems()
    lock.unlink()
    assert problems()
print("Qlot lock evaluation checks passed without IFD")
