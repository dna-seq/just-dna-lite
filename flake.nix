{
  description = "just-dna-lite dev environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        isLinux = pkgs.stdenv.hostPlatform.isLinux;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            pkgs.python313
            pkgs.uv
            pkgs.nodejs_22
          ] ++ pkgs.lib.optionals isLinux [
            pkgs.stdenv.cc.cc.lib
          ];

          shellHook = ''
            export UV_PYTHON="${pkgs.python313}/bin/python3"
          '' + pkgs.lib.optionalString isLinux ''
            export LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH"
          '';
        };
      });
}
