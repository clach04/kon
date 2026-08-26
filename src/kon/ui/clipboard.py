import base64
import os
import shutil
import subprocess
import sys


def copy_to_clipboard(text: str) -> None:
    encoded = base64.b64encode(text.encode()).decode()
    print(f"\033]52;c;{encoded}\a", end="", flush=True)

    if sys.platform == "win32":
        win32_copy_to_clipboard(text)
        return

    if sys.platform == "darwin":
        _try_run(["pbcopy"], text)
        return

    if os.environ.get("TERMUX_VERSION") and _try_run(["termux-clipboard-set"], text):
        return

    if _is_wayland_session():
        if _try_run(["wl-copy"], text):
            return
        if _try_run(["xclip", "-selection", "clipboard"], text):
            return
        _try_run(["xsel", "--clipboard", "--input"], text)
        return

    if _try_run(["xclip", "-selection", "clipboard"], text):
        return
    _try_run(["xsel", "--clipboard", "--input"], text)


# TODO: Linux/Wayland clipboard *reading* is not implemented (wl-paste / xclip -o /
# xsel --output). Paste on Linux falls back to Textual's internal buffer only.

_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002


def read_system_clipboard() -> str | None:
    """Read text from the OS clipboard, or None if unavailable."""
    if sys.platform == "win32":
        return win32_read_clipboard()
    # TODO: non-Windows reading (pbcopy has no reader; use pbpaste, wl-paste,
    # xclip/xsel) is not implemented yet.
    return None


def _win32_clipboard_functions():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    user32.IsClipboardFormatAvailable.restype = wintypes.BOOL
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

    return user32, kernel32


def win32_read_clipboard() -> str | None:
    import ctypes

    user32, kernel32 = _win32_clipboard_functions()
    if not user32.OpenClipboard(None):
        return None
    try:
        if not user32.IsClipboardFormatAvailable(_CF_UNICODETEXT):
            return None
        handle = user32.GetClipboardData(_CF_UNICODETEXT)
        if not handle:
            return None
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            return None
        try:
            return ctypes.wstring_at(ptr)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def win32_copy_to_clipboard(text: str) -> bool:
    """Copy text to the Windows clipboard via the Win32 API (unicode-safe)."""
    import ctypes

    user32, kernel32 = _win32_clipboard_functions()
    if not user32.OpenClipboard(None):
        return False
    try:
        user32.EmptyClipboard()
        buffer = ctypes.create_unicode_buffer(text)
        size = ctypes.sizeof(buffer)
        handle = kernel32.GlobalAlloc(_GMEM_MOVEABLE, size)
        if not handle:
            return False
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            kernel32.GlobalFree(handle)
            return False
        try:
            ctypes.memmove(ptr, buffer, size)
        finally:
            kernel32.GlobalUnlock(handle)
        # On success the system owns the memory; do not free it.
        if not user32.SetClipboardData(_CF_UNICODETEXT, handle):
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()


def _is_wayland_session() -> bool:
    return (
        bool(os.environ.get("WAYLAND_DISPLAY")) or os.environ.get("XDG_SESSION_TYPE") == "wayland"
    )


def _try_run(command: list[str], text: str) -> bool:
    if shutil.which(command[0]) is None:
        return False

    try:
        subprocess.run(
            command,
            input=text,
            text=True,
            check=True,
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return False

    return True
