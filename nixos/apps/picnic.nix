{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  port = (import ../ports.nix).picnic;
  picnic = pkgs.stdenvNoCC.mkDerivation {
    pname = "labs-picnic";
    version = "0.1.0";
    src = ../../apps/picnic;

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
    systemd.services.labs-picnic = {
      description = "Labs picnic places app";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        ExecStart = "${pkgs.python3}/bin/python -m http.server ${toString port} --bind 127.0.0.1 --directory ${picnic}";
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/picnic" = {
        return = "301 /picnic/";
      };

      "/picnic/" = {
        proxyPass = "http://127.0.0.1:${toString port}/";
      };
    };
  };
}
