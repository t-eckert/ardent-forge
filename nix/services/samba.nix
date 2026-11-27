# nix/services/samba.nix
#
# The home directory and the drop folder as SMB shares, for Finder on the Mac
# and the Files app on the phone: smb://ardent-forge.<tailnet>/home and /drop.
#
# Write access to ~ is a shell. Whoever can write ~/.zshrc or
# ~/.ssh/authorized_keys runs code as the user, and ~ also holds the Claude,
# gh and OpenCode logins. So, unlike everything Caddy serves, this is not open
# to the tailnet at large:
#
#   - One user may log in, with a Samba password. There is no guest access.
#   - The `home` share hides every name that starts with a dot, at any depth.
#     That takes the credentials and the login files out of reach. It also
#     hides .git, .env and .gitignore inside repos: work on those over SSH.
#   - Only tailnet and loopback addresses are answered, and the firewall does
#     not open 445 on the LAN. Never set openFirewall here.
#
# The password is set by hand and lives in /var/lib/samba/private, outside this
# repo. On a fresh install, and to change it:
#
#   sudo smbpasswd -a <username>
#
# Keep a copy in the `Ardent Forge` 1Password vault. Port 445 can be narrowed
# further to particular devices with a Tailscale ACL, which is not managed here.
{ lib, locals, ... }:

let
  user = locals.username;

  # macOS keeps Finder metadata in alternate data streams. With these it lands
  # in extended attributes on the file itself, not in ._ files beside it.
  # nfs_aces is off so the Mac cannot rewrite Unix modes through ACLs.
  macos = {
    "vfs objects" = "catia fruit streams_xattr";
    "fruit:metadata" = "stream";
    "fruit:nfs_aces" = "no";
  };
in
{
  services.samba = {
    enable = true;

    # NetBIOS name service and domain membership: nothing on a tailnet uses
    # either. Clients connect by MagicDNS name.
    nmbd.enable = false;
    winbindd.enable = false;

    settings = {
      global = {
        "server string" = "ardent-forge";
        "server role" = "standalone server";

        # Tailscale's address ranges and loopback, by address so it holds
        # whether or not tailscale0 is up when smbd starts.
        "hosts allow" = "100.64.0.0/10 fd7a:115c:a1e0::/48 127.0.0.1 ::1";
        "hosts deny" = "ALL";

        "map to guest" = "never";
        "restrict anonymous" = 2;

        "server min protocol" = "SMB3_00";
        "server smb encrypt" = "required";

        # A symlink that leaves the share is refused. Most of what home-manager
        # links into ~ points at /nix/store and will not open; that is the
        # price of a symlink not being a way out of the share.
        "wide links" = "no";

        "logging" = "systemd";

        "load printers" = "no";
        "printing" = "bsd";
        "printcap name" = "/dev/null";
        "disable spoolss" = "yes";
      };

      home = macos // {
        path = "/home/${user}";
        comment = "Home directory, dotfiles hidden";
        "valid users" = user;
        "read only" = "no";
        "guest ok" = "no";
        # Matches at every depth, files and directories both. Samba cannot
        # anchor a veto to the top of a share.
        "veto files" = "/.*/";
        # A directory holding hidden names cannot be removed from the Mac.
        "delete veto files" = "no";
      };

      # The same directory Caddy's WebDAV `drop` node serves, and the one the
      # screenshots skill reads.
      drop = macos // {
        path = "/var/lib/shared";
        comment = "Drop folder";
        "valid users" = user;
        "read only" = "no";
        "guest ok" = "no";
        "force group" = "users";
        "create mask" = "0664";
        "directory mask" = "2775";
        "veto files" = "/.DS_Store/";
        "delete veto files" = "yes";
      };
    };
  };
}
