# Edit this configuration file to define what should be installed on
# your system.  Help is available in the configuration.nix(5) man page
# and in the NixOS manual (accessible by running ‘nixos-help’).

{ config, pkgs, inputs, ... }:
let
  appSrc = inputs.self;
  commonRuntimeEnv = [
    "APP_ENV=production"
    "IRCCAT_URL=https://irccat.interestedparticipant.org/send"
    "IRCCAT_ENABLED=true"
    "OTEL_ENABLED=true"
    "OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io"
  ];
  workspace = inputs.uv2nix.lib.workspace.loadWorkspace {
    workspaceRoot = appSrc;
  };
  pyprojectOverlay = workspace.mkPyprojectOverlay {
    sourcePreference = "wheel";
  };
  pythonBase = pkgs.callPackage inputs.pyproject-nix.build.packages {
    python = pkgs.python312;
  };
  pythonSet = pythonBase.overrideScope (
    pkgs.lib.composeManyExtensions [
      inputs.pyproject-build-systems.overlays.default
      pyprojectOverlay
    ]
  );
  pythonEnv = pythonSet.mkVirtualEnv "analyze-this-env" workspace.deps.default;
in
{
  imports =
    [ # Include the results of the hardware scan.
      ./hardware-configuration.nix
    ];

  # Bootloader.
  boot.loader.systemd-boot.enable = true;
  # boot.loader.efi.canTouchEfiVariables = true;

  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  networking.hostName = "nixos-analyze-this"; # Define your hostname.
  # networking.wireless.enable = true;  # Enables wireless support via wpa_supplicant.

  # Configure network proxy if necessary
  # networking.proxy.default = "http://user:password@proxy:port/";
  # networking.proxy.noProxy = "127.0.0.1,localhost,internal.domain";

  # Enable networking
  networking.networkmanager.enable = true;

  # Set your time zone.
  time.timeZone = "America/New_York";

  # Select internationalisation properties.
  i18n.defaultLocale = "en_US.UTF-8";

  i18n.extraLocaleSettings = {
    LC_ADDRESS = "en_US.UTF-8";
    LC_IDENTIFICATION = "en_US.UTF-8";
    LC_MEASUREMENT = "en_US.UTF-8";
    LC_MONETARY = "en_US.UTF-8";
    LC_NAME = "en_US.UTF-8";
    LC_NUMERIC = "en_US.UTF-8";
    LC_PAPER = "en_US.UTF-8";
    LC_TELEPHONE = "en_US.UTF-8";
    LC_TIME = "en_US.UTF-8";
  };

  # Enable the X11 windowing system.
  services.xserver.enable = true;

  # Enable the GNOME Desktop Environment.
  services.xserver.displayManager.gdm.enable = true;
  services.xserver.desktopManager.gnome.enable = true;

  # Configure keymap in X11
  services.xserver.xkb = {
    layout = "us";
    variant = "";
  };

  # Enable CUPS to print documents.
  services.printing.enable = true;

  # Enable sound with pipewire.
  services.pulseaudio.enable = false;
  security.rtkit.enable = true;
  services.pipewire = {
    enable = true;
    alsa.enable = true;
    alsa.support32Bit = true;
    pulse.enable = true;
    # If you want to use JACK applications, uncomment this
    #jack.enable = true;

    # use the example session manager (no others are packaged yet so this is enabled by default,
    # no need to redefine it in your config for now)
    #media-session.enable = true;
  };

  # Enable touchpad support (enabled default in most desktopManager).
  # services.xserver.libinput.enable = true;

  # Define a user account. Don't forget to set a password with ‘passwd’.
  users.users.bwilson = {
    isNormalUser = true;
    description = "Ben Wilson";
    extraGroups = [ "networkmanager" "wheel" ];
    packages = with pkgs; [
    #  thunderbird
    ];
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKNEfdHUdKxweW4gp588QGc2dhU+VlNs6GNL5yfE2XxT"
    ];
  };

  users.users.root = {
    openssh.authorizedKeys.keys = [
      "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIKNEfdHUdKxweW4gp588QGc2dhU+VlNs6GNL5yfE2XxT"
    ];
  };

  # Install firefox.
  programs.firefox.enable = true;

  # Allow unfree packages
  nixpkgs.config.allowUnfree = true;

  # List packages installed in system profile. To search, run:
  # $ nix search wget
  environment.systemPackages = with pkgs; [
    vim # Do not forget to add an editor to edit configuration.nix! The Nano editor is also installed by default.
    git
    curl
    wget
  ];

  # Some programs need SUID wrappers, can be configured further or are
  # started in user sessions.
  # programs.mtr.enable = true;
  # programs.gnupg.agent = {
  #   enable = true;
  #   enableSSHSupport = true;
  # };

  # List services that you want to enable:

  # Enable the OpenSSH daemon.
  services.openssh.enable = true;
  services.openssh.openFirewall = true;
  services.qemuGuest.enable = true;

  # Open ports in the firewall.
  networking.firewall.allowedTCPPorts = [ ];
  # networking.firewall.allowedUDPPorts = [ ... ];
  # Or disable the firewall altogether.
  # networking.firewall.enable = false;

  # This value determines the NixOS release from which the default
  # settings for stateful data, like file locations and database versions
  # on your system were taken. It‘s perfectly fine and recommended to leave
  # this value at the release version of the first install of this system.
  # Before changing this value read the documentation for this option
  # (e.g. man configuration.nix or on https://nixos.org/nixos/options.html).
  system.stateVersion = "25.11"; # Did you read the comment?

  # --- Application Configuration ---

  # Create a group for the application
  users.groups.analyze-this = {};

  # Backend Service User
  users.users.analyze-backend = {
    isSystemUser = true;
    group = "analyze-this";
    description = "Analyze This Backend Service";
    # Allow dedicated users to read from the deployment directory if needed
    # extraGroups = [ "analyze-this" ]; 
  };

  # Worker Service User
  users.users.analyze-worker = {
    isSystemUser = true;
    group = "analyze-this";
    description = "Analyze This Worker Service";
  };
  
  # Sops-nix configuration
  # Ensure sops-nix is imported in your flake.nix modules
  sops.defaultSopsFile = ./secrets.yaml;
  sops.defaultSopsFormat = "yaml";
  
  # Check https://github.com/Mic92/sops-nix for key setup (e.g., using ssh host keys)
  sops.age.keyFile = "/var/lib/sops-nix/key.txt"; 
  
  sops.secrets.backend_sa_json = {
    owner = "analyze-backend";
    group = "analyze-this";
    mode = "0440";
  };

  sops.secrets.worker_sa_json = {
    owner = "analyze-worker";
    group = "analyze-this";
    mode = "0440";
  };
  
  sops.secrets.app_env = {
    owner = "analyze-backend";
    group = "analyze-this";
    mode = "0440";
    # Keep only sensitive env vars in this file.
    # Restart services when secrets change
    restartUnits = [
      "analyze-backend.service"
      "worker-analysis.service"
      "worker-normalization.service"
      "worker-follow-up.service"
      "worker-manager.service"
    ];
  };

  sops.secrets.cloudflared_tunnel_token = {
    owner = "root";
    group = "root";
    mode = "0400";
    restartUnits = [ "cloudflared.service" ];
  };

  # Backend Service
  systemd.services.analyze-backend = {
    description = "Analyze This Backend API";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" ];
    serviceConfig = {
      User = "analyze-backend";
      Group = "analyze-this";
      WorkingDirectory = "${appSrc}/backend";
      ExecStart = "${pythonEnv}/bin/uvicorn main:app --host 127.0.0.1 --port 8000";
      EnvironmentFile = "/run/secrets/app_env";
      Environment =
        commonRuntimeEnv ++ [
          "OTEL_SERVICE_NAME=analyzethis-api"
          "GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/backend_sa_json"
        ];
      Restart = "always";
      RestartSec = "10s";
      StateDirectory = "analyze-this";
    };
  };

  # Worker Service
  systemd.services.worker-analysis = {
    description = "Analyze This Worker (Analysis)";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    serviceConfig = {
      Type = "oneshot";
      User = "analyze-worker";
      Group = "analyze-this";
      WorkingDirectory = "${appSrc}/backend";
      ExecStart = "${pythonEnv}/bin/python worker.py --job-type analysis";
      EnvironmentFile = "/run/secrets/app_env";
      Environment =
        commonRuntimeEnv ++ [
          "OTEL_SERVICE_NAME=analyze-worker"
          "GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/worker_sa_json"
        ];
      TimeoutStartSec = "15min";
      RuntimeMaxSec = "15min";
      StateDirectory = "analyze-this";
    };
  };

  systemd.services.worker-normalization = {
    description = "Analyze This Worker (Normalize)";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    serviceConfig = {
      Type = "oneshot";
      User = "analyze-worker";
      Group = "analyze-this";
      WorkingDirectory = "${appSrc}/backend";
      ExecStart = "${pythonEnv}/bin/python worker.py --job-type normalize";
      EnvironmentFile = "/run/secrets/app_env";
      Environment =
        commonRuntimeEnv ++ [
          "OTEL_SERVICE_NAME=analyze-worker-normalize"
          "GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/worker_sa_json"
        ];
      TimeoutStartSec = "15min";
      RuntimeMaxSec = "15min";
      StateDirectory = "analyze-this";
    };
  };

  systemd.services.worker-follow-up = {
    description = "Analyze This Worker (Follow Up)";
    after = [ "network-online.target" ];
    wants = [ "network-online.target" ];
    serviceConfig = {
      Type = "oneshot";
      User = "analyze-worker";
      Group = "analyze-this";
      WorkingDirectory = "${appSrc}/backend";
      ExecStart = "${pythonEnv}/bin/python worker.py --job-type follow_up";
      EnvironmentFile = "/run/secrets/app_env";
      Environment =
        commonRuntimeEnv ++ [
          "OTEL_SERVICE_NAME=analyze-worker-follow-up"
          "GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/worker_sa_json"
        ];
      TimeoutStartSec = "15min";
      RuntimeMaxSec = "15min";
      StateDirectory = "analyze-this";
    };
  };

  systemd.timers.worker-analysis = {
    description = "Run Analyze This Worker (Analysis) every 60s idle";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      Unit = "worker-analysis.service";
      OnBootSec = "30s";
      OnUnitInactiveSec = "60s";
      RandomizedDelaySec = "10s";
      Persistent = true;
    };
  };

  systemd.timers.worker-normalization = {
    description = "Run Analyze This Worker (Normalize) every 60s idle";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      Unit = "worker-normalization.service";
      OnBootSec = "40s";
      OnUnitInactiveSec = "60s";
      RandomizedDelaySec = "10s";
      Persistent = true;
    };
  };

  systemd.timers.worker-follow-up = {
    description = "Run Analyze This Worker (Follow Up) every 60s idle";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      Unit = "worker-follow-up.service";
      OnBootSec = "50s";
      OnUnitInactiveSec = "60s";
      RandomizedDelaySec = "10s";
      Persistent = true;
    };
  };

  systemd.services.worker-manager = {
    description = "Analyze This Worker Manager";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" ];
    serviceConfig = {
      User = "analyze-worker";
      Group = "analyze-this";
      WorkingDirectory = "${appSrc}/backend";
      ExecStart = "${pythonEnv}/bin/python worker_manager.py --loop";
      EnvironmentFile = "/run/secrets/app_env";
      Environment =
        commonRuntimeEnv ++ [
          "OTEL_SERVICE_NAME=analyze-worker-manager"
          "GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/worker_sa_json"
          "MANAGER_INTERVAL_SECONDS=60"
          "ENABLE_JOB_LAUNCHING=false"
        ];
      Restart = "always";
      RestartSec = "10s";
      StateDirectory = "analyze-this";
    };
  };

  systemd.services.cloudflared = {
    description = "Cloudflare Tunnel";
    wantedBy = [ "multi-user.target" ];
    wants = [ "network-online.target" "analyze-backend.service" ];
    after = [ "network-online.target" "analyze-backend.service" ];
    serviceConfig = {
      Type = "simple";
      Restart = "always";
      RestartSec = "5s";
      ExecStart = "${pkgs.bash}/bin/bash -ceu '${pkgs.cloudflared}/bin/cloudflared tunnel --no-autoupdate run --token \"$(cat ${config.sops.secrets.cloudflared_tunnel_token.path})\"'";
    };
  };

}
