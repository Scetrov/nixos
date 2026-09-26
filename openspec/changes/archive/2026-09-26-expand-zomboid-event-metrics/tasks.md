## 1. Update dashboard event coverage

- [x] 1.1 Add reset-aware `$__interval` queries for `zombies-killed-by-fire-today`, `players-killed-by-fire-today`, `players-killed-by-player-today`, and `zombified-players-today` to the Project Zomboid Events per interval panel.
- [x] 1.2 Configure concise legends, approved distinct colours, and panel text that identifies fire-killed zombies as included in total zombie kills; keep the bars non-stacked and absent series unavailable.
- [x] 1.3 Update `docs/project-zomboid-observability.md` with the complete verified daily-event metric inventory, gauge/reset semantics, and the fire-kill subset interpretation.

## 2. Validate and deploy declaratively

- [x] 2.1 Validate the edited dashboard JSON and run the repository's applicable dashboard/OpenTofu validation through `scripts/tofu.sh` without exposing the metrics endpoint or adding RCON.
- [x] 2.2 Apply the dashboard through the established targeted declarative automation path and inspect or render the Events per interval panel at short and long time ranges.
- [x] 2.3 Verify that all seven supported series use discrete non-negative interval values, the fire-kill subset is not visually additive, and missing telemetry is shown as unavailable rather than synthesized zero.

## 3. Refine player roster coverage

- [x] 3.1 Replace unavailable health, days-alive, and individual zombie-kill placeholders with verified World X and World Y coordinate queries while retaining Player ID and last-seen fields.
- [x] 3.2 Validate and deploy the roster update through targeted OpenTofu automation, then render the live roster to confirm a single row displays Player ID, Player, Last seen, World X, and World Y.
