## Deploying with NixOS

```
nixos-rebuild switch --flake .#nixos-analyze-this   \
  --target-host bwilson@nixos-analyze-this   \
  --build-host bwilson@nixos-analyze-this   \
  --use-remote-sudo --ask-sudo-password
```
