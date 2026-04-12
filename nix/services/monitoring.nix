# nix/services/monitoring.nix
{ config, pkgs, lib, locals, ... }:

{
  # ── Prometheus ──────────────────────────────────────────
  services.prometheus = {
    enable = true;
    port = 9090;
    stateDir = "prometheus";  # Relative to /var/lib/

    retentionTime = "30d";

    globalConfig = {
      scrape_interval = "15s";
      evaluation_interval = "15s";
    };

    scrapeConfigs = [
      {
        job_name = "node";
        static_configs = [{
          targets = [ "127.0.0.1:${toString config.services.prometheus.exporters.node.port}" ];
        }];
      }
      {
        job_name = "postgres";
        static_configs = [{
          targets = [ "127.0.0.1:9187" ];
        }];
      }
      {
        job_name = "ardent-forge";
        static_configs = [{
          targets = [ "127.0.0.1:7030" ];
        }];
        metrics_path = "/metrics";
      }
      {
        job_name = "loki";
        static_configs = [{
          targets = [ "127.0.0.1:3100" ];
        }];
      }
    ];
  };

  # Node exporter for system metrics
  services.prometheus.exporters.node = {
    enable = true;
    port = 9100;
    enabledCollectors = [
      "cpu" "diskstats" "filesystem" "loadavg"
      "meminfo" "netdev" "stat" "time" "vmstat"
    ];
  };

  # ── Grafana ─────────────────────────────────────────────
  services.grafana = {
    enable = true;
    dataDir = "/data/grafana";

    settings = {
      server = {
        http_addr = "127.0.0.1";
        http_port = 3000;
        root_url = "https://grafana.${locals.tailnetDomain}";
      };
      security = {
        admin_user = "admin";
        # Set on first boot, then managed in Grafana UI
        admin_password = "$__env{GRAFANA_ADMIN_PASSWORD}";
        secret_key = "$__file{/data/grafana/secret_key}";
      };
      database = {
        type = "postgres";
        host = "/run/postgresql";
        name = "grafana";
        user = "grafana";
      };
      analytics.reporting_enabled = false;
    };

    provision = {
      datasources.settings.datasources = [
        {
          name = "Prometheus";
          type = "prometheus";
          url = "http://127.0.0.1:9090";
          isDefault = true;
        }
        {
          name = "Loki";
          type = "loki";
          url = "http://127.0.0.1:3100";
        }
      ];
    };
  };

  # ── Loki ────────────────────────────────────────────────
  services.loki = {
    enable = true;
    dataDir = "/data/loki";

    configuration = {
      auth_enabled = false;

      server = {
        http_listen_port = 3100;
        grpc_listen_port = 9096;
      };

      common = {
        path_prefix = "/data/loki";
        replication_factor = 1;
        ring.kvstore.store = "inmemory";
        ring.instance_addr = "127.0.0.1";
      };

      schema_config.configs = [{
        from = "2024-01-01";
        store = "tsdb";
        object_store = "filesystem";
        schema = "v13";
        index = {
          prefix = "index_";
          period = "24h";
        };
      }];

      storage_config.filesystem.directory = "/data/loki/chunks";

      limits_config = {
        ingestion_rate_mb = 10;
        ingestion_burst_size_mb = 20;
      };

      compactor = {
        working_directory = "/data/loki/compactor";
        compaction_interval = "10m";
      };
    };
  };

  # Alloy — ships systemd journal logs to Loki (replaces deprecated Promtail)
  services.alloy = {
    enable = true;
  };

  environment.etc."alloy/config.alloy".text = ''
    loki.source.journal "journal" {
      max_age    = "12h"
      labels     = { job = "systemd-journal", host = "ardent-forge" }
      forward_to = [loki.write.local.receiver]
    }

    loki.write "local" {
      endpoint {
        url = "http://127.0.0.1:3100/loki/api/v1/push"
      }
    }
  '';
}
