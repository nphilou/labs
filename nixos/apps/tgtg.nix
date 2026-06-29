{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  port = (import ../ports.nix).tgtg;
  monitor = pkgs.writers.writePython3Bin "labs-tgtg-monitor" {
    libraries = with pkgs.python3Packages; [ tgtg ];
    flakeIgnore = [ "E501" ];
  } (builtins.readFile ../../apps/tgtg/monitor.py);
in
{
  config = lib.mkIf cfg.enable {
    systemd.services.labs-tgtg = {
      description = "Labs Too Good To Go Streamlit app";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];

      environment = {
        STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false";
      };

      serviceConfig = {
        DynamicUser = true;
        WorkingDirectory = ../../apps/tgtg;
        ExecStart = ''
          ${pkgs.python3.withPackages (ps: with ps; [ streamlit pandas tgtg ])}/bin/streamlit run app.py \
            --server.port ${toString port} \
            --server.address 127.0.0.1 \
            --server.headless true
        '';
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/tgtg" = {
        return = "301 /tgtg/";
      };

      "/tgtg/" = {
        proxyPass = "http://127.0.0.1:${toString port}/";
        proxyWebsockets = true;
      };
    };

    systemd.services.labs-tgtg-monitor = {
      description = "Labs Too Good To Go availability monitor";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];

      environment = {
        TGTG_MONITOR_ITEM_ID = "1198174";
        TGTG_MONITOR_MIN_AVAILABLE = "3";
        TGTG_MONITOR_MAX_PRICE_CHF = "11";
        TGTG_MONITOR_STATE = "/var/lib/labs-tgtg-monitor/state.json";
      };

      serviceConfig = {
        Type = "oneshot";
        DynamicUser = true;
        StateDirectory = "labs-tgtg-monitor";
        EnvironmentFile = "-/var/lib/labs/secrets/tgtg-monitor.env";
        ExecStart = lib.getExe monitor;
      };
    };

    systemd.timers.labs-tgtg-monitor = {
      description = "Run Labs Too Good To Go availability monitor";
      wantedBy = [ "timers.target" ];

      timerConfig = {
        OnBootSec = "5min";
        OnUnitActiveSec = "20min";
        RandomizedDelaySec = "90s";
        AccuracySec = "1min";
        Persistent = true;
        Unit = "labs-tgtg-monitor.service";
      };
    };
  };
}
