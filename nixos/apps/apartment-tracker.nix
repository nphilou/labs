{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
in
{
  config = lib.mkIf cfg.enable {
    systemd.services.labs-apartment-tracker = {
      description = "Labs apartment tracker app";
      after = [ "network.target" ];
      wantedBy = [ "multi-user.target" ];

      environment = {
        APARTMENT_TRACKER_DB = "/var/lib/labs-apartment-tracker/apartments.sqlite3";
      };

      serviceConfig = {
        DynamicUser = true;
        StateDirectory = "labs-apartment-tracker";
        WorkingDirectory = ../../apps/apartment-tracker;
        ExecStart = ''
          ${pkgs.python3.withPackages (ps: with ps; [ streamlit pandas ])}/bin/streamlit run app.py \
            --server.port 9103 \
            --server.address 127.0.0.1 \
            --server.headless true
        '';
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/apartment-tracker" = {
        return = "301 /apartment-tracker/";
      };

      "/apartment-tracker/" = {
        proxyPass = "http://127.0.0.1:9103/";
        proxyWebsockets = true;
      };
    };
  };
}
