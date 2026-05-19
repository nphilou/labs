{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
in
{
  config = lib.mkIf cfg.enable {
    systemd.services.labs-streamlit-basic = {
      description = "Labs Streamlit basic app";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        WorkingDirectory = ../../apps/streamlit-basic;
        ExecStart = ''
          ${pkgs.python3.withPackages (ps: with ps; [ streamlit pandas numpy ])}/bin/streamlit run app.py \
            --server.port 9102 \
            --server.address 127.0.0.1 \
            --server.headless true
        '';
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/streamlit-basic" = {
        return = "301 /streamlit-basic/";
      };

      "/streamlit-basic/" = {
        proxyPass = "http://127.0.0.1:9102/";
        proxyWebsockets = true;
      };
    };
  };
}
