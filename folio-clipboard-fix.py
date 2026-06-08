#!/usr/bin/env python3
"""
Folio Views clipboard cleaner daemon.

Root cause: WINE's X11 clipboard bridge calls GlobalSize() on the CF_TEXT
HGLOBAL block rather than strlen(), so it exports the entire allocation to
X11 — including Folio's proprietary binary metadata that follows the null
terminator. This daemon monitors the clipboard and strips that garbage.

Usage:
    python3 folio-clipboard-fix.py [--verbose]
"""

import os
import sys
import re
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QClipboard
from PyQt6.QtCore import QTimer

# Force the X11/XCB backend so this daemon connects to the same clipboard bus
# that WINE (running under XWayland) uses.  Without this, on a Wayland session
# Qt uses the Wayland clipboard protocol, which is a different bus — the daemon
# would see nothing and cause KDE's clipboard bridge (Klipper) to crash.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
DEBUG   = "--debug"   in sys.argv or "-d" in sys.argv
POLL_INTERVAL_MS = 150   # fast enough to clean before a human pastes


def has_folio_garbage(text: str) -> bool:
    """Return True if the text contains Folio-style binary garbage."""
    if not text:
        return False
    # Primary indicator: embedded null byte (Windows CF_TEXT null terminator
    # followed by binary data — legitimate clipboard text never contains NUL).
    if '\x00' in text:
        return True
    # Secondary indicator: clusters of U+00FF (ÿ) — these are 0xFF Windows
    # address bytes that survive Latin-1 / UTF-8 round-tripping.
    ff_count = text.count('\xff') + text.count('ÿ')
    if ff_count >= 3:
        return True
    return False


def clean_folio_text(text: str) -> str:
    """Strip the binary garbage from Folio clipboard content."""
    # Truncate at the first null byte — the CF_TEXT null terminator.
    if '\x00' in text:
        text = text[:text.index('\x00')]
    # Remove any remaining stray C0 control characters (NUL already gone).
    text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Strip trailing whitespace left before the garbage block.
    text = text.rstrip()
    return text


class ClipboardCleaner:
    def __init__(self, clipboard: QClipboard):
        self.clipboard = clipboard
        self._cleaning = False     # re-entrancy guard
        self._last_seen = ""       # hash of last text we processed

        # Signal-based path: fires immediately if XFixes is wired up correctly.
        clipboard.dataChanged.connect(self._check)

        # Polling fallback: reliable even when dataChanged doesn't fire for
        # WINE clipboard changes (a known Qt/X11 limitation).
        self._timer = QTimer()
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._check)
        self._timer.start()

        if VERBOSE:
            print(
                f"[folio-fix] Watching clipboard "
                f"(signal + poll every {POLL_INTERVAL_MS} ms) …",
                flush=True,
            )

    def _check(self):
        if self._cleaning:
            return

        text = self.clipboard.text(QClipboard.Mode.Clipboard)

        if DEBUG:
            mime = self.clipboard.mimeData(QClipboard.Mode.Clipboard)
            formats = mime.formats() if mime else []
            has_null = '\x00' in text if text else False
            print(
                f"[debug] len={len(text):4d}  null={has_null}"
                f"  formats={formats}"
                f"  snippet={repr(text[:50])}",
                flush=True,
            )

        # Skip if content hasn't changed since we last looked.
        if text == self._last_seen:
            return
        self._last_seen = text

        if VERBOSE or DEBUG:
            snippet = repr(text[:60]) if text else "(empty)"
            print(f"[folio-fix] Clipboard changed → {snippet}", flush=True)

        if not has_folio_garbage(text):
            return

        cleaned = clean_folio_text(text)

        if VERBOSE:
            print(
                f"[folio-fix] Garbage detected — "
                f"cleaning {len(text)} → {len(cleaned)} chars",
                flush=True,
            )

        # Safety: don't wipe the clipboard if cleaning yields empty content.
        if not cleaned:
            if VERBOSE:
                print("[folio-fix] Skipped: cleaned result was empty.", flush=True)
            return

        self._cleaning = True
        self._last_seen = cleaned   # update so the next poll doesn't re-trigger
        try:
            self.clipboard.setText(cleaned, QClipboard.Mode.Clipboard)
        finally:
            self._cleaning = False


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    cleaner = ClipboardCleaner(app.clipboard())  # noqa: F841 (kept alive via app)

    print("folio-clipboard-fix: running. Kill this process to stop.", flush=True)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
