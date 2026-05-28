{
  config,
  lib,
  ...
}:

let
  cfg = config.scetrov.services.unifi-network-logs;
in
{
  options.scetrov.services.unifi-network-logs = {
    enable = lib.mkEnableOption "UniFi network log ingestion";

    listenAddress = lib.mkOption {
      type = lib.types.str;
      default = "0.0.0.0";
      description = "Listen address for the UniFi syslog receiver.";
    };

    port = lib.mkOption {
      type = lib.types.port;
      default = 5514;
      description = "UDP port used for UniFi remote syslog ingestion.";
    };

    sourceAddress = lib.mkOption {
      type = lib.types.str;
      default = "10.229.0.1";
      description = "Expected source IP address for the UCG Ultra syslog sender.";
    };

    deviceHostLabel = lib.mkOption {
      type = lib.types.str;
      default = "ucg-ultra";
      description = "Stable host label applied to retained UniFi logs in Loki.";
    };
  };

  config = lib.mkIf cfg.enable {
    services.vector = {
      enable = true;
      settings = {
        sources.unifi_syslog = {
          type = "syslog";
          mode = "udp";
          address = "${cfg.listenAddress}:${toString cfg.port}";
          max_length = 65536;
        };

        transforms.unifi_normalize = {
          type = "remap";
          inputs = [ "unifi_syslog" ];
          source = ''
            .service = "unifi-network"
            .host = "${cfg.deviceHostLabel}"
            .collector_host = "${config.networking.hostName}"
            .collector_source_ip = "${cfg.sourceAddress}"
            .raw_message = to_string!(.message)
            .event_class = "system"
            .action = "unknown"
            .rule_name = null
            .rule_description = null
            .src_ip = null
            .dst_ip = null
            .src_port = null
            .dst_port = null
            .protocol = "unknown"
            .in_interface = null
            .out_interface = null
            .flow_id = null
            .threat_signature = null
            .threat_category = null
            .keep = false

            severity_text = "info"
            if .severity != null {
              severity_text = downcase(to_string!(.severity))
            } else if .severity_keyword != null {
              severity_text = downcase(to_string!(.severity_keyword))
            }
            if severity_text == "0" {
              .severity = "emerg"
            } else if severity_text == "1" {
              .severity = "alert"
            } else if severity_text == "2" {
              .severity = "crit"
            } else if severity_text == "3" {
              .severity = "error"
            } else if severity_text == "4" {
              .severity = "warning"
            } else if severity_text == "5" {
              .severity = "notice"
            } else if severity_text == "6" {
              .severity = "info"
            } else if severity_text == "7" {
              .severity = "debug"
            } else if severity_text == "warn" {
              .severity = "warning"
            } else if severity_text == "err" {
              .severity = "error"
            } else if severity_text == "critical" {
              .severity = "crit"
            } else if severity_text == "emergency" {
              .severity = "emerg"
            } else {
              .severity = severity_text
            }

            firewall_match = parse_regex(.raw_message, r'(?P<rule_block>\[[^\]]+\])?.*?(?:DESCR="(?P<rule_description>[^"]+)"\s+)?IN=(?P<in_interface>\S*)\s+OUT=(?P<out_interface>\S*)\s+.*?SRC=(?P<src_ip>\d+\.\d+\.\d+\.\d+)\s+DST=(?P<dst_ip>\d+\.\d+\.\d+\.\d+).*?PROTO=(?P<protocol>\w+)(?:\s+SPT=(?P<src_port>\d+))?(?:\s+DPT=(?P<dst_port>\d+))?.*?(?:\s+ID=(?P<flow_id>\S+))?') ?? null
            if firewall_match != null {
              .event_class = "firewall"
              . = merge!(., firewall_match)
            }

            action_match = parse_regex(.raw_message, r'\[(?P<rule_name>[A-Za-z0-9_.:-]+)-(?P<action_code>[ABR])\]') ?? null
            message_downcase = downcase!(.raw_message)
            if action_match != null {
              .rule_name = action_match.rule_name
              if action_match.action_code == "A" {
                .action = "allow"
              } else if action_match.action_code == "B" {
                .action = "block"
              } else if action_match.action_code == "R" {
                .action = "reject"
              }
            } else if match!(message_downcase, r'\b(block|drop|deny|reject)\b') {
              .action = "block"
            } else if match!(message_downcase, r'\b(allow|accept|pass)\b') {
              .action = "allow"
            }

            threat_match = match!(message_downcase, r'(threat|ids|ips|intrusion)')
            if threat_match {
              .event_class = "threat"
            }

            threat_signature_match = parse_regex(.raw_message, r'(?i)(?:signature|sig(?:nature)?|rule)[:= ]+"?(?P<threat_signature>[^",]+)"?') ?? null
            if threat_signature_match != null {
              .threat_signature = threat_signature_match.threat_signature
            }

            threat_category_match = parse_regex(.raw_message, r'(?i)(?:category|classification)[:= ]+"?(?P<threat_category>[^",]+)"?') ?? null
            if threat_category_match != null {
              .threat_category = threat_category_match.threat_category
            }

            warning_or_higher = match!(.severity, r'^(warning|warn|error|err|crit|critical|alert|emerg|emergency)$')
            if .event_class == "firewall" || .event_class == "threat" || warning_or_higher {
              .keep = true
            }
          '';
        };

        transforms.unifi_keep = {
          type = "filter";
          inputs = [ "unifi_normalize" ];
          condition = ".keep == true";
        };

        transforms.unifi_cleanup = {
          type = "remap";
          inputs = [ "unifi_keep" ];
          source = ''
            del(.keep)
            del(.rule_block)
          '';
        };

        sinks.unifi_loki = {
          type = "loki";
          inputs = [ "unifi_cleanup" ];
          endpoint = "http://127.0.0.1:3100";
          encoding.codec = "json";
          out_of_order_action = "accept";
          labels = {
            service = "{{ service }}";
            host = "{{ host }}";
            event_class = "{{ event_class }}";
            action = "{{ action }}";
            severity = "{{ severity }}";
            protocol = "{{ protocol }}";
          };
        };
      };
    };

    networking.firewall.extraCommands = ''
      iptables -A nixos-fw -p udp -s ${cfg.sourceAddress} --dport ${toString cfg.port} -j nixos-fw-accept
    '';

    networking.firewall.extraStopCommands = ''
      iptables -D nixos-fw -p udp -s ${cfg.sourceAddress} --dport ${toString cfg.port} -j nixos-fw-accept 2>/dev/null || true
    '';
  };
}
