{ nixpkgsSrc }:
builtins.hashString "sha256" (
  builtins.toJSON {
    nixpkgs = toString nixpkgsSrc;
    scope = builtins.hashFile "sha256" ./scope-sdk.py;
    native = builtins.hashFile "sha256" ./qlot.nix;
    toolchain = builtins.hashFile "sha256" ./toolchain.nix;
  }
)
