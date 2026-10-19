# Dependency-Track 4.14.5 authenticated read-back investigation

## Decision summary

Authenticated read-back is useful for inventory verification, but the reviewed REST APIs do **not** expose an exact upload-token/digest-to-success receipt. Do not use `processing=false`, a matching inventory, or a newer project import timestamp alone as proof that the particular submitted artifact succeeded.

A constrained single-writer design could use a persisted import-timestamp baseline plus post-idle inventory read-back, but only after explicitly establishing exclusive writes and ruling out earlier outstanding/ambiguous submissions. That is a proposed design constraint, not a verified production property. Otherwise, prefer investigating token-correlated success/failure logs through the existing observability path. No new notification receiver or ingress is required by that investigation.

## Scope and evidence strength

Primary sources are the upstream 4.14.5 release, resolved through GitHub to immutable commit `6d0406a27531bc6db24cb84e7fdf3e54ee83b281`. This matches the API version reported during initial discovery; source inspection is not a live authenticated test of the deployed system.

Inspected the relevant resources, exporter, project model, persistence manager, processing task and upstream processing tests. Additionally fetched and statically searched all 53 REST resource Java classes at that commit, excluding value-object/problem classes; all 53 requests succeeded. No import-history/`Bom` record access was found in that resource search. This is evidence about those upstream resources, not an assertion that no extension or future version could provide another endpoint.

No vault credentials were read, dedicated API identity provisioned, authenticated live project request sent, or BOM submitted. Upstream tests were inspected, not executed. A bounded upstream source archive request was abandoned when it exceeded 30 MiB compressed; targeted file inspection replaced it. No fetched source was extracted or executed.

## Supported read-back surfaces

| Surface | Required permission / access | What it proves | Limitation |
| --- | --- | --- | --- |
| `GET /api/v1/project/{uuid}` | `VIEW_PORTFOLIO` and project access check | Current project identity and `lastBomImport` / format | No submitted token, artifact digest or original serial/version receipt |
| `GET /api/v1/bom/cyclonedx/project/{uuid}?format=json&variant=inventory&version=1.6` | `VIEW_PORTFOLIO` and project access check | Reconstructed current inventory | Not the uploaded bytes; exporter generates a random serial and version 1 |
| `GET /api/v1/event/token/{uuid}` | Authenticated event-token surface; exact live identity permissions still require testing | Whether tasks for the token remain active | Idle is not success and does not establish token validity |

Sources:

- [ProjectResource: project read and access check, lines 144–177](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/resources/v1/ProjectResource.java#L144-L177).
- [BomResource: project inventory export, lines 124–209](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/resources/v1/BomResource.java#L124-L209).
- [CycloneDXExporter: new serial and version, lines 93–105](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/parser/cyclonedx/CycloneDXExporter.java#L93-L105).
- [Project: import timestamp and format fields, lines 284–299](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/model/Project.java#L284-L299).
- [EventResource: token-idle semantics](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/resources/v1/EventResource.java).

The collector would need an explicit additional `VIEW_PORTFOLIO` grant for these read-back APIs; do not silently expand a BOM-upload-only identity. Verify server-side project ACL enforcement for the dedicated team, including an unrelated-project denial. Do not grant project creation or portfolio management to the runtime collector.

## Transactional import evidence

In `BomUploadProcessingTask`, project, component, service and dependency-graph processing, plus `recordBomImport`, execute within `qm.runInTransaction`. `recordBomImport` persists the original serial and BOM version internally and updates the project import timestamp. The success message and `BOM_PROCESSED` dispatch occur after that transaction returns.

Thus an advanced import timestamp is a meaningful signal of an import transaction, not merely HTTP acceptance. It does not identify which artifact caused it, and downstream analysis is separate from that transaction.

Sources:

- [Import transaction and subsequent success event, lines 279–304](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/tasks/BomUploadProcessingTask.java#L279-L304).
- [Import record and timestamp update, lines 571–588](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/tasks/BomUploadProcessingTask.java#L571-L588).
- [Internal BOM query manager, lines 66–75](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/persistence/BomQueryManager.java#L66-L75): persistence API, not an exposed REST endpoint.
- [Upstream processing tests, lines 372–405](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/test/java/org/dependencytrack/tasks/BomUploadProcessingTaskTest.java#L372-L405): the tested processing-failure case emits `BOM_PROCESSING_FAILED` and leaves `lastBomImport` null. This is one inspected upstream test case, not exhaustive failure validation.

## Why read-back alone can falsely attribute success

1. Inventory already equals the new BOM's inventory; the new upload fails. Inventory equality and an idle token do not distinguish this from success.
2. Another writer imports successfully after the collector snapshots the timestamp; the collector's own upload fails. The advanced timestamp proves an import, but not the collector's import.
3. An earlier submission remains ambiguous across restart, then finishes while a newer submission fails. A timestamp advance can be attributed to the wrong run even if only this collector normally writes.
4. Exported serial numbers cannot resolve these ambiguities because each export creates a new random serial number; a whole-document hash comparison is also invalid.
5. A timed-out or absent timestamp advance is not a server-provided failure diagnosis. Preserve an unconfirmed/ambiguous state rather than claiming success or blindly permitting a newer overwrite.

## If choosing constrained single-writer read-back

This would require an explicit design update and disposable verification, not just an extra API call:

- Dedicated target with exclusive automated BOM writes; local locking alone cannot constrain other API identities or administrators.
- One outstanding submission per target, including across retries, collector restarts and server restarts. Unresolved earlier acceptance windows must block advancement.
- Persist target UUID/version, pre-submission server import baseline, validated artifact identity, ordering key and pending intent **before** submission; persist the returned token immediately after acceptance.
- After token-idle, require an import timestamp strictly newer than the persisted baseline and bounded canonical inventory verification. Do not compare client wall-clock time or raw exported JSON hashes. Equal/older timestamps fail closed.
- Define normalization against the actual Dependency-Track transformations, including de-duplication and rewritten references. This has not been specified or tested yet.
- Treat read-back unavailable, ambiguous attribution or no import advancement as unconfirmed failure requiring bounded recovery. Never advance the successful run checkpoint on those states.
- Validate success, asynchronous failure, identical consecutive inventories, interrupted acceptance, server restart, unauthorized extra writer and unrelated-target denial in a disposable instance.

These constraints are substantial and still do not supply a native token-specific failure receipt. They should not be assumed from the current deployment.

## Recommended next step

Investigate existing-path logs as the exact-upload success/failure signal, with read-back retained as an optional inventory check. The version-matched task already places the BOM upload token and project UUID in logging MDC and emits `BOM processed successfully` or a parse/processing failure. Verify that the deployed logging format and Alloy/Loki pipeline actually retain these fields, that events are durable across restarts and collection outages, and that the collector can query them with appropriately constrained credentials. A success message confirms the import transaction, not necessarily success of every later vulnerability-analysis task.

Source: [processing context, errors and success, lines 148–189 and 279–304](https://github.com/DependencyTrack/dependency-track/blob/6d0406a27531bc6db24cb84e7fdf3e54ee83b281/src/main/java/org/dependencytrack/tasks/BomUploadProcessingTask.java#L148-L189).

**Status:** Read-back investigation complete; task 1.2 and the asynchronous-completion implementation blocker remain unresolved. No production change or activation is justified by this research alone.
