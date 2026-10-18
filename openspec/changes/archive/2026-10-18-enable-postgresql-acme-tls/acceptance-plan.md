# Approved acceptance plan — executed 2026-10-18

The operator approved this plan, then separately confirmed a recovery route and
the reboot. Real replacement acceptance and reboot verification passed; see
`live-verification.md` for evidence and the tested NixOS shutdown-path correction.
The procedure below is retained as the reviewed plan, not blanket authorization
to repeat issuance or reboot. Both actions remain opt-in and approval-bound.

## 1. One real renewal, without another NixOS switch

**Budget: allow 15–20 minutes**, including the existing Cloudflare DNS propagation
wait. Request one replacement for the existing `scetrov.live` / `*.net.scetrov.live`
certificate only. This rotates the shared certificate used by Caddy as well as
PostgreSQL; it does not create another hostname or change credentials.

Read-only inspection established:

- Unit: `acme-order-renew-scetrov.live.service`; timer:
  `acme-renew-scetrov.live.timer` (currently active).
- Existing executable:
  `/nix/store/7vn89wy0ljiv9w6xqmf1dbhf6whx3cxn-unit-script-acme-order-renew-scetrov.live-start/bin/acme-order-renew-scetrov.live-start`.
- Installed lego **4.35.2** supports `renew --days 90`; `--dynamic` supersedes
  `--days`, so merely appending a days option would NOT force this test.
- Exactly one command token sequence is
  `renew --no-random-sleep --dynamic`.
- Unit runs as `acme:caddy`, with its existing credential loading, sandbox,
  account/domain configuration and state-directory bindings. Do not copy those
  credentials, account files or private keys into the repository or test script.
- Existing `ExecStartPost` consumes the real `renewed` marker and invokes
  `systemctl --no-block try-reload-or-restart caddy.service postgresql-tls-prepare.service`.

Implement a small, explicit Habiki-only Ansible acceptance playbook (not a general
certificate framework), with execution opt-in and a `block`/`always` cleanup:

1. Verify current health, TLS-only HBA, original unit/script identity, exactly one
   expected token sequence, and no renewal job already running. Capture public
   served certificate fingerprint/serial, PostgreSQL start time and container ID.
   Keep one authenticated, autocommit client session open to check it survives.
2. Record whether the existing renewal timer is active, then pause **only that
   timer**. Refuse to touch an existing acceptance drop-in/runtime directory.
3. Under a root-controlled directory `/run/postgresql-tls-renewal-check`, make a
   temporary copy of the public generated renewal script. Change **only** that
   exact command token sequence to `renew --no-random-sleep --days 90`; assert a
   one-replacement diff. Directory/script root:caddy 0750, no credential values.
4. Install one runtime-only drop-in at
   `/run/systemd/system/acme-order-renew-scetrov.live.service.d/90-postgresql-tls-acceptance.conf`.
   Reset/replace `ExecStart` with the temporary script; set `Restart=no` to prevent
   automatic repeated forced attempts and bound `TimeoutStartSec` to 20 minutes.
   Preserve all other unit settings, especially `ExecStartPost`, credentials,
   sandbox and state-directory bindings. Reload unit definitions, **not** the
   parent `acme-scetrov.live.service` or the database.
5. Invoke the existing order/renew service **once** via Ansible. No retry loop and
   no independent lego command that bypasses its original unit environment.
6. Wait for the actual ACME-triggered preparation reload and Caddy reload. Assert
   the fresh served fingerprint/serial changed; chain, validity and both endpoint
   names verify; PostgreSQL start time/container ID did not change; the held
   session still works. Check real clients, TLS-only rejection, socket access and
   Caddy HTTPS. An unchanged certificate is a failed acceptance test, not success.
7. In `always`, remove the acceptance drop-in, reload unit definitions and remove
   the runtime script/directory. Restore the timer to its recorded prior state.
   Verify the original `ExecStart` is restored and no temporary files/drop-ins or
   forced-renewal jobs remain. Preserve error evidence, do not clear failures to
   manufacture success. Cleanup failure is a blocker needing operator attention.

This avoids changing declarative renewal policy and restarting the parent ACME
service (a required dependency of PostgreSQL preparation). It tests the **real
renewal publication/hook path** without restarting PostgreSQL.

On any failure: stop, preserve the currently valid published pair and TLS-only
policy, complete runtime cleanup, and investigate. No automatic plaintext
rollback, database restart, second forced issuance or disabling verification.
Do not publish raw renewal logs, credential bindings or backend caches.

## 2. Separately approved Habiki reboot

**Additional interruption: all Habiki services**, not just PostgreSQL. Allow
5–10 minutes for boot and readiness; obtain explicit approval immediately before
this phase. Do not combine it silently with renewal.

1. Ensure renewal acceptance and runtime cleanup have passed; capture boot ID and
   the new served fingerprint. Confirm a suitable recovery/console route with the
   operator before rebooting.
2. Reboot only inventory host `habiki` via `ansible.builtin.reboot`, with bounded
   reconnect/readiness checks and no host-key-verification bypass. No channel
   update, NixOS rebuild, new package/image, or deployment is needed.
3. Confirm boot ID changed and preparation completed before PostgreSQL started
   using this boot's systemd monotonic timestamps and dependency ordering.
4. Verify the same replacement certificate is served with valid trust/hostname,
   protected key permissions, all real clients using TLS, plaintext/invalid
   verification rejection, socket administration, Caddy HTTPS and app health.
   Run wrapper-only `./scripts/tofu.sh -- plan -refresh=false` again (no apply).
5. Record non-secret evidence. A boot/readiness failure pauses the change;
   recovery preserves data and TLS rather than disabling security controls.

## 3. Finish only after acceptance

Mark task 3.4 complete only after genuine replacement acceptance and coordinated
reboot verification. Rerun focused tests, full pre-commit and strict OpenSpec
validation; inspect/stage only intended non-secret files. Archive the completed
OpenSpec change before any requested final signed commit/PR. No commit or PR has
been requested. Preserve the separately staged Garage proposal; its transport
prerequisite can then be updated with the recorded evidence.
