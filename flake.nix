{
  description = "Analyze This dev environment";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [
        python312
        uv
        # add build tools here if you hit native deps:
        # gcc pkg-config openssl zlib
      ];

      shellHook = ''
        git config user.email "doubtingben@gmail.com"
        git config user.name "Ben Wilson"
      '';
    };
  };
}
