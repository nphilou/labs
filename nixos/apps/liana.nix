{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  liana = pkgs.stdenvNoCC.mkDerivation {
    pname = "labs-liana";
    version = "0.1.0";
    src = ../../apps/liana;

    installPhase = ''
      runHook preInstall
      mkdir -p $out
      cp -r . $out/
      runHook postInstall
    '';
  };
in
{
  config = lib.mkIf cfg.enable {
    systemd.services.labs-liana = {
      description = "Labs Liana portfolio app";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        ExecStart = "${pkgs.python3}/bin/python -m http.server 9104 --bind 127.0.0.1 --directory ${liana}";
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/liana" = {
        return = "301 /liana/";
      };

      "/liana/" = {
        proxyPass = "http://127.0.0.1:9104/";
      };
    };
  };
}
