{
  description = "Analyze This dev environment and server config";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    sops-nix.url = "github:Mic92/sops-nix";
    sops-nix.inputs.nixpkgs.follows = "nixpkgs";
    disko.url = "github:nix-community/disko";
    disko.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, sops-nix, disko, ... }@inputs:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [
        python312
        uv
        git
        gnumake
        sops
        age
      ];
    };

    nixosConfigurations.nixos-analyze-this = nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = { inherit inputs; };
      modules = [
        disko.nixosModules.disko
        ./disk-config.nix
        ./server.nix
        sops-nix.nixosModules.sops
      ];
    };
  };
}
