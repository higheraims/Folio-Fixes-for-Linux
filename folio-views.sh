#!/usr/bin/env bash
# folio-views.sh — Launch Folio Views under WINE with automatic clipboard fix.
#
# This wrapper starts the clipboard-cleaning daemon in the background, runs
# Folio Views, then terminates the daemon when Folio exits.
#
# Configuration:
#   Set FOLIO_EXE to the path of your Folio Views executable, or pass it as
#   the first argument.  Examples:
#
#     FOLIO_EXE="$HOME/.wine/drive_c/Folio/Views.exe" ./folio-views.sh
#     ./folio-views.sh "$HOME/.wine/drive_c/Folio/Views.exe"

set -euo pipefail

SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
CLEANER="$SCRIPT_DIR/folio-clipboard-fix.py"

# --- Resolve the Folio executable -------------------------------------------
if [[ $# -ge 1 ]]; then
    FOLIO_EXE="$1"
    shift
elif [[ -z "${FOLIO_EXE:-}" ]]; then
    echo "Usage: $0 /path/to/FolioViews.exe [wine-args...]" >&2
    echo "  or:  FOLIO_EXE=/path/to/FolioViews.exe $0" >&2
    exit 1
fi

if [[ ! -f "$FOLIO_EXE" ]]; then
    echo "Error: Folio executable not found: $FOLIO_EXE" >&2
    exit 1
fi

# --- Check dependencies ------------------------------------------------------
if ! command -v wine &>/dev/null; then
    echo "Error: 'wine' not found in PATH." >&2
    exit 1
fi

if ! python3 -c "from PyQt6.QtWidgets import QApplication" &>/dev/null 2>&1; then
    echo "Warning: PyQt6 not available — clipboard fix will not run." >&2
    echo "  Install with: pip install PyQt6" >&2
    exec wine "$FOLIO_EXE" "$@"
fi

# --- Start clipboard cleaner -------------------------------------------------
# Force the X11/XCB clipboard bus so the daemon sees the same clipboard that
# WINE (running under XWayland) uses.  On a Wayland session Qt would otherwise
# use the Wayland clipboard protocol — a separate bus — and miss all changes
# made by WINE, while also crashing KDE's Klipper bridge on write-back.
QT_QPA_PLATFORM=xcb python3 "$CLEANER" &
CLEANER_PID=$!

cleanup() {
    kill "$CLEANER_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Clipboard fix daemon started (PID $CLEANER_PID)."

# --- Launch Folio Views ------------------------------------------------------
wine "$FOLIO_EXE" "$@"
