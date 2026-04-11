# Ardent Forge — NixOS Installation Runbook

## Prerequisites

- Bee Link mini PC (Intel N150, 16GB RAM, 1TB NVMe)
- USB drive (8GB+)
- Monitor + keyboard (for initial install only)
- 1Password account with "ArdentForge" vault containing:
  - `anthropic-api-key`
  - `github-pat`
  - `linear-api-key`
  - `linear-team-id`
  - `open-weather-api-key`

## Phase 1: Create NixOS USB Installer

On your Mac:

    # Download minimal NixOS ISO (x86_64)
    curl -LO https://channels.nixos.org/nixos-unstable/latest-nixos-minimal-x86_64-linux.iso

    # Find USB device
    diskutil list

    # Write ISO (replace diskN with your USB)
    sudo dd if=latest-nixos-minimal-x86_64-linux.iso of=/dev/rdiskN bs=4m status=progress
    diskutil eject /dev/diskN

## Phase 2: Install NixOS on Bee Link

Boot from USB, then:

    # Connect to network (ethernet should auto-configure)
    ip a

    # Partition the NVMe
    sudo parted /dev/nvme0n1 -- mklabel gpt
    sudo parted /dev/nvme0n1 -- mkpart ESP fat32 1MB 1GB
    sudo parted /dev/nvme0n1 -- set 1 esp on
    sudo parted /dev/nvme0n1 -- mkpart primary 1GB -8GB
    sudo parted /dev/nvme0n1 -- mkpart primary linux-swap -8GB 100%

    # Format
    sudo mkfs.fat -F 32 -n boot /dev/nvme0n1p1
    sudo mkfs.ext4 -L nixos /dev/nvme0n1p2
    sudo mkswap -L swap /dev/nvme0n1p3

    # Mount
    sudo mount /dev/disk/by-label/nixos /mnt
    sudo mkdir -p /mnt/boot
    sudo mount /dev/disk/by-label/boot /mnt/boot

    # Generate hardware config
    sudo nixos-generate-config --root /mnt

    # Copy the generated hardware config — you'll want this
    cat /mnt/etc/nixos/hardware-configuration.nix

    # Minimal bootstrap config to get SSH + flakes working
    cat > /mnt/etc/nixos/configuration.nix << 'NIXEOF'
    { config, pkgs, ... }:
    {
      imports = [ ./hardware-configuration.nix ];
      boot.loader.systemd-boot.enable = true;
      boot.loader.efi.canTouchEfiVariables = true;
      networking.hostName = "ardent-forge";
      time.timeZone = "America/Toronto";
      services.openssh.enable = true;
      users.users.thomaseckert = {
        isNormalUser = true;
        extraGroups = [ "wheel" ];
        openssh.authorizedKeys.keys = [
          "ssh-ed25519 AAAAC3... thomaseckert"
        ];
      };
      nix.settings.experimental-features = [ "nix-command" "flakes" ];
      environment.systemPackages = with pkgs; [ git vim curl ];
      system.stateVersion = "24.11";
    }
    NIXEOF

    # Install
    sudo nixos-install

    # Set root password when prompted, then reboot
    sudo reboot

## Phase 3: Deploy Full Configuration

From your Mac, after the Bee Link has rebooted and you can SSH in:

    # SSH to the Bee Link (via local network first time)
    ssh thomaseckert@10.0.0.67

    # On the Bee Link: clone the ardent-forge repo
    git clone https://github.com/t-eckert/ardent-forge.git /data/ardent-forge/repo
    cd /data/ardent-forge/repo

    # Copy the real hardware config from the bootstrap install
    cp /etc/nixos/hardware-configuration.nix nix/hardware.nix

    # Create locals.nix from the example (gitignored — stays on this machine)
    cp nix/locals.example.nix nix/locals.nix
    # Edit with your real tailnet domain and SSH public key:
    vim nix/locals.nix

    # Apply the full NixOS configuration
    sudo nixos-rebuild switch --flake ./nix#ardent-forge

    # Set up Tailscale
    sudo tailscale up

    # Sign into 1Password CLI
    eval $(op signin)

    # Run the first-boot setup script
    ~/.local/bin/forge-setup

    # Copy NTFY config
    sudo cp /etc/ardent-forge/ntfy-server.yml.example /data/ntfy/etc/server.yml
    # Edit the base-url to match your tailnet hostname:
    sudo vim /data/ntfy/etc/server.yml

    # Start all services
    sudo systemctl start ardent-forge

## Phase 4: Validate

    # Check all services are running
    systemctl status ardent-forge
    systemctl status postgresql
    systemctl status prometheus
    systemctl status grafana
    systemctl status loki
    systemctl status ollama
    systemctl status podman-ntfy
    systemctl status the-weather
    systemctl status tailscaled
    systemctl status caddy

    # Test Ardent Forge API
    curl http://127.0.0.1:7030/health

    # Test via Tailscale (from Mac)
    curl https://<your-tailnet-domain>/health

    # Test Grafana
    curl -s http://127.0.0.1:3000/api/health | jq .

    # Test NTFY
    curl -d "Ardent Forge is alive" http://127.0.0.1:8090/test

    # Test Ollama
    curl http://127.0.0.1:11434/api/tags

    # Check Prometheus targets
    curl http://127.0.0.1:9090/api/v1/targets | jq '.data.activeTargets[].health'

## Phase 5: Commit Hardware Config

After validation, commit the real hardware config back to the repo:

    cd /data/ardent-forge/repo
    git add nix/hardware.nix
    git commit -m "chore(nix): add real Bee Link hardware configuration"
    git push

## Post-Install

- Bookmark Grafana: `https://grafana.ardent-forge.<tailnet>.ts.net`
- Bookmark Ardent Forge: `https://ardent-forge.<tailnet>.ts.net`
- Set up Grafana dashboards for system metrics and Ardent Forge tasks
- Create a Linear issue to test the full pipeline end-to-end
