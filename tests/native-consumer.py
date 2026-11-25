"""Ordinary Python FFI consumers for the original saved SBCL application."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys

library, expected, backend = sys.argv[1:]
expected = int(expected)
metadata = json.loads((Path(library).parent.parent / 'native-library.json').read_text())
assert hashlib.sha256(Path(library).read_bytes()).hexdigest() == metadata['librarySHA256']
if backend == 'ctypes':
    loaded = ctypes.CDLL(library, mode=os.RTLD_NOW | os.RTLD_NODELETE)
    loaded.native_answer.argtypes = [ctypes.c_uint32]
    loaded.native_answer.restype = ctypes.c_uint32
    assert loaded.native_init() == 0
    for value in [*range(100), 0xffffffff]:
        assert loaded.native_answer(value) == (value + expected) % (1 << 32)
    class DlInfo(ctypes.Structure):
        _fields_ = [('filename', ctypes.c_char_p), ('base', ctypes.c_void_p),
                    ('symbol', ctypes.c_char_p), ('address', ctypes.c_void_p)]
    host = ctypes.CDLL(None)
    host.dladdr.argtypes = [ctypes.c_void_p, ctypes.POINTER(DlInfo)]
    for name in ['native_answer', 'initialize_lisp']:
        info = DlInfo()
        assert host.dladdr(ctypes.cast(getattr(loaded, name), ctypes.c_void_p), ctypes.byref(info))
        assert Path(os.fsdecode(info.filename)).resolve() == Path(library).resolve()
elif backend == 'cffi':
    from cffi import FFI
    ffi = FFI()
    ffi.cdef('int native_init(void); uint32_t native_answer(uint32_t);')
    loaded = ffi.dlopen(library, flags=os.RTLD_NOW | os.RTLD_NODELETE)
    assert loaded.native_init() == 0
    for value in [*range(100), 0xffffffff]:
        assert loaded.native_answer(value) == (value + expected) % (1 << 32)
    ffi.dlclose(loaded)
    assert str(Path(library).resolve()) in Path('/proc/self/maps').read_text()
else:
    raise ValueError(backend)
print(backend + ': 100 allocating callbacks, full GC, overflow and native ownership PASS')
