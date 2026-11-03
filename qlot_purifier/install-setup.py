"""Make a normal SBCL entry point for the installed ASDF project."""

import json
from pathlib import Path
import sys

output, environment = map(Path, sys.argv[1:])
quote = lambda path: json.dumps(str(path) + "/", ensure_ascii=False)
(output / "setup.lisp").write_text(
    "(require :asdf)\n"
    "(asdf:initialize-output-translations '(:output-translations "
    f"({quote(environment / 'quicklisp')} {quote(environment / 'fasl')}) "
    f"({quote(output / 'source')} {quote(output / 'fasl')}) :ignore-inherited-configuration))\n"
    f"(asdf:initialize-source-registry '(:source-registry (:tree {quote(output / 'source')}) :ignore-inherited-configuration))\n"
    f"(load {json.dumps(str(environment / 'quicklisp/setup.lisp'))})\n"
)
