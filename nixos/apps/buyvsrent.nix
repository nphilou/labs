{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  python = pkgs.python3.withPackages (ps: with ps; [
    joblib
    numpy
    plotly
    streamlit
    xlrd
  ]);
  runBuyVsRent = pkgs.writeShellApplication {
    name = "labs-run-buyvsrent";
    runtimeInputs = [ pkgs.git python ];
    text = ''
      set -euo pipefail

      repo_url="https://github.com/ulupo/buyvsrent.git"
      workdir="''${STATE_DIRECTORY:-/var/lib/labs-buyvsrent}"
      repo="$workdir/source"

      mkdir -p "$workdir"

      if [ ! -d "$repo/.git" ]; then
        rm -rf "$repo"
        git clone --depth 1 --branch main "$repo_url" "$repo"
      else
        git -C "$repo" fetch --depth 1 origin main
        git -C "$repo" checkout --force FETCH_HEAD
      fi

      export PYTHONPATH="$repo''${PYTHONPATH:+:$PYTHONPATH}"
      export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

      exec streamlit run "$repo/src/visualizer.py" \
        --server.port 9103 \
        --server.address 127.0.0.1 \
        --server.headless true \
        --server.fileWatcherType none
    '';
  };
in
{
  config = lib.mkIf cfg.enable {
    systemd.services.labs-buyvsrent = {
      description = "Labs buy-vs-rent Streamlit app";
      after = [ "network-online.target" ];
      wants = [ "network-online.target" ];
      wantedBy = [ "multi-user.target" ];

      serviceConfig = {
        DynamicUser = true;
        StateDirectory = "labs-buyvsrent";
        WorkingDirectory = "/var/lib/labs-buyvsrent";
        ExecStart = lib.getExe runBuyVsRent;
        Restart = "always";
        RestartSec = "5s";
      };
    };

    services.nginx.virtualHosts."app.nphilou.ch".locations = {
      "/buyvsrent" = {
        return = "301 /buyvsrent/";
      };

      "/buyvsrent/" = {
        proxyPass = "http://127.0.0.1:9103/";
        proxyWebsockets = true;
      };
    };
  };
}
