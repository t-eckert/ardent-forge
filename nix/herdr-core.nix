# nix/herdr-core.nix
#
# herdr-core (`hc`), the terminal runtime the Herdr Mac app connects to. It is a
# separate program from `herdr`, the TUI in systemPackages beside it: the Mac
# runs `hc machine add ardent-forge`, which needs an hc on this box new enough
# to talk to its own.
#
# nixpkgs carries herdr-core but lags the Mac app (0.1.15 against 0.1.20 when
# this was written), so this takes the official release build instead. Linux
# builds are statically linked and run as shipped. The hash is the release
# manifest's sha256 for linux-x86_64:
#   https://releases.herdr.dev/core/<version>/manifest.json
# To move with the Mac, bump `version`, then set `hash` from
#   nix store prefetch-file https://releases.herdr.dev/core/<version>/herdr-core-linux-x86_64.tar.gz
{ stdenvNoCC, fetchurl, lib }:

stdenvNoCC.mkDerivation rec {
  pname = "herdr-core";
  version = "0.1.20";

  src = fetchurl {
    url = "https://releases.herdr.dev/core/${version}/herdr-core-linux-x86_64.tar.gz";
    hash = "sha256-rGuGiQxFGjdYRiCqpDi3G8DQvUMKLnwdfglfBSxBTnQ=";
  };

  sourceRoot = ".";
  dontConfigure = true;
  dontBuild = true;
  dontStrip = true;

  installPhase = ''
    runHook preInstall
    install -Dm755 herdr-core $out/bin/herdr-core
    ln -s herdr-core $out/bin/hc
    install -Dm644 LICENSE THIRD-PARTY-NOTICES -t $out/share/doc/herdr-core
    runHook postInstall
  '';

  meta = {
    description = "Terminal runtime for coding agents (hc), served to the Herdr app";
    homepage = "https://herdr.dev/core/";
    license = lib.licenses.asl20;
    platforms = [ "x86_64-linux" ];
    mainProgram = "hc";
  };
}
