{pkgs}: {
  deps = [
    pkgs.util-linux
    pkgs.cacert
    pkgs.postgresql
    pkgs.openssl
  ];
}
