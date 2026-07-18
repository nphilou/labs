{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  port = (import ../ports.nix).picnic;
in
{
  config = lib.mkIf cfg.enable {
    systemd.services.labs-picnic = {
      description = "Labs picnic places app";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        WorkingDirectory = ../../apps/picnic;
        ExecStart = ''
          ${pkgs.python3.withPackages (ps: with ps; [ streamlit pandas plotly ])}/bin/streamlit run app.py \
            --server.port ${toString port} \
            --server.address 127.0.0.1 \
            --server.headless true
        '';
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
        proxyWebsockets = true;
      };
    };
  };
}
