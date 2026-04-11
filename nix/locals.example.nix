# Copy to locals.nix and fill in your values.
# locals.nix is gitignored — it never leaves this machine.
{
  # Your Tailscale tailnet domain (find via: tailscale status)
  tailnetDomain = "ardent-forge.example.ts.net";

  # SSH public keys authorized to log in as thomaseckert
  sshKeys = [
    "ssh-ed25519 AAAA... you@host"
  ];
}
