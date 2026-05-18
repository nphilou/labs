{ lib, ... }:

{
  options.nphilou.labs = {
    enable = lib.mkEnableOption "nphilou labs app platform";
  };

  config = {};
}
