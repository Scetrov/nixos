# hermes-native-scheduling Specification

## Purpose
Define native Hermes scheduling on Habiki with refreshed gateway metadata, native job execution persisting across the deployment lifecycle, and declarative, security-preserving scheduling repair.
## Requirements
### Requirement: Native gateway supplies fresh scheduling metadata
The Habiki deployment SHALL run the supported long-lived Hermes gateway and native scheduler. The Scheduled Jobs WebUI SHALL consume regularly refreshed gateway metadata from that deployment without reporting stale metadata during healthy operation.

#### Scenario: Healthy gateway refreshes metadata
- **WHEN** the deployed gateway operates over multiple expected heartbeat intervals
- **THEN** its metadata advances and the Scheduled Jobs WebUI no longer reports `GATEWAY METADATA STALE`

#### Scenario: Healthy schedule is empty
- **WHEN** the native scheduler is healthy and no jobs are configured
- **THEN** the WebUI reports an empty schedule without falsely reporting stale gateway metadata

### Requirement: Native jobs remain visible and executable across deployment lifecycle
A job created through the supported native scheduling interface SHALL appear in the Scheduled Jobs WebUI and execute at its configured schedule. Job definitions and required execution state SHALL persist across gateway/WebUI restart and a targeted NixOS rebuild without destructive state reinitialization.

#### Scenario: Native job runs on schedule
- **WHEN** an automated acceptance check creates a harmless native job and its scheduled time arrives
- **THEN** the job is visible in the WebUI and produces an observable execution result

#### Scenario: Restart and rebuild preserve scheduling
- **WHEN** the gateway and WebUI are restarted and a targeted Habiki rebuild is subsequently deployed
- **THEN** the same test job remains visible and executes at a subsequent scheduled time after each operation without being recreated

### Requirement: Scheduling repair preserves security and exposes failures
The repair SHALL remain declarative through existing NixOS/Ansible automation, preserve persistent production state and existing Authentik ingress, and keep secrets outside the Nix store and diagnostic output. Gateway or scheduler failures SHALL be identifiable through existing native health/status information or logs available to the journal/Loki observability path. An external scheduler SHALL NOT substitute for the native Hermes scheduler.

#### Scenario: Gateway or scheduler becomes unhealthy
- **WHEN** the gateway or scheduler stops making progress in a controlled verification
- **THEN** health/status information or logs make the failure identifiable rather than implying that container liveness proves scheduling health

#### Scenario: Targeted deployment retains access and state boundaries
- **WHEN** the correction is deployed to Habiki using the existing targeted automation
- **THEN** existing job data is preserved, unauthenticated browser access remains gated by Authentik, and no secret or new public scheduling endpoint is introduced
