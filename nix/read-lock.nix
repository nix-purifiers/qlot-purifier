{ lib }:
{
  src,
  lockFile ? src + "/qlot-purifier.lock.json",
  snapshot ? src + "/qlfile.lock",
}:
let
  exists = builtins.pathExists lockFile && builtins.pathExists snapshot;
  raw = if exists then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  entries = data.entries or [ ];
  inputs = data.inputs or { };
  dists = data.dists or [ ];
  releases = data.releases or [ ];
  relative =
    s:
    builtins.isString s
    && s != ""
    && !(lib.hasPrefix "/" s)
    && !(builtins.elem ".." (lib.splitString "/" s));
  safe =
    s: builtins.isString s && s != "." && s != ".." && builtins.match "[A-Za-z0-9_.+-]+" s != null;
  ref = path: builtins.isString path && builtins.any (e: (e.path or null) == path) entries;
  walk =
    prefix:
    let
      dir = builtins.readDir (src + "/${prefix}");
    in
    lib.concatMap (
      name:
      let
        path = if prefix == "" then name else "${prefix}/${name}";
      in
      if
        lib.hasPrefix "." name
        || builtins.elem name [
          "result"
          "__pycache__"
        ]
      then
        [ ]
      else if dir.${name} == "directory" then
        walk path
      else
        lib.optional (dir.${name} == "regular" && lib.hasSuffix ".asd" name) path
    ) (builtins.attrNames dir);
  inventory = builtins.sort builtins.lessThan (
    lib.unique ([ "qlfile" ] ++ walk "" ++ (data.extraInputs or [ ]))
  );
  metadata =
    value:
    builtins.isAttrs value
    && (
      (value ? path && ref value.path && !(value ? content))
      || (
        builtins.isString (value.content or null)
        && builtins.isString (value.sha256 or null)
        && builtins.hashString "sha256" value.content == value.sha256
        && !(value ? path)
      )
    );
  valid =
    exists
    && (data.version or null) == 1
    && (data.purifier or null) == "qlot"
    && builtins.isList (data.extraInputs or null)
    && builtins.all relative data.extraInputs
    && builtins.isAttrs inputs
    && builtins.attrNames inputs == inventory
    && builtins.all (
      name:
      relative name
      && builtins.isAttrs inputs.${name}
      && builtins.isString (inputs.${name}.content or null)
      && builtins.pathExists (src + "/${name}")
      && builtins.hashFile "sha256" (src + "/${name}") == (inputs.${name}.sha256 or null)
      && builtins.hashString "sha256" inputs.${name}.content == inputs.${name}.sha256
    ) (builtins.attrNames inputs)
    && builtins.isAttrs (data.nativeLock or null)
    && builtins.isString (data.nativeLock.content or null)
    && builtins.hashFile "sha256" snapshot == (data.nativeLock.sha256 or null)
    && builtins.hashString "sha256" data.nativeLock.content == data.nativeLock.sha256
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && relative (e.path or null)
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && (e.mirrors or null) == [ ]
      && !(e ? git)
    ) entries
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.isList dists
    && dists != [ ]
    && builtins.all (
      d:
      builtins.isAttrs d
      && safe (d.name or null)
      && builtins.isString (d.version or null)
      && builtins.isAttrs (d.files or null)
      &&
        builtins.attrNames d.files == [
          "distinfo.txt"
          "releases.txt"
          "systems.txt"
        ]
      && builtins.all metadata (builtins.attrValues d.files)
    ) dists
    && builtins.length (lib.unique (map (d: d.name) dists)) == builtins.length dists
    && builtins.isList releases
    && builtins.all (
      r:
      builtins.isAttrs r
      && safe (r.dist or null)
      && safe (r.name or null)
      && safe (r.filename or null)
      && ref (r.path or null)
      && builtins.any (d: d.name == r.dist) dists
      && builtins.any (e: e.path == r.path && e.url == (r.url or null)) entries
      && r.path == "archives/${r.dist}/${r.filename}"
    ) releases
    && builtins.length (lib.unique (map (r: r.path) releases)) == builtins.length releases
    && builtins.isList (data.systems or null)
    && builtins.all (s: builtins.isString s && s != "") data.systems
    && builtins.isAttrs (data.toolVersions or null)
    && builtins.all (key: builtins.isString (data.toolVersions.${key} or null)) [
      "sdk"
      "sbcl"
      "qlot"
      "gcc"
    ];
in
{
  purifier = "qlot";
  inherit data entries;
  nativeSnapshot = if exists then builtins.readFile snapshot else "";
  problems = lib.optional (
    !valid
  ) "Qlot lock is missing, stale, or unsupported; run qlot-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
