This fixture loads the original `purifier-example` ASDF system and its captured
Yason dependency. Its authored SBCL alien callback parses that system's JSON,
allocates storage, requests full GC, and returns an unsigned 32-bit sum. The
caller-authored bridge exports `native_init` and `native_answer` through the
unchanged `native.h` header.

Initialize exactly once before calling the callback. Calls must remain on the
initializing native thread. Keep the library, image and runtime loaded for the
process lifetime. The bridge promotes its own physical DSO to the global symbol
scope required by SBCL's original callable-export initialization and retains it
with `RTLD_NODELETE`. This reserves the process's SBCL runtime and signal handling;
it does not establish coexistence with another independently initialized SBCL
image. Lisp exceptions must be contained before crossing the C boundary. This
fixture returns only immediate unsigned integers; other argument/result ownership
and GC rooting remain the bridge author's responsibility.

Use the packaged preparation command to create the image in a new private
directory, then set `QLOT_NATIVE_IMAGE_DIR` before initialization. The image is
the raw output of SBCL's `save-lisp-and-die`. It includes variable GC timing
data and is created outside the reproducible Nix package.
