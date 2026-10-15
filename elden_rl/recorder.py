"""Gravação das lutas: vídeo lado a lado + registro em dados de cada episódio.

Cada luta é gravada direto num arquivo temporário no disco (não ocupa memória). No fim:
- vitória: o vídeo é sempre guardado;
- derrota: guardado só a cada ``keep_every`` lutas (amostra para mostrar a evolução);
- todos os episódios entram em ``episodes.csv``, com ou sem vídeo.

O quadro do vídeo tem o jogo à esquerda, "o que a IA vê" à direita e uma faixa embaixo com
as barras lidas, a ação escolhida e a recompensa.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

GAME_SIZE = (640, 360)      # largura x altura do painel do jogo
AI_SIZE = 360               # painel quadrado do "que a IA vê"
STRIP_H = 70                # faixa de texto embaixo
CSV_FIELDS = ["episode", "started_at", "duration_s", "outcome", "boss_hp_min", "player_hp_min",
              "damage_dealt", "steps", "total_reward", "video"]


def _bar(img, x, y, w, frac, color, label):
    cv2.rectangle(img, (x, y), (x + w, y + 10), (60, 60, 60), -1)
    cv2.rectangle(img, (x, y), (x + int(w * max(0.0, min(1.0, frac))), y + 10), color, -1)
    cv2.putText(img, f"{label} {frac:4.0%}", (x, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42,
                (230, 230, 230), 1, cv2.LINE_AA)


def compose(frame: np.ndarray, ai_view: np.ndarray | None, info: dict) -> np.ndarray:
    """Monta o quadro do vídeo: jogo | IA, com a faixa de informações embaixo."""
    W = GAME_SIZE[0] + AI_SIZE
    out = np.zeros((GAME_SIZE[1] + STRIP_H, W, 3), np.uint8)
    out[: GAME_SIZE[1], : GAME_SIZE[0]] = cv2.resize(frame, GAME_SIZE, interpolation=cv2.INTER_AREA)

    if ai_view is not None:
        v = ai_view
        if v.ndim == 2:
            v = cv2.cvtColor(v, cv2.COLOR_GRAY2BGR)
        out[: AI_SIZE, GAME_SIZE[0]:] = cv2.resize(v, (AI_SIZE, AI_SIZE), interpolation=cv2.INTER_NEAREST)
    cv2.putText(out, "O QUE A IA VE", (GAME_SIZE[0] + 10, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                (0, 220, 255), 1, cv2.LINE_AA)

    y = GAME_SIZE[1] + 25
    v = info.get("values", {})
    _bar(out, 15, y, 180, v.get("player_hp", 0), (40, 40, 200), "vida")
    _bar(out, 215, y, 180, v.get("player_stamina", 0), (60, 170, 60), "vigor")
    _bar(out, 415, y, 300, v.get("boss_hp", 0), (20, 20, 140), "chefe")
    text = (f"episodio {info.get('episode', 0)}   acao: {info.get('action', '-')}   "
            f"recompensa: {info.get('reward', 0):+.2f}   t={info.get('t', 0):5.1f}s")
    cv2.putText(out, text, (15, y + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (230, 230, 230), 1, cv2.LINE_AA)
    return out


@dataclass
class EpisodeRecorder:
    out_dir: Path
    # Um quadro por decisão do agente (passo de 0,2 s = 5 por segundo). Com 15 o vídeo saía 3x
    # mais rápido que a luta real.
    fps: float = 5.0
    keep_every: int = 50           # guarda o vídeo de 1 a cada N derrotas
    episode: int = 0
    _writer: object = None
    _tmp: Path | None = None
    _stats: dict = field(default_factory=dict)
    _last_frame_t: float = 0.0

    def __post_init__(self):
        self.out_dir = Path(self.out_dir)
        (self.out_dir / "videos").mkdir(parents=True, exist_ok=True)
        self.csv_path = self.out_dir / "episodes.csv"
        if self.csv_path.exists():  # continua a numeração de uma sessão anterior
            with open(self.csv_path, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            self.episode = max((int(r["episode"]) for r in rows), default=0)

    @property
    def recording(self) -> bool:
        return self._writer is not None

    def start(self) -> None:
        if self.recording:
            self.end("interrupted")
        self.episode += 1
        self._tmp = self.out_dir / "videos" / f"_tmp_ep{self.episode:05d}.mp4"
        size = (GAME_SIZE[0] + AI_SIZE, GAME_SIZE[1] + STRIP_H)
        self._writer = cv2.VideoWriter(str(self._tmp), cv2.VideoWriter_fourcc(*"mp4v"), self.fps, size)
        self._stats = {"started_at": time.strftime("%Y-%m-%d %H:%M:%S"), "t0": time.time(),
                       "boss_hp_min": 1.0, "player_hp_min": 1.0, "steps": 0, "total_reward": 0.0}
        self._last_frame_t = 0.0

    def add(self, frame: np.ndarray, values: dict, ai_view: np.ndarray | None = None,
            action: str = "-", reward: float = 0.0) -> None:
        """Registra um passo. Só escreve no vídeo no ritmo de ``fps`` (economiza disco)."""
        if not self.recording:
            return
        s = self._stats
        s["steps"] += 1
        s["total_reward"] += reward
        if values.get("boss_hp", 0) > 0:
            s["boss_hp_min"] = min(s["boss_hp_min"], values["boss_hp"])
        if any(values.get(k, 0) > 0 for k in ("player_fp", "player_stamina")):
            s["player_hp_min"] = min(s["player_hp_min"], values.get("player_hp", 0))
        now = time.time()
        if now - self._last_frame_t >= 1.0 / self.fps:
            info = {"values": values, "action": action, "reward": reward,
                    "episode": self.episode, "t": now - s["t0"]}
            self._writer.write(compose(frame, ai_view, info))
            self._last_frame_t = now

    def end(self, outcome: str) -> Path | None:
        """Fecha o episódio (``"victory"``, ``"death"``, ``"timeout"``...). Devolve o vídeo guardado."""
        if not self.recording:
            return None
        self._writer.release()
        self._writer = None
        keep = outcome == "victory" or (self.keep_every > 0 and self.episode % self.keep_every == 0)
        video = None
        if keep:
            video = self._tmp.with_name(f"ep{self.episode:05d}_{outcome}.mp4")
            self._tmp.replace(video)
        else:
            self._tmp.unlink(missing_ok=True)
        s = self._stats
        row = {
            "episode": self.episode, "started_at": s["started_at"],
            "duration_s": round(time.time() - s["t0"], 2), "outcome": outcome,
            "boss_hp_min": round(s["boss_hp_min"], 4), "player_hp_min": round(s["player_hp_min"], 4),
            "damage_dealt": round(1.0 - s["boss_hp_min"], 4), "steps": s["steps"],
            "total_reward": round(s["total_reward"], 4), "video": video.name if video else "",
        }
        new = not self.csv_path.exists()
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if new:
                w.writeheader()
            w.writerow(row)
        return video
