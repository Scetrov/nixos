## Context

The repository already runs a central observability stack on `habiki` with Grafana, Mimir, Loki, Tempo, Pyroscope, Prometheus, Alloy, and OnCall exposed behind `metrics.net.scetrov.live`. Grafana already has the core datasources and correlations configured, but the current catalog is limited to a small number of dashboards and service coverage is inconsistent: some services expose metrics cleanly, some only partially, and some have no explicit Grafana-facing observability contract. The desired end state is not just more charts; it is a coherent operator workflow where Grafana is the first place to assess platform health and drill into individual services.

## Goals / Non-Goals

**Goals:**
- Make Grafana the primary operator entrypoint for the environment.
- Add a dashboard structure that separates platform-wide views from service-specific views.
- Define a minimum observability contract so service metrics, logs, and traces share stable identity.
- Prioritize declarative, source-controlled dashboard and telemetry configuration.
- Allow incremental service onboarding without blocking the entire change on universal tracing or profiling support.

**Non-Goals:**
- Rebuild or replace the existing Grafana, Mimir, Loki, Tempo, or Pyroscope stack.
- Require every service to implement full tracing and profiling before the portal is useful.
- Replace service-native UIs for domain-specific workflows that do not belong in Grafana.
- Move away from the repository's existing NixOS, Ansible, and OpenTofu deployment model.

## Decisions

### 1. Grafana becomes the operations portal, not just a dashboard host

- **Decision:** Introduce a layered dashboard experience consisting of a platform overview, a service catalog, and per-service dashboards.
- **Rationale:** Operators need a predictable path from fleet health to service diagnosis. A landing experience prevents Grafana from devolving into a flat list of unrelated dashboards.
- **Alternative considered:** Add more standalone dashboards without a catalog. This is faster initially but does not create a true single-pane workflow.

### 2. Use a minimum observability contract for service onboarding

- **Decision:** Define a shared service identity across signals, with at least `service` and `host` available wherever the underlying exporter or instrumentation supports them.
- **Rationale:** Grafana correlations only become useful when metrics, logs, and traces describe the same service with consistent labels or resource attributes.
- **Alternative considered:** Let each service keep ad hoc labels and dashboard conventions. That keeps local changes small but breaks cross-signal navigation.

### 3. Keep dashboards declarative and source-controlled

- **Decision:** Manage the overview, catalog, and service dashboards through the repository's declarative Grafana workflow and avoid manual UI-only ownership.
- **Rationale:** The stack is infrastructure-as-code driven, and dashboard drift would undermine reproducibility.
- **Alternative considered:** Use Grafana UI editing as the primary source of truth and export JSON later. That is convenient during experimentation but difficult to review, test, and keep consistent.

### 4. Stage telemetry onboarding by maturity, not by perfection

- **Decision:** Bring services into the portal with the strongest supported baseline first, typically metrics plus logs, and then add traces or profiles where the service stack supports them.
- **Rationale:** This allows early operational value while making gaps explicit instead of silently blocking the single-pane effort on the hardest integrations.
- **Alternative considered:** Require complete signal parity across every managed service before publishing the portal. That would delay the operator experience and likely stall the change.

### 5. Organize dashboards around platform and service concerns

- **Decision:** Separate platform-wide dashboards from service dashboards using stable folder or equivalent organizational conventions.
- **Rationale:** Operators should be able to distinguish between shared infrastructure health and a specific application's health without learning a bespoke naming system.
- **Alternative considered:** Keep all dashboards in one flat namespace. That works at the current size but will not scale cleanly as services are onboarded.

## Risks / Trade-offs

- **[Risk] Dashboard sprawl without a clear convention** -> Mitigate by defining folder, naming, UID, and drilldown conventions before adding many new dashboards.
- **[Risk] Inconsistent labels prevent useful correlations** -> Mitigate by enforcing a minimum observability contract for service identity during onboarding.
- **[Risk] Some services cannot expose traces or profiles quickly** -> Mitigate by allowing phased onboarding with explicit signal gaps on service dashboards.
- **[Risk] Declarative ownership split across multiple layers becomes confusing** -> Mitigate by documenting where Grafana datasources, folders, dashboards, and service telemetry are managed before implementation begins.
- **[Risk] Single-pane expectations expand into replacing every service-native workflow** -> Mitigate by keeping Grafana focused on operational awareness and drilldown, not every domain-specific action.

## Migration Plan

1. Define the target dashboard structure, naming conventions, and service identity contract.
2. Add the platform overview and service catalog dashboards.
3. Onboard services in priority order, starting with those that already expose useful metrics or logs.
4. Add cross-signal drilldowns and explicit signal-gap handling for partially instrumented services.
5. Deploy narrowly to `habiki` using the existing targeted NixOS and OpenTofu workflows, then validate the operator journey end to end.

Rollback is to remove the new dashboard and telemetry onboarding changes from source control and redeploy the same targeted workflows, returning Grafana to the current smaller dashboard set.

## Open Questions

- Which layer should own long-term dashboard source-of-truth details when Grafana datasources live in NixOS configuration but dashboard resources may also be managed through OpenTofu?
- Which services should be considered phase-one onboarding targets after the existing system resources and frontier indexer views?
- Should Grafana OnCall exporter support be enabled as part of this change, or treated as a follow-on integration if the current container deployment makes it awkward?
