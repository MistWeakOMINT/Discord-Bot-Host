{ pkgs }: {
  deps = [
    pkgs.python310
    pkgs.nodePackages.pnpm
    pkgs.nodejs-18_x
    pkgs.libuuid
  ];
}