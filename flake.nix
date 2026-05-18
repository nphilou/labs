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
    in
    {
      packages.${system}.hello = hello;
      packages.${system}.default = hello;

      nixosModules.default = import ./nixos/module.nix;
    };
}
