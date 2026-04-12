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
}
