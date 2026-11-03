{
  symlinkJoin,
  nativeQlot,
  sbcl,
  git,
  curl,
  gnutar,
  gzip,
  unzip,
  gnumake,
  gcc,
  cacert,
  which,
  coreutils,
  findutils,
  gnused,
  pkg-config,
}:
symlinkJoin {
  name = "qlot-purifier-toolchain";
  paths = [
    nativeQlot
    sbcl
    git
    curl
    gnutar
    gzip
    unzip
    gnumake
    gcc
    cacert
    which
    coreutils
    findutils
    gnused
    pkg-config
  ];
}
