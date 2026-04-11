# nix/services/postgresql.nix
{ config, pkgs, lib, ... }:

{
  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_17;
    dataDir = "/data/postgresql";

    enableTCPIP = true;

    # Only allow connections from Tailscale and localhost
    authentication = pkgs.lib.mkForce ''
      # TYPE  DATABASE        USER            ADDRESS                 METHOD
      local   all             all                                     peer
      host    all             all             127.0.0.1/32            scram-sha-256
      host    all             all             100.64.0.0/10           scram-sha-256
    '';

    settings = {
      # ── Memory (tuned for 16GB RAM, shared with other services) ──
      shared_buffers = "2GB";
      effective_cache_size = "12GB";
      maintenance_work_mem = "512MB";
      work_mem = "32MB";

      # ── Connections ──
      max_connections = 200;
      max_worker_processes = 4;

      # ── WAL ──
      max_wal_size = "4GB";
      wal_compression = "on";
      checkpoint_timeout = "10min";

      # ── Autovacuum (SSD-optimized) ──
      autovacuum_vacuum_cost_delay = "2ms";
      autovacuum_vacuum_cost_limit = 2000;

      # ── Logging ──
      log_min_duration_statement = 1000;  # Log queries > 1s
    };

    # Create databases for services
    ensureDatabases = [
      "ardent_forge"
      "grafana"
    ];

    ensureUsers = [
      {
        name = "ardent_forge";
        ensureDBOwnership = true;
      }
      {
        name = "grafana";
        ensureDBOwnership = true;
      }
    ];
  };

  # Postgres exporter for Prometheus
  services.prometheus.exporters.postgres = {
    enable = true;
    port = 9187;
    runAsLocalSuperUser = true;
  };
}
