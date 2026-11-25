"""Causal native compiler/SDK controls using the actual owning project API."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
configuration = '''nativeImage = {
 source="native-export.lisp";bridge="bridge.c";header="native.h";
 initialize="native_init";exports=["native_init" "native_answer"];
 callbacks=[{package="COMMON-LISP-USER";symbol="NATIVE-ANSWER";alien="native_answer_cb";result="uint32_t";arguments=["uint32_t"];}];
};'''

with tempfile.TemporaryDirectory(prefix='qlot-native-controls-') as directory:
    directory = Path(directory)
    for case, expected in [
        ('ordinary-function', 'Not an original SBCL alien callable'),
        ('foreign-definition', 'outside declared authored source'),
        ('lisp-signature', 'Callback signature mismatch'),
        ('c-slot-signature', 'Callback slot signature mismatch'),
        ('prebuilt-project-fasl', 'Prebuilt project FASL was loaded'),
        ('foreign-direct-load', 'Foreign SBCL LOAD outside owned roots'),
        ('header-conflict', 'conflicting types'),
        ('hidden-callback-storage', 'pointer-sized native data storage'),
    ]:
        source = directory / case
        shutil.copytree(root / 'examples/native-callable', source)
        if case == 'ordinary-function':
            (source / 'native-export.lisp').write_text('(defun native-answer (value) value)\n')
        elif case == 'foreign-definition':
            shutil.copyfile(source / 'native-export.lisp', source / 'other.lisp')
            (source / 'native-export.lisp').write_text(
                '(load (merge-pathnames "other.lisp" *load-truename*))\n')
        elif case == 'lisp-signature':
            source_file = source / 'native-export.lisp'
            source_file.write_text(source_file.read_text().replace(
                '((value sb-alien:unsigned-int))', '((value sb-alien:unsigned-long))'))
        elif case == 'c-slot-signature':
            bridge = source / 'bridge.c'
            bridge.write_text(bridge.read_text().replace(
                '(*native_answer_cb)(uint32_t)', '(*native_answer_cb)(uint64_t)'))
        elif case == 'prebuilt-project-fasl':
            with (source / 'native-export.lisp').open('a') as callback:
                callback.write(
                    '\n(load (concatenate \'string (sb-ext:posix-getenv "QLOT_PROJECT")'
                    ' "/fasl/example.fasl"))\n')
        elif case == 'foreign-direct-load':
            with (source / 'native-export.lisp').open('a') as callback:
                callback.write('''
(let ((path (merge-pathnames "foreign.lisp" (uiop:temporary-directory))))
  (with-open-file (stream path :direction :output :if-exists :supersede)
    (write-line "(values)" stream))
  (load path))
''')
        elif case == 'header-conflict':
            header = source / 'native.h'
            header.write_text(header.read_text().replace(
                'native_answer(uint32_t)', 'native_answer(uint64_t)'))
        else:
            bridge = source / 'bridge.c'
            bridge.write_text(bridge.read_text().replace(
                'uint32_t (*native_answer_cb)', 'static uint32_t (*native_answer_cb)'))
        expression = '''let
 f = builtins.getFlake %s;
 system = builtins.currentSystem;
 p = import f.inputs.nixpkgs {inherit system;overlays=[f.overlays.default];};
 product = p.qlot-purifier.buildQlotProject {src = builtins.toPath %s; %s};
 in product.packages.native-library
''' % (json.dumps('path:' + str(root)), json.dumps(str(source)), configuration)
        command = ['nix', 'build', '--impure', '--expr', expression, '--no-link', '-L']
        if case in {'ordinary-function', 'foreign-definition', 'lisp-signature',
                    'prebuilt-project-fasl', 'foreign-direct-load'}:
            prepare = subprocess.check_output(
                ['nix', 'build', '--impure', '--expr',
                 expression.replace('in product.packages.native-library',
                                    'in product.packages.prepare-native-image'),
                 '--no-link', '--print-out-paths'], text=True
            ).strip()
            destination = directory / 'rejected-image'
            command = [str(Path(prepare) / 'bin/qlot-prepare-native-image'),
                       str(destination)]
            result = subprocess.run(command, capture_output=True, text=True)
            assert not destination.exists()
        else:
            result = subprocess.run(command, capture_output=True, text=True)
        if not result.returncode or expected not in result.stderr:
            raise AssertionError(case + '\n' + result.stdout + result.stderr)
        print(case + ': rejected by original SDK/compiler/ownership check', flush=True)
