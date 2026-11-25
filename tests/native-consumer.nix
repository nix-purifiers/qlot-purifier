{
  pkgs,
  product,
  expected ? 42,
  foreignPreparer ? null,
}:
let
  python = pkgs.python3.withPackages (packages: [ packages.cffi ]);
  producer = product.packages.native-library;
  projections = product.projections;
  library = "${producer}/lib/libapplication.so";
in
assert toString projections.python-ffi == toString projections.native;
assert toString projections.java-ffi == toString projections.native;
pkgs.runCommand "qlot-native-callable-consumer" { } ''
  export HOME="$TMPDIR/home"
  mkdir -p "$HOME" "$out"
  ${python}/bin/python3 - ${projections.native}/catalog.json ${library} <<'PY'
  import json, sys
  from pathlib import Path
  catalog = json.loads(Path(sys.argv[1]).read_text())
  assert catalog['libraries']['application'] == sys.argv[2]
  assert catalog['targets']['application']['abi'] == 'c'
  assert Path(catalog['libraries']['application']).is_file()
  PY
  cp ${projections.native}/catalog.json "$out/catalog.json"
  export QLOT_NATIVE_IMAGE_DIR="$TMPDIR/prepared"
  ${product.packages.prepare-native-image}/bin/qlot-prepare-native-image "$QLOT_NATIVE_IMAGE_DIR"
  (cd "$QLOT_NATIVE_IMAGE_DIR" && sha256sum --check SHA256SUMS)
  ${pkgs.lib.optionalString (foreignPreparer != null) ''
    ${foreignPreparer}/bin/qlot-prepare-native-image "$TMPDIR/foreign"
    QLOT_NATIVE_IMAGE_DIR="$TMPDIR/foreign" ${python}/bin/python3 - ${library} <<'PY'
    import ctypes, sys
    assert ctypes.CDLL(sys.argv[1]).native_init() == 2
    PY
  ''}
  ${pkgs.gcc}/bin/gcc -DEXPECTED=${toString expected} \
    -I${producer}/include ${./native-consumer.c} \
    -L${producer}/lib -Wl,-rpath,${producer}/lib \
    -lapplication -o "$TMPDIR/native-consumer"
  "$TMPDIR/native-consumer"
  ${python}/bin/python3 ${./native-consumer.py} ${library} ${toString expected} ctypes > "$out/ctypes.txt"
  ${python}/bin/python3 ${./native-consumer.py} ${library} ${toString expected} cffi > "$out/cffi.txt"
  ${pkgs.jdk21}/bin/java --enable-preview --enable-native-access=ALL-UNNAMED --source 21 \
    ${./NativeCallable.java} ${library} ${toString expected} > "$out/java.txt"
''
