# Copy to locals.nix and fill in your values.
# locals.nix is gitignored — it never leaves this machine.
{
  # Your username on the system
  username = "youruser";

  # Your Tailscale tailnet domain (find via: tailscale status)
  tailnetDomain = "ardent-forge.example.ts.net";

  # SSH public keys authorized to log in
  sshKeys = [
    "ssh-ed25519 AAAA... you@host"
  ];

  # GitHub repos to clone into ~/Repos/github.com/owner/repo on first boot.
  # GH_TOKEN is resolved from 1Password at start time, so private repos work.
  # Add a new entry and run `sudo systemctl start workspace-init` to clone
  # without rebooting.
  workspaceRepos = [
    "owner/repo"
  ];
}
