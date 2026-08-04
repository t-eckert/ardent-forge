# nix/services/smartd.nix
{ config, pkgs, lib, ... }:

let
  # smartd's NixOS module always injects its own "-m <nomailer> -M exec
  # smartd-notify.sh" into every directive, and that script is the only thing
  # smartd calls. Adding a second -M exec through defaults.autodetected does
  # not add a second handler — it produces a directive with two conflicting
  # -M exec clauses. The supported way in is notifications.mail.mailer, which
  # smartd-notify.sh invokes as `mailer -i <recipient>` with the message on
  # stdin, so this stands in for sendmail.
  #
  # Posted straight to ntfy rather than routed through Grafana: there is no
  # SMART exporter in this nixpkgs (services.prometheus.exporters has no
  # smartctl, disk or nvme entry) and node_exporter's nvme collector reports
  # only inventory — model, serial, capacity — with nothing about health.
  # Going direct also means the warning does not depend on Prometheus and
  # Grafana being up, which is the wrong assumption for a message whose
  # subject is the disk they are stored on.
  smartd-ntfy = pkgs.writeShellScriptBin "smartd-ntfy" ''
    # Called as: smartd-ntfy -i <recipient>. The arguments are sendmail's, and
    # are irrelevant here; the message arrives on stdin.
    body="$(${pkgs.coreutils}/bin/cat)"
    ${pkgs.curl}/bin/curl -s --max-time 10 \
      -H "Title: SMART warning on ''${SMARTD_DEVICESTRING:-ardent-forge}" \
      -H "Priority: urgent" \
      -H "Tags: rotating_light,floppy_disk" \
      -d "$body" \
      http://127.0.0.1:8090/ardent-forge || true
  '';
in
{
  # The box runs a single consumer NVMe with no RAID and, as of this commit,
  # no backups. That combination makes early warning the only thing between a
  # disk fault and losing /data, so it is worth having even though SMART is an
  # imperfect predictor.
  services.smartd = {
    enable = true;
    autodetect = true;

    notifications = {
      mail = {
        enable = true;
        recipient = "root";
        mailer = "${smartd-ntfy}/bin/smartd-ntfy";
      };
      # Harmless second channel; nobody is usually logged in to see it.
      wall.enable = true;
    };

    # defaults.autodetected is deliberately left at its default of "-a", which
    # monitors health, temperature and the error log — the subset that means
    # anything on NVMe. The ATA-only directives (-o offline tests, -S attribute
    # autosave, -s self-test schedules) would only make this device log
    # warnings about not supporting them.
  };
}
