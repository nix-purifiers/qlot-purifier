"""Verify the native installed release graph against the capture."""

import json
from pathlib import Path
import sys

data = json.loads(Path(sys.argv[1]).read_text())
actual_dists, actual_releases = {}, set()
for line in Path(sys.argv[2]).read_text().splitlines():
    fields = line.split("\t")
    if fields[0] == "DIST":
        actual_dists[fields[1]] = fields[2]
    elif fields[0] == "CAPTURE":
        actual_releases.add(
            (fields[1], fields[2], fields[3].replace("http://", "https://", 1))
        )
assert actual_dists == {d["name"]: d["version"] for d in data["dists"]}, (
    "Installed distributions differ from the native lock"
)
assert actual_releases == {
    (r["dist"], r["name"], r["url"]) for r in data["releases"]
}, "Installed releases differ from the capture"
