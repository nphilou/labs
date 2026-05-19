{
  description = "Small self-hosted apps for nphilou.ch";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs, ... }:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs { inherit system; };
      hello = pkgs.stdenvNoCC.mkDerivation {
        pname = "labs-hello";
        version = "0.1.0";
        src = ./apps/hello;

        installPhase = ''
          runHook preInstall
          mkdir -p $out
          cp -r . $out/
          runHook postInstall
        '';
      };
      sendDeployEmail = pkgs.writers.writePython3Bin "labs-send-deploy-email" {
        libraries = with pkgs.python3Packages; [ resend python-dotenv ];
        flakeIgnore = [ "E501" ];
      } (builtins.readFile ./scripts_send_deploy_email.py);
    in
    {
      packages.${system}.hello = hello;
      packages.${system}.send-deploy-email = sendDeployEmail;
      packages.${system}.default = hello;

      nixosModules.default = import ./nixos/module.nix;
    };
}
