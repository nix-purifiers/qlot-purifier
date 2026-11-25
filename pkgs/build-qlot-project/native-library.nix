{
  lib,
  runCommand,
  writeText,
  python3,
  gcc,
  sbcl,
}:
{
  project,
  image,
  callbacks,
  callbackSource,
  bridge,
  header,
  initialize,
  exports,
}:
let
  relative =
    value:
    builtins.isString value
    && value != ""
    && !(lib.hasPrefix "/" value)
    && builtins.all (part: part != ".." && part != "") (lib.splitString "/" value);
  symbol = value: builtins.isString value && builtins.match "[A-Za-z_][A-Za-z0-9_]*" value != null;
  runtimeLibraries = map (package: toString (package.lib or package.out)) sbcl.buildInputs;
  specification = writeText "sbcl-native-library.json" (
    builtins.toJSON {
      inherit callbacks callbackSource;
      imageIdentity = image.identity;
      inherit
        bridge
        header
        initialize
        exports
        runtimeLibraries
        ;
    }
  );
in
assert lib.assertMsg (
  relative bridge && relative header
) "nativeImage bridge/header must be relative authored files";
assert lib.assertMsg (
  symbol initialize && builtins.all symbol exports && builtins.elem initialize exports
) "nativeImage requires an exported C initializer and valid C export names";
assert lib.assertMsg (
  lib.length (lib.unique exports) == lib.length exports
) "nativeImage exports must be unique";
runCommand "common-lisp-native-library"
  {
    nativeBuildInputs = [
      python3
      gcc
    ];
    passthru = { inherit project image sbcl; };
  }
  ''
    ${python3}/bin/python3 ${./native-library.py} ${project} ${sbcl} \
      ${gcc}/bin/gcc ${gcc.bintools}/bin/nm ${specification} "$out"
  ''
