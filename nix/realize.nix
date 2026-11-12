{
  project,
  companion,
  snapshot,
  target ? "environment",
}:
let
  nixpkgsSrc = /. + "@nixpkgs@";
  pkgs = import nixpkgsSrc { };
  purifier = import (/. + "@purifier@/nix/lib") { inherit (pkgs) lib; };
  nativeQlot = pkgs.callPackage ./qlot.nix { };
  toolchain = pkgs.callPackage ./toolchain.nix { inherit nativeQlot; };
  sdkVersion = import ./sdk-version.nix { inherit nixpkgsSrc; };
  args = {
    src = /. + project;
    lockFile = /. + companion;
    snapshot = /. + snapshot;
  };
  lock = import ../lib-overlays/default/read-lock.nix { inherit (pkgs) lib; } args;
in
if target == "environment" then
  pkgs.callPackage ../pkgs/build-qlot-project/environment.nix {
    inherit
      purifier
      nativeQlot
      toolchain
      sdkVersion
      ;
  } { inherit lock; }
else if target == "release" then
  (pkgs.callPackage ../pkgs/build-qlot-project/default.nix {
    inherit
      purifier
      nativeQlot
      toolchain
      sdkVersion
      ;
  } args).release
else
  throw "qlot-purifier: unknown target"
