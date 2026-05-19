{ config, lib, pkgs, ... }:

let
  cfg = config.nphilou.labs;
  sendDeployEmail = pkgs.writers.writePython3Bin "labs-send-deploy-email" {
    libraries = with pkgs.python3Packages; [ resend python-dotenv ];
    flakeIgnore = [ "E501" ];
  } (builtins.readFile ../scripts_send_deploy_email.py);
in

{
  imports = [
    ./apps/hello.nix
  ];

  options.nphilou.labs = {
    enable = lib.mkEnableOption "nphilou labs app platform";
  };

  config = lib.mkIf cfg.enable {
    environment.systemPackages = [ sendDeployEmail ];
  };
}
