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
      "meminfo" "netdev" "stat" "systemd" "time" "vmstat"
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
        root_url = "https://${locals.tailnetDomain}/svc/grafana/";
        serve_from_sub_path = true;
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
      datasources.settings = {
        deleteDatasources = [
          { name = "Prometheus"; orgId = 1; }
          { name = "Loki"; orgId = 1; }
        ];
        datasources = [
          {
            name = "Prometheus";
            type = "prometheus";
            uid = "prometheus";
            url = "http://127.0.0.1:9090";
            isDefault = true;
            orgId = 1;
          }
          {
            name = "Loki";
            type = "loki";
            uid = "loki";
            url = "http://127.0.0.1:3100";
            orgId = 1;
          }
        ];
      };

      dashboards.settings.providers = [
        {
          name = "default";
          options.path = "/data/ardent-forge/repo/grafana/dashboards";
          options.foldersFromFilesStructure = true;
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

        # Alloy ships the whole journal to Loki, including Loki's own logs, so
        # anything Loki logs is amplified back into itself. At info level its
        # per-table compaction chatter was ~550k journal lines a week — the
        # largest log producer on the box by an order of magnitude.
        log_level = "warn";
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

  # The `__journal_*` fields are internal labels: they are dropped when an entry
  # leaves loki.source.journal, so a downstream loki.relabel component never
  # sees them. The rules have to be handed to the source itself via
  # `relabel_rules`, which is why loki.relabel here has an empty forward_to —
  # it exists only to export `.rules`.
  environment.etc."alloy/config.alloy".text = ''
    loki.source.journal "journal" {
      max_age       = "12h"
      labels        = { host = "ardent-forge" }
      relabel_rules = loki.relabel.journal.rules
      forward_to    = [loki.process.dev_suite.receiver]
    }

    loki.relabel "journal" {
      forward_to = []

      rule {
        source_labels = ["__journal__systemd_unit"]
        target_label  = "unit"
      }

      // Anything the user manager starts reports _SYSTEMD_UNIT=user@1000.service,
      // which says nothing about what actually logged. The real name is in
      // _SYSTEMD_USER_UNIT. Match on (.+) rather than the default (.*) so this
      // only fires for user units instead of blanking `unit` for system ones.
      rule {
        source_labels = ["__journal__systemd_user_unit"]
        regex         = "(.+)"
        target_label  = "unit"
      }

      rule {
        source_labels = ["__journal_priority_keyword"]
        target_label  = "level"
      }

      // Default; overridden for the dev suite below.
      rule {
        target_label = "job"
        replacement  = "systemd-journal"
      }

      // The Chill Subs dev suite out-logs the entire rest of the box and is not
      // system state — it is one developer's stack running in the foreground.
      // Give it its own job so it can be read, and ignored, on its own.
      rule {
        source_labels = ["__journal__systemd_user_unit"]
        regex         = `cs-galley-suite\.service`
        target_label  = "job"
        replacement   = "chill-subs-dev"
      }

      // The suite's containers log to the journal themselves, tagged by podman
      // as <project>_<service>_<n>. Capture the service, not the project: the
      // infra compose file runs postgres, redis and s3proxy all under project
      // "local", so keying on the project would collapse the three into one.
      // Keyed on the user unit too, so `process` stays a dev-suite-only label.
      rule {
        source_labels = ["__journal__systemd_user_unit", "__journal_syslog_identifier"]
        regex         = `cs-galley-suite\.service;[a-z0-9-]+_([a-z0-9-]+)_[0-9]+`
        target_label  = "process"
      }
    }

    // Everything else from the suite arrives on process-compose's own stdout,
    // which relays each child prefixed with "[name<TAB>]" — on those lines the
    // prefix is the only thing identifying the process. The trailing whitespace
    // is what keeps this off ordinary log lines that merely start with "[".
    loki.process "dev_suite" {
      forward_to = [loki.write.local.receiver]

      stage.match {
        selector = `{job="chill-subs-dev"}`

        stage.regex {
          expression = `^\[(?P<process>[a-z][a-z0-9-]*)\s+\]`
        }

        stage.labels {
          values = { process = "" }
        }
      }
    }

    loki.write "local" {
      endpoint {
        url = "http://127.0.0.1:3100/loki/api/v1/push"
      }
    }
  '';
}
