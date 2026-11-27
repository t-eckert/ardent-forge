{ lib, buildNpmPackage, nodejs_24 }:

buildNpmPackage {
  pname = "implementer";
  version = (lib.importJSON ../package.json).version;

  src = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../package.json
      ../package-lock.json
      ../tsconfig.json
      ../tsconfig.build.json
      ../src
      ../images
    ];
  };

  nodejs = nodejs_24;
  # The session image's Containerfile, which the NixOS module builds on the host as the implementer's user.
  postInstall = ''
    mkdir -p $out/share/implementer
    cp -r images $out/share/implementer/images
  '';
  # node:sqlite still prints an ExperimentalWarning on Node 24; the wrapper calls node directly, so the shebang
  # flag in src/cli.ts does not reach it.
  makeWrapperArgs = [ "--set" "NODE_OPTIONS" "--disable-warning=ExperimentalWarning" ];
  # Update with `nix run nixpkgs#prefetch-npm-deps -- package-lock.json` after changing dependencies.
  npmDepsHash = "sha256-LZMUNfmM9ALT6+LuermiMBvod8z1loSBWV9jkslzBHU=";

  meta = {
    description = "The Forge's coding agent";
    mainProgram = "implementer";
  };
}
