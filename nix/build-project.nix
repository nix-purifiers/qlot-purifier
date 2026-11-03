{
  lib,
  runCommand,
  fetchgit,
  python3,
  writeText,
  purifier,
  nativeQlot,
  toolchain,
  sbcl,
  gcc,
  sdkVersion,
  findutils,
  coreutils,
  gnutar,
  gzip,
}:
{
  src,
  lockFile ? src + "/qlot-purifier.lock.json",
  snapshot ? src + "/qlfile.lock",
  fetchers ? { },
  nativeBuildInputs ? [ ],
  system ? lib.removeSuffix ".asd" (
    builtins.head (builtins.filter (lib.hasSuffix ".asd") (builtins.attrNames (builtins.readDir src)))
  ),
  buildCommand ?
    "sbcl --noinform --no-userinit --no-sysinit --non-interactive --load \"$out/setup.lisp\" --eval "
    + lib.escapeShellArg "(ql:quickload ${builtins.toJSON system} :silent t)",
  checkCommand ?
    "sbcl --noinform --no-userinit --no-sysinit --non-interactive --load \"$out/setup.lisp\" --eval "
    + lib.escapeShellArg "(asdf:test-system ${builtins.toJSON system})",
  installCommand ? "",
  doCheck ? true,
  srcFilter ?
    path: type:
    !(builtins.elem (baseNameOf path) [
      ".git"
      ".qlot"
      ".qlot-purifier"
      ".bundle-libs"
      "result"
      "__pycache__"
    ]),
}:
let
  lock = purifier.checkLock (
    import ./read-lock.nix { inherit lib; } { inherit src lockFile snapshot; }
  );
  environment = import ./environment.nix {
    inherit
      lib
      runCommand
      fetchgit
      python3
      writeText
      purifier
      nativeQlot
      toolchain
      sbcl
      gcc
      sdkVersion
      findutils
      coreutils
      ;
  } { inherit lock fetchers nativeBuildInputs; };
  source = lib.cleanSourceWith {
    inherit src;
    filter = srcFilter;
  };
  project =
    runCommand "purified-common-lisp-project"
      {
        nativeBuildInputs = [
          toolchain
          python3
        ]
        ++ nativeBuildInputs;
      }
      ''
        export PATH=${toolchain}/bin:$PATH HOME="$TMPDIR/home" XDG_CACHE_HOME="$TMPDIR/cache"
        mkdir -p "$HOME" "$out/source"
        cp -pr ${source}/. "$out/source/"
        chmod -R u+w "$out/source"
        python3 ${../qlot_purifier/install-setup.py} "$out" ${environment}
        cd "$out/source"
        ${buildCommand}
        ${lib.optionalString doCheck checkCommand}
        ${installCommand}
      '';
  release =
    runCommand "common-lisp-project-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        set -o pipefail
        mkdir -p "$out" source
        cp -r ${source}/. source/
        chmod -R u+w source
        cp ${lockFile} source/qlot-purifier.lock.json
        cp ${snapshot} source/qlfile.lock
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -cf - source | gzip -n > "$out/source.tar.gz"
      '';
in
assert lock.problems == [ ];
assert lib.assertMsg (
  lock.data.toolVersions == {
    sdk = sdkVersion;
    sbcl = sbcl.version;
    qlot = nativeQlot.version;
    gcc = gcc.version;
  }
) "Common Lisp SDK changed; run qlot-purifier lock --update";
{
  packages = {
    default = project;
    inherit project environment;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
