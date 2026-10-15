"""Envio de teclas pelo ``SendInput`` do Windows, com códigos de varredura (scan codes).

Jogos com DirectInput, como o Elden Ring, leem o código físico da tecla (scan code) e
ignoram teclas virtuais. Esta implementação confere o retorno do ``SendInput``, mas atenção:
quando o Windows bloqueia a tecla porque o jogo roda com mais privilégio que o script
(UIPI), o ``SendInput`` NÃO avisa. Para esse caso existe ``process_elevated``.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

# Botões do mouse aceitos como "tecla" em keys.json (ex.: "lock_on": "mouse_middle").
# Valor: (flag de apertar, flag de soltar).
MOUSE_BUTTONS = {
    "mouse_left": (0x0002, 0x0004),
    "mouse_right": (0x0008, 0x0010),
    "mouse_middle": (0x0020, 0x0040),  # clique da rodinha
}

# Scan codes do teclado padrão (conjunto 1). Setas usam o prefixo "estendido".
SCAN_CODES = {
    "esc": 0x01, "1": 0x02, "2": 0x03, "3": 0x04, "4": 0x05, "5": 0x06,
    "q": 0x10, "w": 0x11, "e": 0x12, "r": 0x13, "t": 0x14, "y": 0x15, "u": 0x16,
    "i": 0x17, "o": 0x18, "p": 0x19, "enter": 0x1C, "ctrl": 0x1D,
    "a": 0x1E, "s": 0x1F, "d": 0x20, "f": 0x21, "g": 0x22, "h": 0x23, "j": 0x24,
    "k": 0x25, "l": 0x26, "shift": 0x2A, "z": 0x2C, "x": 0x2D, "c": 0x2E, "v": 0x2F,
    "b": 0x30, "n": 0x31, "m": 0x32, "alt": 0x38, "space": 0x39, "tab": 0x0F,
    "up": 0x48, "left": 0x4B, "right": 0x4D, "down": 0x50,
}
EXTENDED = {"up", "down", "left", "right"}

ULONG_PTR = ctypes.c_size_t  # 64 bits no Python 64 bits


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class SendInputError(RuntimeError):
    pass


_user32 = None


def _u32():
    global _user32
    if _user32 is None:
        _user32 = ctypes.WinDLL("user32", use_last_error=True)
        _user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
        _user32.SendInput.restype = wintypes.UINT
    return _user32


def _send(scan: int, flags: int) -> None:
    user32 = _u32()
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.u.ki = KEYBDINPUT(0, scan, flags | KEYEVENTF_SCANCODE, 0, 0)
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        raise SendInputError(f"SendInput falhou, erro do Windows {ctypes.get_last_error()}")


def _send_mouse(flags: int) -> None:
    user32 = _u32()
    inp = INPUT(type=INPUT_MOUSE)
    inp.u.mi = MOUSEINPUT(0, 0, 0, flags, 0, 0)
    sent = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
    if sent != 1:
        raise SendInputError(f"SendInput (mouse) falhou, erro do Windows {ctypes.get_last_error()}")


def _scan(key: str) -> tuple[int, int]:
    k = key.lower()
    if k not in SCAN_CODES:
        raise KeyError(f"Tecla {key!r} sem scan code em winput.SCAN_CODES")
    return SCAN_CODES[k], (KEYEVENTF_EXTENDEDKEY if k in EXTENDED else 0)


def keyDown(key: str) -> None:  # noqa: N802 - mesma interface do pydirectinput
    if key.lower() in MOUSE_BUTTONS:
        _send_mouse(MOUSE_BUTTONS[key.lower()][0])
        return
    scan, flags = _scan(key)
    _send(scan, flags)


def keyUp(key: str) -> None:  # noqa: N802
    if key.lower() in MOUSE_BUTTONS:
        _send_mouse(MOUSE_BUTTONS[key.lower()][1])
        return
    scan, flags = _scan(key)
    _send(scan, flags | KEYEVENTF_KEYUP)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def process_elevated(hwnd: int) -> bool | None:
    """O processo dono da janela roda como administrador? ``None`` = não deu para saber
    (acontece com processos protegidos, como jogos com anti-cheat)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    advapi32.OpenProcessToken.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE))
    advapi32.GetTokenInformation.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                             wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    proc = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not proc:
        return None
    token = wintypes.HANDLE()
    try:
        if not advapi32.OpenProcessToken(proc, 0x0008, ctypes.byref(token)):  # TOKEN_QUERY
            return None
        elevation = wintypes.DWORD()
        size = wintypes.DWORD()
        ok = advapi32.GetTokenInformation(token, 20, ctypes.byref(elevation),  # TokenElevation
                                          ctypes.sizeof(elevation), ctypes.byref(size))
        return bool(elevation.value) if ok else None
    finally:
        if token:
            kernel32.CloseHandle(token)
        kernel32.CloseHandle(proc)
