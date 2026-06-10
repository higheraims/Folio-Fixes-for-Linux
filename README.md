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

## Fix 2 — WINE upstream status (not yet properly fixed)

The WINE clipboard export code has been significantly refactored, but **the Folio case remains broken as of Wine 11 Staging (empirically confirmed).**

### What WINE did change

Commit `55bbe99c` ("winex11: Use data-only NtUserGetClipboardData to export clipboard data", April 2022, first stable release wine-8.0) removed direct `GlobalSize()` calls from `dlls/winex11.drv/clipboard.c`. The export functions no longer call `GlobalLock`/`GlobalSize`/`GlobalUnlock` themselves — they receive a pre-marshalled flat buffer from `NtUserGetClipboardData`.

`GlobalSize()` is genuinely gone from that file in all releases from wine-7.8 onwards.

### Why the bug persists anyway

The buffer passed into the export path still originates from the full `HGLOBAL` allocation. More critically, the only null-stripping that occurs is in `string_from_unicode_text()`:

```c
while (j && !str[j - 1]) j--;   // strips trailing null bytes only
```

This walks backwards from the **end** of the buffer and stops at the first non-null byte. Folio's binary metadata is not null padding — it is real binary data (Windows memory handles and heap addresses). The last bytes of the garbage are non-null values like `0xFF`, `0x54`, `0xB8`. The loop stops immediately and the entire garbage block is still exported to X11.

In short: the fix addresses applications that pad their clipboard data with extra trailing `\x00` bytes. It does not address applications like Folio Views that store structured binary data after the null terminator.

### What a proper fix would look like

The export path needs to treat CF_TEXT as a C string and truncate at the first null byte, not strip nulls from the tail:

```c
/* current behaviour — strips trailing nulls only, misses mid-buffer garbage */
while (j && !str[j - 1]) j--;

/* correct behaviour for CF_TEXT — truncate at the null terminator */
size_t text_len = strnlen(str, len);
j = (DWORD)text_len;
```

This would be the appropriate patch to submit to the [WINE bug tracker](https://bugs.winehq.org/). It is a small, safe change that only affects the text export path and matches the documented Windows convention for CF_TEXT.

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
