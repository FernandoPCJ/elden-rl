"""Backup e restauração do save do Elden Ring.

O save fica em %APPDATA%\\EldenRing\\<número da Steam>\\ER0000.sl2 (com uma cópia .bak).
Ele guarda TODOS os personagens da conta num arquivo só.

Regras de segurança:
- só mexe no save com o jogo FECHADO (o jogo reescreve o arquivo enquanto roda);
- antes de restaurar, sempre guarda uma cópia do save atual ("antes-de-restaurar-...").
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SAVES_DIR = PROJECT / "saves"
SAVE_NAMES = ("ER0000.sl2", "ER0000.sl2.bak")


def game_save_dir() -> Path:
    """Pasta do save do jogo. Se houver mais de uma conta Steam, usa a modificada mais recente."""
    base = Path(os.environ.get("APPDATA", "")) / "EldenRing"
    candidates = [d for d in base.glob("*") if d.is_dir() and (d / "ER0000.sl2").exists()]
    if not candidates:
        raise FileNotFoundError(f"Nenhum ER0000.sl2 encontrado em {base}")
    return max(candidates, key=lambda d: (d / "ER0000.sl2").stat().st_mtime)


def game_running() -> bool:
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq eldenring.exe"],
                             capture_output=True, text=True, timeout=10).stdout
    except (FileNotFoundError, subprocess.SubprocessError):
        return False  # fora do Windows (testes)
    return "eldenring.exe" in out.lower()


def _copy_save(src: Path, dst: Path) -> list[Path]:
    dst.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in SAVE_NAMES:
        if (src / name).exists():
            shutil.copy2(src / name, dst / name)
            copied.append(dst / name)
    if not copied:
        raise FileNotFoundError(f"Nenhum arquivo de save em {src}")
    return copied


def backup(label: str = "", game_dir: Path | None = None, saves_dir: Path = SAVES_DIR) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"backup-{stamp}" + (f"-{label}" if label else "")
    dest = saves_dir / name
    _copy_save(game_dir or game_save_dir(), dest)
    return dest


def list_backups(saves_dir: Path = SAVES_DIR) -> list[Path]:
    return sorted((d for d in saves_dir.glob("backup-*") if (d / "ER0000.sl2").exists()),
                  key=lambda d: d.name)


def restore(backup_dir: Path, game_dir: Path | None = None, saves_dir: Path = SAVES_DIR) -> Path:
    """Copia o backup para a pasta do jogo. Antes, guarda o save atual. Devolve essa cópia."""
    game_dir = game_dir or game_save_dir()
    safety = saves_dir / f"antes-de-restaurar-{time.strftime('%Y%m%d-%H%M%S')}"
    _copy_save(game_dir, safety)
    for name in SAVE_NAMES:
        if (backup_dir / name).exists():
            shutil.copy2(backup_dir / name, game_dir / name)
    return safety
