# Folio Fixes for Linux

Patches and workarounds for WINE interoperability under Linux, so Folio Views will work as intended.

As a user of the EGW Writings software, running under WINE in Linux, I found everything working great but some small problems have cropped up. The main one is that in a Wayland session the clipboard contents gets confused and copy and paste makes a mess. 

---

## Problem: Garbled clipboard paste

When text is copied from Folio Views (running under WINE) and pasted into a Linux application, binary garbage is appended to the text. Example:

> Jesus did not receive baptism as a confession of guilt… `{ DA 111.2}` **`Tÿ X"¸ … ¨Tÿ ¨"¸ …`** *(binary junk)*

### Root cause

Folio Views stores its clipboard text as a Windows `HGLOBAL` memory block where the human-readable text is followed by binary document metadata (internal record handles and heap addresses for Folio's proprietary citation format). The block layout is:

```
[  plain text  ][ NUL ][ binary Folio metadata … ]
```

The Windows convention for `CF_TEXT` is that readers call `strlen()` to find the end of the text — the binary data after the null terminator is ignored by Windows applications.

**WINE's X11 clipboard bridge breaks this convention.** In `dlls/winex11.drv/clipboard.c`, the function that exports `CF_TEXT` to X11 calls `GlobalSize()` to determine how many bytes to write to the X11 selection, instead of `strlen()`. The result is that the *entire allocation* — garbage and all — is written to the X11 clipboard, where every receiving application sees it.

---

## Fix 1 — Clipboard cleaner daemon (recommended for end users)

`folio-clipboard-fix.py` is a background daemon that monitors the X11 clipboard using PyQt6. When it detects garbled Folio content (identified by embedded null bytes), it strips everything from the first `\x00` onward and writes the clean text back to the clipboard. This happens within milliseconds and is invisible to the user.

**Requirements:** Python 3, PyQt6 (`pip install PyQt6`)

### Quickstart

The easiest way for end users is the included launcher wrapper:

```bash
# Make scripts executable (once)
chmod +x folio-views.sh folio-clipboard-fix.py

# Launch Folio Views — the clipboard fix runs automatically
./folio-views.sh /path/to/FolioViews.exe

# Or set the path once as an environment variable
export FOLIO_EXE="$HOME/.wine/drive_c/Folio/Views.exe"
./folio-views.sh
```
`folio-views.sh` starts the daemon, launches Folio via WINE, and kills the daemon when Folio exits. Nothing else needs to change.

On my system, it works out like this:

```bash
WINEPREFIX=$HOME/.wine $HOME/Folio-Fixes-for-Linux/folio-views.sh '/home/$USER/.wine/drive_c/Estate/Research Ed/Folio/Views.exe' 'C:\Estate\Research\Folio\Books\egw-comp.sdw'
```
(Adjust the path to the .sh file and replace $USER with the right user folder)

### Dependencies for above

Assuming you already have a working WINE installation with Folio Views installed, the only other dependency you're likely to need is Python-pyqt6. Install on Fedora (the distro I run) goes like this:

``` bash
sudo dnf install python3-pyqt6
```

### Running the daemon standalone

If you prefer to manage the daemon yourself (e.g. keep it running for the entire session):

```bash
python3 folio-clipboard-fix.py &          # silent background
python3 folio-clipboard-fix.py --verbose  # print a line on each clean
```

---

## Fix 2 — WINE upstream patch (proper long-term fix)

The correct fix is a one-line change in WINE's source code. The relevant file is:

```
dlls/winex11.drv/clipboard.c
```

The function that exports `CF_TEXT` / `CF_OEMTEXT` data to X11 uses `GlobalSize(handle)` to determine the byte count. It should use `strlen(ptr)` (or `strnlen` with the global size as the bound) instead:

```c
/* BEFORE (wrong) */
size_t len = GlobalSize(handle);

/* AFTER (correct) */
const char *ptr = GlobalLock(handle);
size_t len = strnlen(ptr, GlobalSize(handle));
GlobalUnlock(handle);
```

For `CF_UNICODETEXT` the analogous fix is to use `wcslen(ptr) * sizeof(WCHAR)` rather than `GlobalSize(handle)`.

This patch should be submitted upstream to the [WINE bug tracker](https://bugs.winehq.org/). Any distribution that ships a patched WINE would fix the problem for all affected Windows applications, not just Folio Views.

If someone has some clout with the folks over at WINE, please be my guest and try to get this done.

---

## Fix 3 — Manual clipboard cleaner (existing power-user workaround)

Tools such as `xclip`, `xdotool`, or clipboard manager applications (Clipman, GPaste, etc.) can be configured to strip non-printable characters from clipboard content. This approach works but requires manual configuration and is not suitable for novice users.

---

## Files

| File | Purpose |
|---|---|
| `folio-clipboard-fix.py` | PyQt6 daemon — monitors and cleans the clipboard |
| `folio-views.sh` | Launcher wrapper — starts the daemon alongside Folio Views |
| `Copy and Paste Samples.txt` | Raw clipboard output samples showing the garbage |
