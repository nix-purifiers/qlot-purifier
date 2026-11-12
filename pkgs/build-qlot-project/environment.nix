{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  toolchain,
  nativeQlot,
  sbcl,
  gcc,
  sdkVersion,
  findutils,
  coreutils,
}:
{
  lock,
  fetchers ? { },
  nativeBuildInputs ? [ ],
}:
let
  checked = purifier.checkLock lock;
  sources = purifier.tree (
    {
      name = "locked-quicklisp-sources";
      entries = checked.entries;
      inherit
        runCommand
        fetchgit
        python3
        writeText
        ;
    }
    // fetchers
  );
  manifest = writeText "qlot-capture.json" (builtins.toJSON checked.data);
  snapshot = writeText "qlfile.lock" checked.nativeSnapshot;
in
assert checked.problems == [ ];
assert lib.assertMsg (
  checked.data.toolVersions == {
    sdk = sdkVersion;
    sbcl = sbcl.version;
    qlot = nativeQlot.version;
    gcc = gcc.version;
  }
) "Common Lisp SDK changed; run qlot-purifier lock --update";
runCommand "purified-qlot-environment"
  {
    nativeBuildInputs = [
      toolchain
      python3
      findutils
      coreutils
    ]
    ++ nativeBuildInputs;
  }
  ''
    export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home" XDG_CACHE_HOME="$TMPDIR/cache"
    mkdir -p "$out" "$HOME"
    python3 ${../../qlot_purifier/stage.py} ${manifest} ${nativeQlot.source}/quicklisp-client ${sources} "$out"
    sbcl --noinform --no-userinit --no-sysinit --non-interactive --load "$out/quicklisp/setup.lisp" --load "$out/install.lisp"
    sbcl --noinform --no-userinit --no-sysinit --non-interactive --load "$out/quicklisp/setup.lisp" --load ${../../qlot_purifier/export.lisp} > "$TMPDIR/installed.tsv"
    python3 ${../../qlot_purifier/check-installed.py} ${manifest} "$TMPDIR/installed.tsv"
    find "$out/quicklisp" -type f -exec touch -h -d @1 {} +
    export ASDF_OUTPUT_TRANSLATIONS="(:output-translations (\"$out/quicklisp/\" \"$out/fasl/\") :ignore-inherited-configuration)"
    sbcl --noinform --no-userinit --no-sysinit --non-interactive --load "$out/quicklisp/setup.lisp" --load "$out/warm.lisp"
    cp ${manifest} "$out/capture.json"
    cp ${snapshot} "$out/qlfile.lock"
    ln -s ${sources} "$out/sources"
  ''
