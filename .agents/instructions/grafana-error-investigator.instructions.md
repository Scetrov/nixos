---
description: This file provides instructions for investigating errors and warnings in Grafana/Loki.
applyTo: "**/*"
---

# Grafana Error Investigation

When troubleshooting system health or responding to reports of errors, use the following workflow to query and analyze logs from the central observability stack.

## 🔑 Authentication
- Credentials are stored in `~/env/grafana.env`.
- Source this file to obtain `GRAFANA_SERVICE_TOKEN`.
- Query Loki through Grafana's datasource API at `https://metrics.net.scetrov.live/grafana/api/ds/query`.
- The Loki datasource UID is `loki`.
- Direct `https://metrics.net.scetrov.live/loki` queries are protected by Authentik and redirect to interactive login.

## 🔍 Log Query Workflow
1. **Query Loki:** Use Grafana's `/grafana/api/ds/query` endpoint with the `loki` datasource.
2. **Filter:** Focus on logs containing `error`, `warn`, `failed`, `failure`, `critical`, `fatal`, or `exception`.
3. **Time Range:** Start with the last 6 hours (`date -d "6 hours ago" +%s%3N` for Grafana milliseconds).
4. **Analysis:**
   - Group messages by frequency to identify high-impact recurring issues.
   - Filter out noise from internal monitoring, DNS `NOERROR` query logs, and healthy container health events.
   - Correlate errors across services using the `job` label.

## 🛠 Tooling
A pre-configured investigation script is available at:
`.agents/skills/grafana-error-investigator/scripts/investigate_errors.sh`

Usage:
```bash
./.agents/skills/grafana-error-investigator/scripts/investigate_errors.sh [hours]
```

## 📋 Reporting
- Present findings as a prioritized list.
- Prioritize by severity (service downtime > intermittent warnings) and frequency.
- Propose specific remediations for the top findings.
