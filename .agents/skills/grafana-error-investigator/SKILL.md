---
name: grafana-error-investigator
description: Investigates errors and warnings logged in Grafana (Loki). Use this skill when the user wants to identify, prioritize, and fix issues reported in the system logs. It sources credentials from ~/env/grafana.env and queries Loki for recent Errors and Warnings.
---

# Grafana Error Investigator

This skill helps you investigate system health by querying Loki for Errors and Warnings, presenting them as a prioritized list, and offering to fix them.

## Workflow

1. **Source Credentials**: Always source `~/env/grafana.env` to obtain `GRAFANA_SERVICE_TOKEN`.
2. **Query Loki**: Use `curl` to query the Loki API at `https://metrics.net.scetrov.live/loki/api/v1/query_range`.
3. **Analyze Results**: 
   - Focus on logs from the last 1-6 hours.
   - Filter for strings like "error", "warn", "fail", "critical".
   - Group similar log messages to identify recurring issues.
4. **Prioritize**: Rank issues by frequency and perceived severity.
5. **Present**: Show a clean list of top issues.
6. **Act**: Offer to investigate and fix the top three items.

## Automated Investigation

You can use the provided script to get a prioritized list of errors:

```bash
.agents/skills/grafana-error-investigator/scripts/investigate_errors.sh [hours]
```

## Presentation and Action

After running the investigation:
1. **List Results**: Present the top errors found, grouped by frequency.
2. **Prioritize**: Briefly explain why certain items are higher priority (e.g., service down vs. intermittent warning).
3. **Offer Help**: Explicitly offer to work on the top three items from the list.
4. **Follow-up**: If the user selects an item, use other Gemini CLI tools (research, replace, run_shell_command) to diagnose and fix the issue.

## Guidance for Error Analysis

- Look for stack traces or specific error codes.
- Identify which service/job is producing the most errors.
- Check if the errors correlate with recent deployments or changes.
- If multiple services are failing, look for a common dependency (e.g., database, network).
