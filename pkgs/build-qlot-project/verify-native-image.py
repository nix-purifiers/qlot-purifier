"""Verify that the original SDK compiled and loaded the selected ASDF files."""
import hashlib
import json
from pathlib import Path
import sys

project, environment, sdk, image = map(Path, sys.argv[1:])


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


roots = [(project / 'source').resolve(), (project / 'fasl').resolve(),
         environment.resolve(), sdk.resolve()]
inventory = json.loads((image / 'asdf-inventory.json').read_text())
if not inventory:
    raise ValueError('Native ASDF inventory must not be empty')
events = json.loads((image / 'native-events.json').read_text())
compiled = {(row['input'], row['inputSHA256'], row['outputSHA256'])
            for row in events if row['operation'] == 'COMPILE-FILE'}
loaded = {(row['input'], row['inputSHA256'])
          for row in events if row['operation'] == 'LOAD'}
fresh_root = (image / 'fasl').resolve()
observed = []
verified_fasls = 0
for row in inventory:
    files = [row['source'], *(name for name in row['outputs'] if Path(name).is_file())]
    missing = set(row['outputs']) - set(files[1:])
    bootstrap_root = (environment / 'quicklisp/quicklisp').resolve()
    if missing and not (row['system'] == 'quicklisp'
                        and Path(row['source']).is_relative_to(bootstrap_root)):
        raise ValueError('Missing ASDF compiled output: ' + ', '.join(sorted(missing)))
    hashes = {}
    for filename in files:
        path = Path(filename).resolve(strict=True)
        if not path.is_file() or not any(path.is_relative_to(root) for root in [*roots, fresh_root]):
            raise ValueError('Foreign ASDF source/compiled output: ' + filename)
        hashes[str(path)] = digest(path)
    for filename in files[1:]:
        fasl = Path(filename).resolve(strict=True)
        source = Path(row['source']).resolve(strict=True)
        if not fasl.is_relative_to(fresh_root):
            raise ValueError('ASDF output outside fresh image cache: ' + filename)
        if ((str(source), hashes[str(source)], hashes[str(fasl)]) not in compiled
                or (str(fasl), hashes[str(fasl)]) not in loaded):
            raise ValueError('Missing native compile/load provenance: ' + filename)
        verified_fasls += 1
    observed.append({**row, 'verifiedOutputs': files[1:], 'sha256': hashes})

compile_hashes = {entry[2] for entry in compiled}
for filename, sha in loaded:
    path = Path(filename)
    if path.is_relative_to((project / 'fasl').resolve()):
        raise ValueError('Prebuilt project FASL was loaded: ' + filename)
    if path != (project / 'setup.lisp').resolve() and not any(
        path.is_relative_to(root) for root in [*roots, fresh_root]
    ):
        raise ValueError('Foreign SBCL LOAD outside owned roots: ' + filename)
    if digest(path) != sha:
        raise ValueError('Observed SBCL LOAD bytes changed: ' + filename)
    if path.is_relative_to(fresh_root):
        if sha not in compile_hashes:
            raise ValueError('Missing native compile/load provenance: ' + filename)

if not verified_fasls:
    raise ValueError('Native ASDF compilation must produce loaded FASLs')

(image / 'verified-asdf.json').write_text(json.dumps(observed, sort_keys=True) + '\n')
