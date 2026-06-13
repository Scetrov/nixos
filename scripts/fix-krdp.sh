#!/usr/bin/env bash
set -euo pipefail

stamp="$(date +%Y%m%dT%H%M%S)"
backup="$HOME/.config/kde-rdp-geometry-backup-$stamp"

mkdir -p "$backup"

cp -a "$HOME/.config/kdeglobals" "$backup/" 2>/dev/null || true
cp -a "$HOME/.config/plasmashellrc" "$backup/" 2>/dev/null || true
cp -a "$HOME/.config/kwinrc" "$backup/" 2>/dev/null || true
cp -a "$HOME/.local/share/kscreen" "$backup/kscreen" 2>/dev/null || true

echo "Backup written to: $backup"

# Remove stale global/per-screen scaling.
kwriteconfig6 --file kdeglobals --group KScreen --key ScaleFactor --delete || true
kwriteconfig6 --file kdeglobals --group KScreen --key ScreenScaleFactors --delete || true

# Disable floating panel as a test.
kwriteconfig6 --file plasmashellrc \
  --group "PlasmaViews" \
  --group "Panel 2" \
  --key floating 0 || true

# Remove stale panel length saved for the old 3413x1440 logical screen.
kwriteconfig6 --file plasmashellrc \
  --group "PlasmaViews" \
  --group "Panel 2" \
  --group "Defaults" \
  --key minLength \
  --delete || true

kwriteconfig6 --file plasmashellrc \
  --group "PlasmaViews" \
  --group "Panel 2" \
  --group "Defaults" \
  --key maxLength \
  --delete || true

kwriteconfig6 --file plasmashellrc \
  --group "PlasmaViews" \
  --group "Panel 2" \
  --group "Horizontal3413" \
  --key alignment \
  --delete || true

# Force KScreen to rebuild remote monitor state next login.
if [[ -d "$HOME/.local/share/kscreen" ]]; then
  mv "$HOME/.local/share/kscreen" "$HOME/.local/share/kscreen.disabled-$stamp"
fi

mkdir -p "$HOME/.local/share/kscreen"

systemctl --user restart plasma-kscreen.service || true
systemctl --user restart plasma-plasmashell.service || true

echo
echo "Now fully log out of the XRDP session and reconnect."
echo "A plasmashell restart is not enough to clear QT_SCREEN_SCALE_FACTORS for the whole session."
