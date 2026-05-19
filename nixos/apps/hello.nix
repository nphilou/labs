{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  hello = pkgs.stdenvNoCC.mkDerivation {
    pname = "labs-hello";
    version = "0.1.0";
    src = ../../apps/hello;

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
    systemd.services.labs-hello = {
      description = "Labs hello app";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        ExecStart = "${pkgs.python3}/bin/python -m http.server 9101 --bind 127.0.0.1 --directory ${hello}";
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/hello" = {
        return = "301 /hello/";
      };

      "/hello/" = {
        proxyPass = "http://127.0.0.1:9101/";
      };
    };
  };
}
