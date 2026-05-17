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

LOKI_URL=${LOKI_URL:-"https://metrics.net.scetrov.live/loki"}
HOURS=${1:-6}
START=$(date -d "$HOURS hours ago" +%s%N)

# Query Loki for Errors and Warnings
QUERY='{job=~".+"} |~ "(?i)error|warning|fail|critical"'

# Fetch logs
RAW_JSON=$(curl -s -G -H "Authorization: Bearer $GRAFANA_SERVICE_TOKEN" \
    --data-urlencode "query=$QUERY" \
    --data-urlencode "start=$START" \
    "$LOKI_URL/api/v1/query_range")

if [[ $(echo "$RAW_JSON" | jq -r '.status') != "success" ]]; then
    echo "Error: Loki query failed." >&2
    echo "$RAW_JSON" | jq -r '.error' >&2
    exit 1
fi

# Extract log lines and metadata
# Format: [JOB] LOG_MESSAGE
LOGS=$(echo "$RAW_JSON" | jq -r '
    .data.result[] | 
    .stream.job as $job | 
    .values[] | 
    "[\($job)] \(.[1])"
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
    sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[^ ]* //g' | \
    sed -E 's/0x[0-9a-fA-F]+/<hex>/g' | \
    sed -E 's/[0-9]{5,}/<id>/g' | \
    sort | uniq -c | sort -rn | head -n 20 | \
    while read count msg; do
        printf "Frequency: %3d | %s\n" "$count" "$msg"
    done
