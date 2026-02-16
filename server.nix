# Edit this configuration file to define what should be installed on
# your system.  Help is available in the configuration.nix(5) man page
# and in the NixOS manual (accessible by running ‘nixos-help’).

{ config, pkgs, inputs, appVenv, ... }:

{
  imports =
    [ # Include the results of the hardware scan.
      ./hardware-configuration.nix
    ];

  # Bootloader.
  boot.loader.systemd-boot.enable = true;
  # boot.loader.efi.canTouchEfiVariables = true;

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
  services.qemuGuest.enable = true;

  # Open ports in the firewall.
  # networking.firewall.allowedTCPPorts = [ ... ];
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
    # Restart services when secrets change
    restartUnits = [ "analyze-backend.service" "analyze-worker.service" ];
  };

  # Backend Service
  systemd.services.analyze-backend = {
    description = "Analyze This Backend API";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" ];
    serviceConfig = {
      User = "analyze-backend";
      Group = "analyze-this";
      WorkingDirectory = "${inputs.self}/backend";
      ExecStart = "${appVenv}/bin/fastapi run main.py";
      EnvironmentFile = "/run/secrets/app_env";
      Environment = "GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/backend_sa_json";
      Restart = "always";
      RestartSec = "10s";
    };
  };

  # Worker Service
  systemd.services.analyze-worker = {
    description = "Analyze This Worker (Analysis)";
    wantedBy = [ "multi-user.target" ];
    after = [ "network.target" ];
    serviceConfig = {
      User = "analyze-worker";
      Group = "analyze-this";
      WorkingDirectory = "${inputs.self}/backend";
      ExecStart = "${appVenv}/bin/python worker.py --job-type analysis";
      EnvironmentFile = "/run/secrets/app_env";
      Environment = "GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/worker_sa_json";
      Restart = "always";
      RestartSec = "10s";
    };
  };

}