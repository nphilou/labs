{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  ports = import ./ports.nix;
  portValues = builtins.attrValues ports;
  uniquePortValues = lib.unique portValues;
  sendDeployEmail = pkgs.writers.writePython3Bin "labs-send-deploy-email" {
    libraries = with pkgs.python3Packages; [ resend python-dotenv ];
    flakeIgnore = [ "E501" ];
  } (builtins.readFile ../scripts_send_deploy_email.py);
in

{
  imports = [
    ./apps/apartment-tracker.nix
    ./apps/hello.nix
    ./apps/hello-stefan.nix
    ./apps/streamlit-basic.nix
    ./apps/buyvsrent.nix
    ./apps/liana.nix
    ./apps/tgtg.nix
  ];

  options.nphilou.labs = {
    enable = lib.mkEnableOption "nphilou labs app platform";
  };

  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = builtins.length portValues == builtins.length uniquePortValues;
        message = "nphilou.labs service ports must be unique. Check nixos/ports.nix.";
      }
    ];

    environment.systemPackages = [ sendDeployEmail ];
  };
}
