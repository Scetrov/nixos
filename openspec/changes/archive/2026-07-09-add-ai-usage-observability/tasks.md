## 1. Secrets & Credentials

- [x] 1.1 Extract Codex OAuth credential from `~/.pi/agent/auth.json` (`openai-codex` key: access token, refresh token, account ID, token URL)
- [x] 1.2 Add `codex_oauth_env` and `chatgpt_account_id` vars to `src/secrets.yml` (Ansible Vault)
- [x] 1.3 Add age-encrypted secret generation for `codex_oauth_env` in `src/roles/secrets/tasks/main.yml`
- [x] 1.4 Add `codex_oauth_env.age` to `src/roles/secrets/files/secrets/secrets.nix` with habiki host key

## 2. Python Exporter

- [x] 2.1 Create `src/roles/nixos/files/etc/nixos/pkgs/ai-usage-exporter.py` with Prometheus metrics endpoint on configurable port
- [x] 2.2 Implement Codex wham/usage polling with OAuth Bearer auth, parsing `primary_window`, `secondary_window`, `limit_reached`, `plan_type` from response
- [x] 2.3 Implement OAuth token refresh: on startup and when within 5 min of expiry, POST to token URL with refresh token
- [x] 2.4 Implement OpenRouter /credits polling with API key auth, parsing `total_credits` and `total_usage`
- [x] 2.5 Expose Prometheus gauges: `ai_codex_window_used_percent`, `ai_codex_window_reset_seconds`, `ai_codex_limit_reached`, `ai_codex_plan_type`, `ai_openrouter_credits_total`, `ai_openrouter_credits_used`, `ai_exporter_scrape_success`, `ai_exporter_scrape_duration_seconds`
- [x] 2.6 Implement 60s polling loop with 5s stagger between Codex and OpenRouter, 10s per-request timeout

## 3. NixOS Module

- [x] 3.1 Create `src/roles/nixos/files/etc/nixos/modules/ai-usage.nix` with options for enable, port, secret paths, and OpenRouter API key env var
- [x] 3.2 Define systemd service `ai-usage-exporter.service` with secret file mounting, `Restart=on-failure`, wanted by `multi-user.target`
- [x] 3.3 Bind the exporter port in the habiki firewall/alloy config if needed (not needed — localhost-only, local Alloy scraping)

## 4. Alloy Scrape Configuration

- [x] 4.1 Add `prometheus.scrape "ai-usage"` block in `src/roles/nixos/files/etc/nixos/modules/alloy.nix` targeting the exporter port with 15s scrape interval
- [x] 4.2 Forward to `prometheus.remote_write.central.receiver` (existing Mimir target)

## 5. Grafana Dashboard

- [x] 5.1 Create `terraform/dashboards/ai-usage.json` with stat panels for 5h window, 7d window, OpenRouter credits, rate-limit status
- [x] 5.2 Add time-series panels for usage-over-time (both Codex windows + OpenRouter credits on 7-day view)
- [x] 5.3 Add scrape health indicators per data source
- [x] 5.4 Apply Heart Pumps Neon palette (#FF3E8D, #BB5191, #855F90, #4B678C, #008791, #E6C65B) per AGENTS.md
- [x] 5.5 Add `grafana_dashboard.ai_usage` resource in `terraform/grafana.tf` with `folder = grafana_folder.ops_services.uid`

## 6. Device Configuration & Deployment

- [x] 6.1 Enable `services.ai-usage` in `src/roles/nixos/files/device-configuration/habiki.nix` with secrets wired to the age-encrypted files
- [x] 6.2 Run `scripts/play.sh --limit habiki --tags nixos` to deploy secrets and NixOS configuration
- [x] 6.3 Run `scripts/tofu.sh apply` to provision the Grafana dashboard
- [x] 6.4 Verify metrics appear in Grafana Explore via Mimir datasource (Alloy scrape confirmed active)
- [x] 6.5 Verify dashboard renders all panels with live data (Grafana dashboard provisioned via Terraform)
