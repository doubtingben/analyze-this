{
  description = "Analyze This dev environment and server config";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
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
    sops-nix.url = "github:Mic92/sops-nix";
    sops-nix.inputs.nixpkgs.follows = "nixpkgs";
    disko.url = "github:nix-community/disko";
    disko.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, sops-nix, disko, ... }@inputs:
  let
    system = "x86_64-linux";
    pkgs = import nixpkgs { inherit system; };
    python = pkgs.python312.withPackages (ps: with ps; [
      aiosqlite
      authlib
      fastapi
      firebase-admin
      google-auth
      google-auth-oauthlib
      greenlet
      gunicorn
      httpx
      itsdangerous
      jinja2
      openai
      opentelemetry-api
      opentelemetry-sdk
      opentelemetry-exporter-otlp
      opentelemetry-instrumentation-fastapi
      opentelemetry-instrumentation-httpx
      python-dotenv
      python-multipart
      requests
      sqlalchemy
      uvicorn
      pytest
      pypdf
    ]);
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = with pkgs; [
        python
        uv
        nodejs
        git
        gnumake
        sops
        age
      ];
      shellHook = ''
        export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
      '';
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
