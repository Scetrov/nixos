# UniFi Network Logging

This guide documents the repository-managed UniFi network log integration for the UCG Ultra.

## What this change provisions

- A dedicated Vector syslog receiver on `habiki`
- UDP listener on port `5514`
- Firewall allow rule scoped to the UCG Ultra source IP `10.229.0.1`
- Loki labels `service=unifi-network` and `host=ucg-ultra`
- A Grafana dashboard named **UniFi Network Logs** in **Operations / Services**

The managed pipeline retains:

- firewall events
- threat / IDS / IPS events
- warning-or-higher non-firewall events

## UniFi Network Application configuration

Configure the UniFi controller or console remote logging destination to send syslog to:

- **Host / IP:** `10.229.10.2`
- **Protocol:** UDP
- **Port:** `5514`

If the UI supports log scope or categories, enable the gateway or network security events needed for firewall, IDS or IPS, and warning-level operational visibility.

## Deployment workflow

Apply the host-side changes narrowly to `habiki`:

```bash
./scripts/play.sh --limit habiki --tags nixos
```

Apply the declarative Grafana dashboard changes through the OpenTofu wrapper:

```bash
./scripts/tofu.sh -chdir=terraform apply
```

## Validation

### 1. Confirm the receiver is listening on habiki

After the NixOS deployment, verify the Vector service is running and bound to UDP `5514`.

Suggested checks on `habiki`:

```bash
systemctl status vector
ss -lunp | grep 5514
```

### 2. Confirm logs arrive in Loki

Open Grafana Explore and run:

```logql
{service="unifi-network"}
```

Then verify that retained events include structured fields such as:

- `event_class`
- `action`
- `src_ip`
- `dst_ip`
- `src_port`
- `dst_port`
- `protocol`
- `severity`

### 3. Confirm the dashboard renders

Open:

- **Operations / Platform / Operations Service Catalog**
- **Operations / Services / UniFi Network Logs**

Validate that the dashboard shows:

- recent firewall actions
- allow vs block trends
- top source IPs
- destination ports or protocol breakdowns
- recent threat events
- recent warning or error events

## Troubleshooting

- If no logs arrive, re-check the UniFi remote logging host, UDP port, and the UCG Ultra source IP.
- If the Vector service is running but Grafana is empty, test the base Loki query `{service="unifi-network"}` in Explore before debugging dashboard panels.
- If only low-value events appear missing, remember that the pipeline intentionally drops non-firewall messages below warning severity.
