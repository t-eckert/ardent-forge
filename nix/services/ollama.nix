# nix/services/ollama.nix
{ config, pkgs, lib, ... }:

{
  services.ollama = {
    enable = true;
    host = "127.0.0.1";
    port = 11434;

    # CPU-only — no GPU on the Bee Link
    package = pkgs.ollama-cpu;

    # Models stored in default location /var/lib/ollama
    #
    # No models are pulled declaratively. There used to be a oneshot that
    # pulled qwen2.5:3b for the task-triage path; with that gone, which model
    # is worth having is a per-experiment decision. Pull on demand:
    #   ollama pull <model>
  };
}
