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
      {
        # Caddy's admin API doubles as its metrics endpoint. Worth scraping
        # less for the metrics than for `up`: Caddy is the only way anything
        # on the tailnet is reachable, and nothing was watching it.
        job_name = "caddy";
        static_configs = [{
          targets = [ "127.0.0.1:2019" ];
        }];
      }
      {
        # Grafana serves under /svc/grafana (serve_from_sub_path), so bare
        # /metrics 301s and the path has to be spelled out.
        #
        # Scraping the alerting stack with the alerting stack is circular, and
        # deliberately so: if Grafana is down nothing can page anyway, but the
        # gap becomes visible in the target list and in history afterwards,
        # rather than silently looking like nothing ever went wrong.
        job_name = "grafana";
        metrics_path = "/svc/grafana/metrics";
        static_configs = [{
          targets = [ "127.0.0.1:3000" ];
        }];
      }
      {
        # Galley's backend runs a second server purely for metrics, on
        # METRICS_PORT from dev-suite/env/backend.env — not on the API port,
        # which is why /metrics on :8020 returns 404.
        #
        # This is a dev-suite process, not a system service: it is only up when
        # the suite is running, so `up{job="galley"}` is expected to be 0 much
        # of the time. That is a useful signal rather than a fault, and the
        # dashboards treat it as one.
        job_name = "galley";
        static_configs = [{
          targets = [ "127.0.0.1:8021" ];
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

      # ── Alerting ────────────────────────────────────────
      # Prometheus, Grafana and ntfy have all been running for months without
      # anything connecting them, which meant the box could be broken and say
      # nothing: the whole Chill Subs stack sat in a restart loop through a
      # reboot and was only noticed by someone going and looking.
      #
      # ntfy ships a pre-defined `grafana` template, so the webhook needs no
      # translator service in between — ?template=grafana turns Grafana's
      # payload into a titled notification, prefixed 🚨 firing / ✅ resolved.
      # Verified against the running ntfy before this landed.
      alerting = {
        contactPoints.settings = {
          apiVersion = 1;
          contactPoints = [{
            orgId = 1;
            name = "ntfy";
            receivers = [{
              uid = "ntfy-ardent-forge";
              type = "webhook";
              settings = {
                url = "http://127.0.0.1:8090/ardent-forge?template=grafana";
                httpMethod = "POST";
              };
            }];
          }];
        };

        policies.settings = {
          apiVersion = 1;
          policies = [{
            orgId = 1;
            receiver = "ntfy";
            group_by = [ "alertname" ];
            group_wait = "30s";
            group_interval = "5m";
            # Long enough that an unfixed problem does not become background
            # noise, short enough not to be forgotten.
            repeat_interval = "12h";
          }];
        };

        rules.settings = {
          apiVersion = 1;
          groups = [{
            orgId = 1;
            name = "ardent-forge";
            folder = "Alerts";
            interval = "1m";
            rules =
              let
                # Each rule is an instant query (A) fed to a threshold (C).
                # noDataState is OK throughout: every one of these is a
                # "something is wrong" signal, and absent data means the thing
                # is not running rather than that it is broken. Alerting on
                # absence here would fire every time the dev suite is off.
                promRule = { uid, title, expr, gt, for_, summary }: {
                  inherit uid title;
                  condition = "C";
                  for = for_;
                  noDataState = "OK";
                  execErrState = "Error";
                  annotations.summary = summary;
                  labels = { };
                  data = [
                    {
                      refId = "A";
                      relativeTimeRange = { from = 600; to = 0; };
                      datasourceUid = "prometheus";
                      model = {
                        refId = "A";
                        instant = true;
                        editorMode = "code";
                        expr = expr;
                      };
                    }
                    {
                      refId = "C";
                      relativeTimeRange = { from = 600; to = 0; };
                      datasourceUid = "__expr__";
                      model = {
                        refId = "C";
                        type = "threshold";
                        expression = "A";
                        conditions = [{
                          evaluator = { type = "gt"; params = [ gt ]; };
                        }];
                      };
                    }
                  ];
                };
              in
              [
                (promRule {
                  uid = "af-unit-failed";
                  title = "systemd unit failed";
                  expr = ''sum(node_systemd_unit_state{state="failed"})'';
                  gt = 0;
                  for_ = "5m";
                  summary = "A systemd unit on ardent-forge is in the failed state.";
                })
                (promRule {
                  uid = "af-disk-filling";
                  title = "root filesystem above 80%";
                  expr = ''100 - (node_filesystem_avail_bytes{mountpoint="/"} * 100 / node_filesystem_size_bytes{mountpoint="/"})'';
                  gt = 80;
                  for_ = "15m";
                  summary = "Root filesystem is over 80% full. /nix/store and /data are the usual causes.";
                })
                (promRule {
                  uid = "af-target-down";
                  title = "prometheus target down";
                  # galley is excluded deliberately: it is a dev-suite process
                  # and is legitimately down whenever the suite is not running.
                  expr = ''count(up{job!="galley"} == 0)'';
                  gt = 0;
                  for_ = "10m";
                  summary = "A Prometheus scrape target has been unreachable for 10 minutes.";
                })
                {
                  uid = "af-reindex-failing";
                  title = "typesense reindex failing";
                  condition = "C";
                  for = "10m";
                  noDataState = "OK";
                  execErrState = "OK";
                  annotations.summary =
                    "Mongo -> Typesense reindex is failing, so submitter search is drifting out of sync with the editor.";
                  labels = { };
                  data = [
                    {
                      refId = "A";
                      relativeTimeRange = { from = 900; to = 0; };
                      datasourceUid = "loki";
                      model = {
                        refId = "A";
                        queryType = "instant";
                        editorMode = "code";
                        expr = ''sum(count_over_time({job="chill-subs-dev", process="typesense-indexer"} |= `[reindex] FAILED` [10m]))'';
                      };
                    }
                    {
                      refId = "C";
                      relativeTimeRange = { from = 900; to = 0; };
                      datasourceUid = "__expr__";
                      model = {
                        refId = "C";
                        type = "threshold";
                        expression = "A";
                        conditions = [{
                          evaluator = { type = "gt"; params = [ 0 ]; };
                        }];
                      };
                    }
                  ];
                }
              ];
          }];
        };
      };
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

        # Loki deletes nothing by default. The compactor below was already
        # running, but compaction and retention are separate jobs — without
        # this the chunks under /data/loki were being tidied and then kept
        # forever. Prometheus has had retentionTime = "30d" all along; this is
        # the missing equivalent.
        retention_period = "30d";
      };

      compactor = {
        working_directory = "/data/loki/compactor";
        compaction_interval = "10m";

        # Retention is a compactor job and has to be switched on explicitly.
        # It also requires the index period to be 24h, which schema_config
        # above already sets, and a delete_request_store once enabled.
        retention_enabled = true;
        retention_delete_delay = "2h";
        delete_request_store = "filesystem";
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

      // Every container in the suite is logged twice: podman's journald driver
      // writes it directly, tagged <project>_<service>_<n>, and process-compose
      // relays the same stream on its own stdout because it runs `podman
      // compose up` in the foreground. Drop the direct copy and keep the relay,
      // which is the one that carries the process name and has no blank-line
      // padding. Scoped to the suite's unit so system containers — ntfy,
      // the-weather — are untouched.
      //
      // Mongo also sets `logging.driver: none` in its compose file, which stops
      // the duplicate at the source. This rule is what covers the containers
      // whose compose files live in shared repos and are not ours to change.
      rule {
        source_labels = ["__journal__systemd_user_unit", "__journal_syslog_identifier"]
        regex         = `cs-galley-suite\.service;[a-z0-9-]+_[a-z0-9-]+_[0-9]+`
        action        = "drop"
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

        // Having lifted the name into a label, drop the prefix from the line
        // itself — it is pure duplication in every log panel. Must come after
        // the two stages above, which still need it to be there.
        //
        // The capture group has to be named. stage.replace only substitutes
        // named groups: given an expression with none it matches, reports no
        // error, and leaves the line exactly as it was. Verified by running
        // this pipeline under `alloy run` against sample lines before landing
        // it — the unnamed version silently did nothing.
        //
        // The padding is one or more tabs and the trailing space is not always
        // present, hence \s+ and \s?. Anchored at ^, so an application's own
        // bracketed prefix further along the line survives — "[typesense-indexer
        // <tab>] [typesense-indexer] fetched 2" keeps the second one.
        stage.replace {
          expression = `^(?P<pcprefix>\[[a-z][a-z0-9-]*\s+\]\s?)`
          replace    = ""
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
