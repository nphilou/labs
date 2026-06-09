{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  port = (import ../ports.nix)."hello-stefan";
  helloStefan = pkgs.stdenvNoCC.mkDerivation {
    pname = "labs-hello-stefan";
    version = "0.1.0";
    src = ../../apps/hello-stefan;

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
    systemd.services.labs-hello-stefan = {
      description = "Labs hello Stefan app";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        ExecStart = "${pkgs.python3}/bin/python -m http.server ${toString port} --bind 127.0.0.1 --directory ${helloStefan}";
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/hello-stefan" = {
        return = "301 /hello-stefan/";
      };

      "/hello-stefan/" = {
        proxyPass = "http://127.0.0.1:${toString port}/";
      };
    };
  };
}
