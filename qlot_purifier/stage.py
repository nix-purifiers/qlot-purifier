"""Stage captured metadata; Quicklisp performs archive installation itself."""

import json
from pathlib import Path
import shutil
import sys

manifest, client, sources, output = map(Path, sys.argv[1:])
data = json.loads(manifest.read_text())
quicklisp = output / "quicklisp"
shutil.copytree(client, quicklisp)
quicklisp.chmod(0o755)
for path in quicklisp.rglob("*"):
    path.chmod(0o755 if path.is_dir() else 0o644)
for index, dist in enumerate(data["dists"]):
    directory = quicklisp / "dists" / dist["name"]
    directory.mkdir(parents=True)
    for filename, value in dist["files"].items():
        if "path" in value:
            shutil.copyfile(sources / value["path"], directory / filename)
        else:
            (directory / filename).write_text(value["content"])
    (directory / "enabled.txt").touch()
    (directory / "preference.txt").write_text(str(index + 1))
for release in data["releases"]:
    target = quicklisp / "dists" / release["dist"] / "archives" / release["filename"]
    target.parent.mkdir(exist_ok=True)
    target.symlink_to(sources / release["path"])
for name in ("tmp", "local-projects", "local-init"):
    (quicklisp / name).mkdir(exist_ok=True)
(quicklisp / "local-projects/system-index.txt").touch()
(quicklisp / "local-init/purifier-offline.lisp").write_text("""
(defun purifier-refuse-network (url file &rest args)
  (declare (ignore file args))
  (error "URL is absent from the locked Quicklisp repository: ~A" url))
(setf ql-http:*fetch-scheme-functions*
      '(("http" . purifier-refuse-network) ("https" . purifier-refuse-network)))
""")
with (output / "install.lisp").open("w") as stream:
    for release in data["releases"]:
        stream.write(
            "(ql-dist:ensure-installed (ql-dist:find-release-in-dist "
            + json.dumps(release["name"])
            + " (ql-dist:find-dist "
            + json.dumps(release["dist"])
            + ")))\n"
        )
(output / "warm.lisp").write_text(
    "(ql:quickload '("
    + " ".join(json.dumps(name, ensure_ascii=False) for name in data["systems"])
    + ") :silent t)\n"
)
