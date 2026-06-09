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

## Fix 2 — Upgrade WINE (fixes the root cause)

**This bug is already fixed in current WINE.** The `dlls/winex11.drv/clipboard.c` file in WINE master no longer uses `GlobalSize()` to size clipboard exports. It now uses a `string_from_unicode_text()` helper that explicitly strips trailing null bytes after the unicode conversion, so binary data after the CF_TEXT null terminator is never written to the X11 selection.

If you are seeing the problem, your installed WINE is an older version from your distribution's repositories. Upgrading to a current WINE build will fix it at the source and make the clipboard daemon unnecessary.

### Upgrading to current WINE on Fedora

Add the WineHQ repository and install the stable or development release:

```bash
sudo dnf config-manager --add-repo \
  https://dl.winehq.org/wine-builds/fedora/$(rpm -E %fedora)/winehq.repo
sudo dnf install winehq-stable
# or for the latest development build:
# sudo dnf install winehq-devel
```

### Why the daemon is still useful

- Users on distribution-provided WINE (which often lags years behind upstream) will still see the bug.
- The daemon is harmless on a fixed WINE — it polls every 150 ms, never finds a null byte, and does nothing.
- It also guards against any other application that puts null bytes in clipboard text.

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
