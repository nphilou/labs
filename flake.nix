{
  description = "Small self-hosted apps for nphilou.ch";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { ... }: {
    nixosModules.default = import ./nixos/module.nix;
  };
}
