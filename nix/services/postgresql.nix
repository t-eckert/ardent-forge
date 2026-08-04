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
      "grafana"
    ];

    ensureUsers = [
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

  # ── Nightly logical dumps ───────────────────────────────
  # /data is the persistent state root and is not in git, so until this the
  # only copy of the grafana database — dashboards, users, alert state — was
  # the live one under /data/postgresql.
  #
  # Dumps rather than a file-level copy of the data directory: copying a
  # running cluster's files is not crash-consistent and restores to a corrupt
  # cluster. A custom-format dump is also what any future off-box backup
  # should be shipping, so this is the prerequisite for restic rather than a
  # detour around it.
  #
  # This protects against fat-fingers, bad migrations and a botched upgrade.
  # It does not protect against the disk dying — the dumps land on the same
  # NVMe. Getting them off the box needs a restic repository and a credential
  # that has to be created by hand; see docs/backups.md.
  systemd.tmpfiles.rules = [
    "d /data/backup 0750 postgres postgres -"
    "d /data/backup/postgres 0750 postgres postgres -"
  ];

  systemd.services.postgres-dump = {
    description = "Nightly pg_dump of every non-template database";
    requires = [ "postgresql.service" ];
    after = [ "postgresql.service" ];

    serviceConfig = {
      Type = "oneshot";
      User = "postgres";
      Group = "postgres";
      # A failure here surfaces through the "systemd unit failed" alert, which
      # is the point — a backup that stops silently is worse than none, since
      # it is trusted.
      UMask = "0077";
    };

    path = [ config.services.postgresql.package pkgs.coreutils pkgs.findutils ];

    script = ''
      set -euo pipefail
      dir=/data/backup/postgres
      stamp=$(date -u +%Y%m%dT%H%M%SZ)

      # datallowconn excludes template0, which cannot be connected to and so
      # cannot be dumped.
      psql -At -c "SELECT datname FROM pg_database WHERE NOT datistemplate AND datallowconn" \
      | while read -r db; do
          [ -n "$db" ] || continue
          # Custom format: compressed, and restorable selectively with pg_restore.
          pg_dump --format=custom --file="$dir/$db-$stamp.dump" "$db"
        done

      # Keep a fortnight. Small databases, and anything older is likely to have
      # drifted too far from the current schema to be worth restoring anyway.
      find "$dir" -name '*.dump' -type f -mtime +14 -delete
    '';
  };

  systemd.timers.postgres-dump = {
    description = "Nightly pg_dump";
    wantedBy = [ "timers.target" ];
    timerConfig = {
      OnCalendar = "*-*-* 03:15:00";
      Persistent = true;   # catch up if the box was asleep at 03:15
      RandomizedDelaySec = "5m";
    };
  };
}
