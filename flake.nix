{
  description = "Analyze This dev environment and server config";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    sops-nix.url = "github:Mic92/sops-nix";
    sops-nix.inputs.nixpkgs.follows = "nixpkgs";
    disko.url = "github:nix-community/disko";
    disko.inputs.nixpkgs.follows = "nixpkgs";

    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, sops-nix, disko, pyproject-nix, uv2nix, pyproject-build-systems, ... }@inputs:
  let
    inherit (nixpkgs) lib;
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };

    # Load the uv workspace from uv.lock
    workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

    # Create overlay from locked dependencies, preferring pre-built wheels
    overlay = workspace.mkPyprojectOverlay {
      sourcePreference = "wheel";
    };

    # Build the Python package set with uv2nix overlays
    python = pkgs.python312;
    pythonSet = (pkgs.callPackage pyproject-nix.build.packages {
      inherit python;
    }).overrideScope (
      lib.composeManyExtensions [
        pyproject-build-systems.overlays.default
        overlay
      ]
    );

    # Build the production virtualenv from workspace default deps
    appVenv = pythonSet.mkVirtualEnv "analyze-this-env" workspace.deps.default;
  in {
    # Expose the venv as a package for independent testing
    packages.${system}.default = appVenv;

    nixosConfigurations.nixos-analyze-this = nixpkgs.lib.nixosSystem {
      inherit system;
      specialArgs = { inherit inputs appVenv; };
      modules = [
        disko.nixosModules.disko
        ./disk-config.nix
        ./server.nix
        sops-nix.nixosModules.sops
      ];
    };
  };
}
