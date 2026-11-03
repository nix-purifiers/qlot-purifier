{
  sbclPackages,
  sbcl,
  python3,
  writeText,
  writeShellScriptBin,
}:
let
  lisp = sbclPackages.overrideScope (
    final: prev: {
      qlot-cli = prev.qlot-cli.overrideLispAttrs (old: {
        postPatch =
          (old.postPatch or "")
          + "\n"
          + ''
            ${python3}/bin/python3 ${./scope-sdk.py} "$PWD"
          '';
        buildScript = writeText "compile-qlot-systems.lisp" ''
          (load "${final.qlot-cli.asdfFasl}/asdf.fasl")
          (asdf:load-system :qlot/command)
          (asdf:load-system :qlot/subcommands)
        '';
        installPhase = ''
          mkdir -p "$out"
          cp -r . "$out/"
        '';
      });
    }
  );
  loader = sbcl.withPackages (_: [ lisp.qlot-cli ]);
  runner = writeText "qlot-main.lisp" ''
    (load (sb-ext:posix-getenv "ASDF"))
    (asdf:load-system :qlot/command)
    (asdf:load-system :qlot/subcommands)
    (require :sb-posix)
    (dolist (key '("CL_SOURCE_REGISTRY" "ASDF_OUTPUT_TRANSLATIONS" "ASDF" "SBCL_HOME"))
      (if (uiop:getenvp (concatenate 'string "QLOT_CALLER_HAS_" key))
          (setf (uiop:getenv key) (uiop:getenv (concatenate 'string "QLOT_CALLER_" key)))
          (sb-posix:unsetenv key)))
    (asdf:clear-configuration)
    (qlot/cli:main)
  '';
  launcher = writeShellScriptBin "qlot" ''
    for key in CL_SOURCE_REGISTRY ASDF_OUTPUT_TRANSLATIONS ASDF SBCL_HOME; do
      if [ -v "$key" ]; then
        export "QLOT_CALLER_HAS_$key=1" "QLOT_CALLER_$key=''${!key}"
      else
        unset "QLOT_CALLER_HAS_$key" "QLOT_CALLER_$key"
      fi
      unset "$key"
    done
    exec ${loader}/bin/sbcl --noinform --no-userinit --no-sysinit --script ${runner} "$@"
  '';
in
launcher.overrideAttrs (_: {
  version = sbclPackages.qlot-cli.version;
  passthru = {
    library = lisp.qlot-cli;
    source = lisp.qlot-cli.src;
  };
})
