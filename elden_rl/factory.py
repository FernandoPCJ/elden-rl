"""Monta o ambiente real (jogo aberto no Windows) com todas as peças."""

from __future__ import annotations

from pathlib import Path

from .controls import Controller
from .env import EldenBossEnv, EnvConfig
from .hud import HUD, screen_state
from .recorder import EpisodeRecorder
from .reset import ResetRoutine
from .window import GameCapture


def make_env(run_dir: Path, keep_every: int = 50, cfg: EnvConfig | None = None) -> EldenBossEnv:
    cap = GameCapture()
    hud = HUD.load()
    ctl = Controller()

    def observe():
        frame = cap.grab()
        return hud.read(frame), screen_state(frame)

    try:
        cap.focus()
    except Exception:
        pass
    recorder = EpisodeRecorder(Path(run_dir), keep_every=keep_every)
    return EldenBossEnv(cap.grab, hud, ctl, ResetRoutine(observe, ctl), screen_state,
                        cfg=cfg, recorder=recorder)
