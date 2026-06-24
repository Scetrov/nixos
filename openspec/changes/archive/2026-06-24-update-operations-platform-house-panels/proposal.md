## Why

The Operations Platform Overview is the landing dashboard for day-to-day observability, but it does not yet surface the most important house climate and air-quality signals. Adding house-level environmental summaries there lets operators spot indoor comfort or air-quality issues without first drilling into the Home Assistant dashboards.

## What Changes

- Add house environmental panels to the existing Operations Platform Overview dashboard.
- Surface average indoor temperature and average outdoor temperature as landing-page metrics or trends.
- Surface average indoor humidity and average outdoor humidity as landing-page metrics or trends.
- Surface CO2 and air-quality status using the retained Home Assistant environmental telemetry already exported to Mimir.
- Keep dashboard definitions declarative under the existing Terraform-managed Grafana workflow.
- No breaking changes.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `grafana-operations-portal`: Extend the Operations Platform Overview dashboard requirements to include house climate and air-quality summary panels backed by Home Assistant telemetry.

## Impact

- Affects `terraform/dashboards/platform-overview.json`.
- May reuse query patterns and curated Home Assistant sensor allowlists from `terraform/dashboards/home-assistant-environment.json` and `terraform/dashboards/home-assistant-house-overview.json`.
- Uses the existing Grafana folder/dashboard provisioning in `terraform/grafana.tf`; no new secrets, routes, ports, or identity resources are expected.
- Validation should include JSON formatting plus targeted OpenTofu planning through `./scripts/tofu.sh` before deployment.
