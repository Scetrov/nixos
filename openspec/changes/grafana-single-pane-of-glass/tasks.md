# Grafana Single Pane Of Glass

## 1. Portal Structure

- [x] 1.1 Define the declarative source-of-truth, folder structure, naming rules, and UID conventions for the Grafana operations portal
- [x] 1.2 Add platform-wide Grafana dashboards for overall observability stack health and host or fleet health
- [x] 1.3 Add a service catalog dashboard or equivalent landing view that links operators to service-specific dashboards

## 2. Service Observability Contract

- [x] 2.1 Define the minimum service identity and telemetry contract for metrics, logs, and traces used by Grafana correlations
- [x] 2.2 Update service telemetry configuration where needed so supported signals expose stable service and host identity
- [x] 2.3 Document or surface explicit signal gaps for services that cannot yet provide traces or profiles

## 3. Service Onboarding

- [x] 3.1 Onboard phase-one services with per-service dashboards and drilldowns, starting from services that already expose useful metrics or logs
- [x] 3.2 Expand or complete telemetry onboarding for partially integrated services such as Dependency Track, OnCall, Hermes, and Home Assistant as supported by their runtime models
- [x] 3.3 Add cross-links from service dashboards into logs, traces, profiles, incidents, and relevant external service views

## 4. Validation And Rollout

- [x] 4.1 Deploy the Grafana, NixOS, and OpenTofu changes narrowly to `habiki` using the existing targeted workflows
- [x] 4.2 Verify authentication, routing, dashboard provisioning, and datasource correlations through the Grafana UI
- [x] 4.3 Validate at least one end-to-end operator workflow from overview to service drilldown for each phase-one service
