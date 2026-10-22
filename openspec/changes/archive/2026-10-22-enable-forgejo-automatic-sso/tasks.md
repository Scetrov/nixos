## 1. Establish supported behavior

- [x] 1.1 Verify the installed Forgejo release, current login routes/source configuration, and supported auto-entry/logout mechanisms against matching upstream documentation/source; record the secure host-side recovery procedure and stop for a feasibility blocker if no bounded supported solution meets direct and launch entry. See `investigation.md`: native-only entry is insufficient; the operator subsequently approved narrow Caddy routing.
- [x] 1.2 Reproduce current and candidate behavior using a disposable local Forgejo/test identity-provider setup where feasible; establish browser versus Git/API/callback/logout route boundaries and supported deep-link forms without touching production state.

## 2. Configure and regression-test

- [x] 2.1 Implement the smallest supported declarative auto-entry change using the existing Authentik source; preserve access groups, validated same-origin destinations, private ingress, runtime secrets, and disabled local-password login.
- [x] 2.2 Add focused configuration/protocol regressions and browser acceptance coverage for existing/absent Forgejo and Authentik sessions, direct and dashboard entry, supported deep links, unsafe return URLs, logout, denied users, invalid callbacks, expired sessions, and provider outage. Verify recovery and no unbounded redirect loops.
- [x] 2.3 Verify Git SSH/HTTPS, API tokens, webhook and health behavior remains native with no blanket forward-auth; run relevant existing Forgejo tests and repeat the disposable reproduction with the candidate.

## 2a. Browser-state regression

- [x] 2.4 Fix the persistent logout pause reported in Firefox: consume it on the first native login landing, retain a usable logout page, and verify that a subsequent visit automatically starts SSO. Add a failing native-browser regression before the fix, redeploy through the targeted path, and repeat the cookie-jar reproduction against production.

## 3. Deploy and finalize

- [x] 3.1 Document entry/logout/failure/recovery and rollback behavior, review host drift, and deploy through the targeted Habiki Forgejo path; use scripts/tofu.sh for any necessary identity changes and avoid unrelated hosts/services.
- [x] 3.2 Verify live browser/protocol acceptance and configuration persistence after service restart/targeted rebuild; record operator-only checks honestly and leave acceptance tasks pending if access is unavailable. Operator confirmed live Firefox browser acceptance after the logout-pause fix.
- [x] 3.3 Run strict OpenSpec validation and configured pre-commit gates, archive this change, and stage only intended files. Strict validation and all pre-commit gates pass; the active change is archived below. No commit or PR requested or created.
- [x] 3.4 Map every acceptance criterion in issue #23 to recorded evidence and post a redacted closure summary with durable evidence links using gh. Close #23 as completed only when all criteria are supported, then verify the issue state; otherwise leave it open and record unmet criteria or verification blockers.
