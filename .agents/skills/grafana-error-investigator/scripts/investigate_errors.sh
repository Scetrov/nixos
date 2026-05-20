#!/usr/bin/env bash

# Source credentials
if [ -f ~/env/grafana.env ]; then
    source ~/env/grafana.env
else
    echo "Error: ~/env/grafana.env not found."
    exit 1
fi

if [ -z "$GRAFANA_SERVICE_TOKEN" ]; then
    echo "Error: GRAFANA_SERVICE_TOKEN not found in ~/env/grafana.env."
    exit 1
fi

GRAFANA_URL=${GRAFANA_URL:-"https://metrics.net.scetrov.live/grafana"}
LOKI_DATASOURCE_UID=${LOKI_DATASOURCE_UID:-"loki"}
HOURS=${1:-6}
START_MS=$(date -d "$HOURS hours ago" +%s%3N)
END_MS=$(date +%s%3N)

# Query Loki through Grafana. Direct /loki queries are protected by Authentik,
# while Grafana's datasource API accepts the service account token.
QUERY='{job=~".+"} |~ "(?i)(^|[^a-z])(error|warn|failed|failure|critical|fatal|exception)([^a-z]|$)"'

REQUEST_JSON=$(jq -n \
    --arg from "$START_MS" \
    --arg to "$END_MS" \
    --arg datasource_uid "$LOKI_DATASOURCE_UID" \
    --arg expr "$QUERY" \
    '{
      queries: [
        {
          refId: "A",
          datasource: {type: "loki", uid: $datasource_uid},
          expr: $expr,
          queryType: "range",
          maxLines: 3000,
          intervalMs: 1000
        }
      ],
      from: $from,
      to: $to
    }')

RAW_JSON=$(curl -sS \
    -H "Authorization: Bearer $GRAFANA_SERVICE_TOKEN" \
    -H "Content-Type: application/json" \
    -X POST \
    --data "$REQUEST_JSON" \
    "$GRAFANA_URL/api/ds/query")

STATUS=$(echo "$RAW_JSON" | jq -r '.results.A.status // empty' 2>/dev/null)
if [[ "$STATUS" != "200" ]]; then
    echo "Error: Grafana Loki datasource query failed." >&2
    echo "$RAW_JSON" | jq -r '.message // .error // .results.A.error // "No error detail returned."' >&2
    exit 1
fi

# Extract log lines and metadata
# Format: [JOB] LOG_MESSAGE
LOGS=$(echo "$RAW_JSON" | jq -r '
    .results.A.frames[]?.data.values as $values |
    range(0; ($values[2] | length)) |
    ($values[0][.] // {}) as $labels |
    "[\($labels.unit // $labels.syslog_identifier // $labels.job // "unknown")] \($values[2][.])"
')

if [ -z "$LOGS" ]; then
    echo "No errors or warnings found in the last $HOURS hours."
    exit 0
fi

# Group and count unique messages (roughly)
# We strip timestamps/IDs to group effectively and filter out internal query logs
echo "$LOGS" | \
    grep -v "executing query" | \
    grep -v "Response received from loki" | \
    grep -v "latency=" | \
    grep -viE "queryLog: query resolved|health_status=healthy|response_code=NOERROR|question_name=" | \
    sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.+-]+//g' | \
    sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?//g' | \
    sed -E 's/0x[0-9a-fA-F]+/<hex>/g' | \
    sed -E 's/[a-f0-9]{32,}/<hash>/g' | \
    sed -E 's/[0-9]{5,}/<id>/g' | \
    sed -E 's/[[:space:]]+/ /g' | \
    grep -vE '^[[:space:]]*$' | \
    sort | uniq -c | sort -rn | head -n 20 | \
    while read count msg; do
        printf "Frequency: %3d | %s\n" "$count" "$msg"
    done
