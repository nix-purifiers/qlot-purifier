# Preserve SBCL's raw saved image. Its GC timing fields are not reproducible;
# callers must not treat this artifact as a deterministic serialization.
{
  lib,
  sbcl,
  writeShellScriptBin,
  coreutils,
  python3,
}:
{
  project,
  environment,
  system,
  source,
  callbacks,
}:
let
  relative =
    value:
    builtins.isString value
    && value != ""
    && !(lib.hasPrefix "/" value)
    && builtins.all (part: part != ".." && part != "") (lib.splitString "/" value);
  symbol = value: builtins.isString value && builtins.match "[A-Za-z_][A-Za-z0-9_]*" value != null;
  string = value: "\"" + builtins.replaceStrings [ "\\" "\"" ] [ "\\\\" "\\\"" ] value + "\"";
  abiTypes = {
    int32_t = "(signed 32)";
    uint32_t = "(unsigned 32)";
    int64_t = "(signed 64)";
    uint64_t = "(unsigned 64)";
  };
  knownType = name: builtins.isString name && builtins.hasAttr name abiTypes;
  signature =
    callback:
    lib.concatStringsSep " " (map (name: abiTypes.${name}) ([ callback.result ] ++ callback.arguments));
  bindings = map (callback: ''
    (let* ((package (or (find-package ${string callback.package})
                        (error "Missing callback package")))
           (name (or (find-symbol ${string callback.symbol} package)
                     (error "Missing callback symbol"))))
      (unless (sb-alien:alien-callable-function name)
        (error "Not an original SBCL alien callable: ~S" name))
      (let* ((alien (sb-alien:alien-callable-function name))
             (index (sb-alien::alien-callback-index alien))
             (function (aref sb-alien::*alien-callback-functions* index))
             (definition (sb-introspect:definition-source-pathname
                           (sb-introspect:find-definition-source function)))
             (expected (truename (concatenate 'string
                         (sb-ext:posix-getenv "QLOT_PROJECT") "/source/" ${string source}))))
        (unless (and definition (equal (truename definition) expected))
          (error "Callback definition is outside declared authored source: ~S" name))
        (unless (equal (sb-alien-internals:unparse-alien-type
                         (sb-alien-internals:alien-value-type alien))
                       '(function ${signature callback} &rest))
          (error "Callback signature mismatch: ~S" name))
        (unless first (write-char #\, metadata))
        (setf first nil)
        (write-string "{\"alien\":" metadata)
        (qlot-json-string ${string callback.alien} metadata)
        (write-string ",\"source\":" metadata)
        (qlot-json-string (namestring definition) metadata)
        (write-string ",\"nativeType\":" metadata)
        (qlot-json-string (write-to-string
          (sb-alien-internals:unparse-alien-type
            (sb-alien-internals:alien-value-type alien))) metadata)
        (write-char #\} metadata))
      (push (list ${string callback.alien} name) exports))
  '') callbacks;
  inventory = builtins.path {
    path = ./asdf-inventory.lisp;
    name = "asdf-inventory.lisp";
  };
  observer = builtins.path {
    path = ./native-provenance.lisp;
    name = "native-provenance.lisp";
  };
  script = builtins.toFile "save-native-image.lisp" ''
    (require :asdf)
    (load ${string (toString inventory)})
    (load ${string (toString observer)})
    (qlot-native-start-observer)
    (load (concatenate 'string (sb-ext:posix-getenv "QLOT_PROJECT") "/setup.lisp"))
    (asdf:initialize-output-translations
      `(:output-translations
        (t ,(concatenate 'string (sb-ext:posix-getenv "out") "/fasl/"))
        :ignore-inherited-configuration))
    (ql:quickload ${string system} :silent t)
    (load (concatenate 'string (sb-ext:posix-getenv "QLOT_PROJECT") "/source/" ${string source}))
    (qlot-native-stop-observer)
    (qlot-native-write-events
      (concatenate 'string (sb-ext:posix-getenv "out") "/native-events.json"))
    (setf *qlot-native-events* nil)
    (qlot-asdf-inventory
      (concatenate 'string (sb-ext:posix-getenv "out") "/asdf-inventory.json"))
    (require :sb-introspect)
    (let ((exports nil))
      (with-open-file (metadata
          (concatenate 'string (sb-ext:posix-getenv "out") "/callback-inventory.json")
          :direction :output :if-exists :error)
        (write-char #\[ metadata)
        (let ((first t))
          ${lib.concatStringsSep "\n" bindings})
        (write-char #\] metadata))
      (sb-ext:save-lisp-and-die
        (concatenate 'string (sb-ext:posix-getenv "out") "/native.core")
        :callable-exports (nreverse exports)))
  '';
  verifier = builtins.path {
    path = ./verify-native-image.py;
    name = "verify-native-image.py";
  };
  identity = builtins.hashString "sha256" (
    toString script + toString project + toString sbcl + toString verifier
  );
  prepare = writeShellScriptBin "qlot-prepare-native-image" ''
    set -eu
    export PATH=${
      lib.makeBinPath [
        coreutils
        sbcl
      ]
    }
    if [ "$#" -ne 1 ]; then
      echo "Usage: qlot-prepare-native-image NEW_DIRECTORY" >&2
      exit 2
    fi
    out=$(realpath -m -- "$1")
    umask 077
    mkdir -- "$out"
    trap 'rm -rf -- "$out"' EXIT
    trap 'exit 1' HUP INT TERM
    export out QLOT_PROJECT=${project}
    export HOME="$out/.home" XDG_CACHE_HOME="$out/.cache"
    mkdir -p "$HOME" "$XDG_CACHE_HOME"
    ${generate}
    rm -rf -- "$HOME" "$XDG_CACHE_HOME"
    printf '%s\n' "${identity}" > "$out/identity"
    (
      cd "$out"
      sha256sum native.core asdf-inventory.json callback-inventory.json native-events.json verified-asdf.json identity > SHA256SUMS
    )
    trap - EXIT
    printf '%s\n' "$out/native.core"
  '';
  generate = ''
    test -f "$QLOT_PROJECT/source/"${lib.escapeShellArg source}
    source_root=$(realpath "$QLOT_PROJECT/source")
    authored_source=$(realpath "$QLOT_PROJECT/source/"${lib.escapeShellArg source})
    case "$authored_source" in "$source_root"/*) ;; *) echo "Foreign callback source" >&2; exit 1;; esac
    sbcl --noinform --no-userinit --no-sysinit --non-interactive --load ${script}
    test -s "$out/native.core"
    ${python3}/bin/python3 ${verifier} ${project} ${environment} ${sbcl} "$out"
  '';
in
assert lib.assertMsg (relative source) "nativeImage.source must be a relative authored file";
assert lib.assertMsg (callbacks != [ ]) "nativeImage.callbacks must not be empty";
assert lib.assertMsg (builtins.all (
  callback:
  builtins.attrNames callback == [
    "alien"
    "arguments"
    "package"
    "result"
    "symbol"
  ]
  && knownType callback.result
  && builtins.isList callback.arguments
  && builtins.all knownType callback.arguments
  && symbol callback.alien
  && builtins.isString callback.package
  && callback.package != ""
  && builtins.isString callback.symbol
  && callback.symbol != ""
) callbacks) "nativeImage.callbacks requires package, symbol and a C alien name";
assert lib.assertMsg (
  lib.length (lib.unique (map (callback: callback.alien) callbacks)) == lib.length callbacks
) "nativeImage callback C names must be unique";
{
  inherit prepare identity;
}
