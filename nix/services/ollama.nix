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

    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      ExecStart = "${pkgs.ollama}/bin/ollama pull qwen2.5:3b";
    };
  };
}
