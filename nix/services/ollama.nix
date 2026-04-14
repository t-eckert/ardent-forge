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
  };

  # Pull a small, fast model after Ollama starts
  systemd.services.ollama-model-pull = {
    description = "Pull default Ollama model for task triage";
    wantedBy = [ "multi-user.target" ];
    after = [ "ollama.service" ];
    requires = [ "ollama.service" ];

    # Ollama's Go envconfig panics on startup if $HOME is unset — the
    # oneshot unit had no HOME, which is why this was failing on every
    # deploy and painting the whole pipeline red.
    environment = {
      HOME = "/var/lib/ollama";
    };

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = "${pkgs.ollama-cpu}/bin/ollama pull qwen2.5:3b";
      # Best-effort model pull — don't fail the whole nixos-rebuild if this
      # can't reach out to the registry. The main ollama service is what
      # actually serves inference.
      SuccessExitStatus = "0 1 2";
    };
  };
}
