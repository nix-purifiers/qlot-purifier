from pathlib import Path
import sys

root = Path(sys.argv[1])
p = root / "src/cli.lisp"
s = p.read_text()
if "QLOT_PURIFIER_HOME" in s:
    sys.exit(0)
needle = "(defun main ()\n"
assert needle in s
s = s.replace(
    needle,
    needle
    + """  (when (uiop:getenvp "QLOT_PURIFIER_HOME")
    (setf qlot/utils/project:*qlot-directory*
          (uiop:ensure-directory-pathname (uiop:getenv "QLOT_PURIFIER_HOME"))))
""",
)
s = s.replace(
    '(list "--load" ".qlot/setup.lisp")',
    '(list "--load" (or (uiop:getenvp "QLOT_PURIFIER_SETUP") ".qlot/setup.lisp"))',
)
needle = "(defun qlot-command-install (argv)\n"
assert needle in s
s = s.replace(
    needle,
    needle
    + """  (when (uiop:getenvp "QLOT_PURIFIER_FROZEN")
    (ensure-package-loaded :qlot/check)
    (return-from qlot-command-install
      (uiop:symbol-call :qlot/check :check-project *default-pathname-defaults*)))
""",
)
p.write_text(s)
p = root / "src/parser.lisp"
s = p.read_text()
needle = "(defun find-lock (qlfile)\n"
assert needle in s
s = s.replace(
    needle,
    needle
    + """  (when (uiop:getenvp "QLOT_PURIFIER_NATIVE_LOCK")
    (return-from find-lock (pathname (uiop:getenv "QLOT_PURIFIER_NATIVE_LOCK"))))
""",
)
p.write_text(s)

p = root / "src/utils/project.lisp"
s = p.read_text()
needle = "(merge-pathnames *qlot-directory* project-root)"
assert needle in s
s = s.replace(
    needle,
    '(if (uiop:getenvp "QLOT_PURIFIER_HOME") (uiop:ensure-directory-pathname (uiop:getenv "QLOT_PURIFIER_HOME")) '
    + needle
    + ")",
)
p.write_text(s)

p = root / "src/install.lisp"
s = p.read_text()
needle = "      (with-package-functions #:ql-dist (ensure-installed release name)\n        (let ((releases"
assert needle in s
s = s.replace(
    needle,
    '      (with-package-functions #:ql-dist (ensure-installed release name)\n        (when (uiop:getenvp "QLOT_PURIFIER_CAPTURE")\n          (with-open-file (out (uiop:getenv "QLOT_PURIFIER_CAPTURE")\n                               :direction :output :if-exists :supersede)\n            (dolist (system all-dependencies)\n              (format out "~A~%" (name system)))))\n        (let ((releases',
)
p.write_text(s)
