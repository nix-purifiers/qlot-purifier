"""Build a caller-authored ABI bridge against the unchanged SBCL runtime object."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

project, sdk, gcc, nm, specification, output = sys.argv[1:]
project, sdk, output = map(Path, (project, sdk, output))
spec = json.loads(Path(specification).read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def authored(name):
    root = (project / 'source').resolve()
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Bridge/header must belong to original project source')
    return path

bridge, header = authored(spec['bridge']), authored(spec['header'])
callback_source = authored(spec['callbackSource'])
original = {str(path): digest(path) for path in (bridge, header, callback_source)}
output.mkdir(parents=True, exist_ok=True)
(output / 'lib').mkdir()
(output / 'include').mkdir()
library = output / 'lib' / 'libapplication.so'
# Require every declared public symbol to be usable through the original header.
probe = output / 'header-check.c'
probe.write_text('#include ' + json.dumps(str(header)) + '\n' + '\n'.join(
    'void *check_' + name + '(void) { return (void *)&' + name + '; }'
    for name in spec['exports']))
subprocess.run([gcc, '-Werror', '-fsyntax-only', str(probe)], check=True)
probe.unlink()
translation = output / 'bridge-checked.c'
translation.write_text('#include ' + json.dumps(str(bridge)) + '\n#include ' + json.dumps(str(header)) + '\n')
with translation.open('a') as declarations:
    declarations.write('#include <stdint.h>\n')
    for callback in spec['callbacks']:
        arguments = ', '.join(callback['arguments']) or 'void'
        name = callback['alien']
        declarations.write(
            f"_Static_assert(__builtin_types_compatible_p(__typeof__({name}), "
            f"{callback['result']} (*)({arguments})), \"Callback slot signature mismatch\");\n"
        )
command = [gcc, '-shared', '-fPIC', '-o', str(library), str(translation),
           str(sdk / 'lib/sbcl/sbcl.o'),
           '-DSDK=' + json.dumps(str(sdk))]
command += ['-DQLOT_PREPARED_IDENTITY=' + json.dumps(spec['imageIdentity'])]
for root in spec['runtimeLibraries']:
    command += ['-L' + root + '/lib', '-Wl,-rpath,' + root + '/lib']
command += ['-ldl', '-lpthread', '-lzstd', '-lm']
subprocess.run(command, check=True)
translation.unlink()
symbols = subprocess.check_output([nm, '-D', '--defined-only', str(library)], text=True)
functions = {parts[-1] for line in symbols.splitlines()
             if len(parts := line.split()) >= 3 and parts[-2] in ('T', 'W')}
if not set(spec['exports']) <= functions:
    raise ValueError('Missing callable ABI exports')
storage = subprocess.check_output([nm, '-D', '-S', '--defined-only', str(library)], text=True)
slots = {parts[-1]: (int(parts[1], 16), parts[2])
         for line in storage.splitlines() if len(parts := line.split()) == 4}
for declaration in spec['callbacks']:
    callback = declaration['alien']
    size, kind = slots.get(callback, (0, ''))
    if size != struct.calcsize('P') or kind not in ('B', 'D'):
        raise ValueError('Callback must have pointer-sized native data storage: ' + callback)
for path, sha in original.items():
    if digest(Path(path)) != sha:
        raise ValueError('Authored bridge/header changed during compilation')
shutil.copyfile(header, output / 'include' / header.name)
metadata = {'schema': 1, 'project': str(project),
            'sdk': str(sdk), 'authoredSHA256': original,
            'runtimeObjectSHA256': digest(sdk / 'lib/sbcl/sbcl.o'),
            'originalSDKCoreSHA256': digest(sdk / 'lib/sbcl/sbcl.core'),
            'originalSDKExecutableSHA256': digest(sdk / 'bin/sbcl'),
            'imageIdentity': spec['imageIdentity'],
            'librarySHA256': digest(library), 'exports': spec['exports'],
            'runtimeContract': 'One image per process; same native thread; process lifetime; caller owns initialization, GC roots, exception containment and ABI conversions'}
(output / 'native-library.json').write_text(json.dumps(metadata, sort_keys=True) + '\n')
