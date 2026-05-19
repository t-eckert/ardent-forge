# nix/services/tailscale-portforward.nix
#
# Dev-server exposure is now managed dynamically by Ardent Forge's
# TailscaleServe module (forge/tailscale/serve.py) at startup.
#
# Each repo that declares a dev_port in repo.yaml gets a
# `tailscale serve --https=<port>` entry, making it reachable at
# https://<machine>.<tailnet>:<port>/ with TLS handled by Tailscale.
#
# The old nftables blanket-redirect (all TCP on tailscale0 → localhost)
# has been removed. Only explicitly declared dev_port entries are exposed.
# Ardent Forge itself is served by Caddy at https://<tailnet-domain>/.
{ ... }: {}
