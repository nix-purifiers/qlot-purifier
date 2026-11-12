{
  description = "Locked, Nix-resolved Common Lisp dependencies";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        qlot-purifier = final.lib.makeScope final.newScope (scope: {
          nativeQlot = scope.callPackage ./nix/qlot.nix { };
          toolchain = scope.callPackage ./nix/toolchain.nix { };
          sdkVersion = import ./nix/sdk-version.nix { nixpkgsSrc = nixpkgs; };
          cli = scope.callPackage ./pkgs/qlot-purifier/default.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildQlotProject = scope.callPackage ./pkgs/build-qlot-project/default.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).qlot-purifier.cli;
        cli = self.packages.${system}.default;
        sdk = (pkgsFor system).qlot-purifier.toolchain;
        native = (pkgsFor system).qlot-purifier.nativeQlot;
        native-library = (pkgsFor system).qlot-purifier.nativeQlot.library;
      });
      lib.qlot-purifier = import ./lib-overlays/default { lib = nixpkgs.lib; };
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/qlot-purifier";
          meta.description = "Lock Common Lisp dependencies";
        };
      });
      checks = forAll (
        system:
        let
          build = (pkgsFor system).qlot-purifier.buildQlotProject { src = ./examples/minimal; };
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
          installed = (pkgsFor system).runCommand "installed-common-lisp-consumer" { } ''
            export HOME="$TMPDIR/home"
            mkdir -p "$HOME"
            ${(pkgsFor system).sbcl}/bin/sbcl --noinform --no-userinit --no-sysinit --non-interactive \
              --load ${build.packages.project}/setup.lisp \
              --eval '(ql:quickload "purifier-example" :silent t)' \
              --eval '(write-line (purifier-example:serialized))' > answer.json
            ${(pkgsFor system).python3}/bin/python3 -c 'import json; assert json.load(open("answer.json")) == {"answer":42}'
            mkdir "$out"
            cp answer.json "$out/answer.json"
          '';
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
