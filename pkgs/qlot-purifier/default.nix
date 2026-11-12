{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  toolchain,
  nativeQlot,
  sbcl,
  gcc,
  cacert,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "qlot-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/qlot-purifier"
    cp -r qlot_purifier nix lib-overlays pkgs "$out/lib/qlot-purifier/"
    install -m755 bin/qlot-purifier "$out/bin/qlot-purifier"
    substituteInPlace "$out/lib/qlot-purifier/nix/realize.nix" \
      --replace-fail '@nixpkgs@' '${nixpkgsSrc}' \
      --replace-fail '@purifier@' '${purifierSrc}'
    wrapProgram "$out/bin/qlot-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          toolchain
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set QLOT_PURIFIER_NATIVE_QLOT ${nativeQlot}/bin/qlot \
      --set QLOT_PURIFIER_NATIVE_SBCL ${sbcl}/bin/sbcl \
      --set QLOT_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set QLOT_PURIFIER_SBCL_VERSION ${sbcl.version} \
      --set QLOT_PURIFIER_QLOT_VERSION ${nativeQlot.version} \
      --set QLOT_PURIFIER_GCC_VERSION ${gcc.version} \
      --set QLOT_PURIFIER_SDK "$out" \
      --set QLOT_PURIFIER_TOOLCHAIN ${toolchain}
    for tool in qlot sbcl; do
      makeWrapper "$out/bin/qlot-purifier" "$out/bin/$tool" --add-flags "--native --tool=$tool --"
    done
    for program in ${toolchain}/bin/*; do
      name=$(basename "$program")
      if [ ! -e "$out/bin/$name" ]; then ln -s "$program" "$out/bin/$name"; fi
    done
  '';
  meta = {
    description = "Native Common Lisp workflow with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "qlot-purifier";
  };
}
