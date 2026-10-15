"""Leitura das barras do HUD (vida do personagem, vigor e vida do chefe) por cor.

Cada barra é uma faixa fina da tela, definida em ``hud_config.json`` como fração da área do
jogo (x, y, largura, altura entre 0 e 1). Assim a configuração vale para qualquer resolução.

Como a barra de vida do personagem cresce com o atributo Vigor, a leitura é feita contra um
comprimento de referência (``full_columns``), medido com a vida cheia pelo script de
calibração. A barra do chefe tem tamanho fixo e é lida contra a largura da própria região.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import cv2
import numpy as np

CONFIG_PATH = Path(__file__).resolve().parents[1] / "hud_config.json"


@dataclass
class ColorRange:
    """Faixa de cor em HSV (OpenCV: H 0–179, S e V 0–255). Duas faixas cobrem o vermelho."""

    ranges: list[tuple[list[int], list[int]]]

    def mask(self, bgr: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        out = np.zeros(hsv.shape[:2], dtype=bool)
        for lo, hi in self.ranges:
            out |= cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8)) > 0
        return out


RED = ColorRange([([0, 120, 70], [8, 255, 255]), ([170, 120, 70], [179, 255, 255])])
# A barra do chefe é um vermelho bem escuro (V ~ 75-90), então aceita brilho mais baixo
# e exige saturação alta para não confundir com pedras e sombras.
DARK_RED = ColorRange([([0, 150, 35], [8, 255, 255]), ([170, 150, 35], [179, 255, 255])])
GREEN = ColorRange([([40, 90, 60], [85, 255, 255])])
BLUE = ColorRange([([95, 110, 60], [130, 255, 255])])
COLORS = {"red": RED, "darkred": DARK_RED, "green": GREEN, "blue": BLUE}


@dataclass
class Bar:
    x: float
    y: float
    w: float
    h: float
    color: str = "red"
    full_columns: int | None = None  # comprimento da barra cheia, em pixels (calibrado)
    calib_width: int | None = None   # largura da tela na calibração; corrige outras resoluções

    def crop(self, frame: np.ndarray) -> np.ndarray:
        H, W = frame.shape[:2]
        x0, y0 = int(self.x * W), int(self.y * H)
        x1, y1 = max(x0 + 1, int((self.x + self.w) * W)), max(y0 + 1, int((self.y + self.h) * H))
        return frame[y0:y1, x0:x1]

    def filled_columns(self, frame: np.ndarray, max_gap: int = 3, start_window: int = 16) -> int:
        """Comprimento da barra: trecho contínuo pintado a partir da borda esquerda.

        As barras do jogo sempre enchem da esquerda para a direita. Contar só o trecho
        contínuo a partir do início ignora pixels soltos da mesma cor no cenário (pedras
        avermelhadas, grama) e tolera buracos de até ``max_gap`` colunas.
        """
        cols = COLORS[self.color].mask(self.crop(frame)).mean(axis=0) >= 0.5
        head = cols[:start_window]  # a barra precisa começar perto da borda esquerda da região
        if not head.any():
            return 0
        start = int(np.argmax(head))
        end, gap = start, 0
        for i in range(start, len(cols)):
            if cols[i]:
                end, gap = i + 1, 0
            else:
                gap += 1
                if gap > max_gap:
                    break
        return int(end - start)

    def read(self, frame: np.ndarray) -> float:
        """Fração da barra preenchida, entre 0 e 1."""
        cols = self.filled_columns(frame)
        if self.full_columns:
            # A calibração foi feita numa largura de tela; em outra resolução a barra cheia tem
            # outro comprimento em pixels, proporcional à largura.
            ref = self.full_columns * (frame.shape[1] / self.calib_width if self.calib_width else 1.0)
        else:
            ref = self.crop(frame).shape[1]
        return float(min(1.0, cols / max(ref, 1)))

    def rect_px(self, frame: np.ndarray) -> tuple[int, int, int, int]:
        H, W = frame.shape[:2]
        return int(self.x * W), int(self.y * H), int((self.x + self.w) * W), int((self.y + self.h) * H)


# Posições medidas num print real do jogo em 1280x720 (12/10/2026), com o HUD em "Ligado".
# As barras do personagem começam em x ~ 104 px e crescem para a direita conforme os
# atributos, por isso a região vai até quase metade da tela. A barra do chefe foi medida num
# print da luta contra o Soldado de Godrick (x 312-973 px, y 580-584 px).
DEFAULT_BARS = {
    "player_hp": Bar(0.078, 0.0458, 0.45, 0.0042, "red"),
    "player_fp": Bar(0.078, 0.0625, 0.45, 0.0042, "blue"),
    "player_stamina": Bar(0.078, 0.0792, 0.45, 0.0042, "green"),
    "boss_hp": Bar(0.244, 0.8056, 0.516, 0.0056, "darkred"),
}


@dataclass
class HUD:
    bars: dict[str, Bar] = field(default_factory=lambda: {k: Bar(**asdict(v)) for k, v in DEFAULT_BARS.items()})

    def read(self, frame: np.ndarray) -> dict[str, float]:
        return {name: bar.read(frame) for name, bar in self.bars.items()}

    @staticmethod
    def hud_visible(values: dict[str, float]) -> bool:
        """Vida, mana e vigor zerados ao mesmo tempo = HUD escondido (menu, Graça, tela de
        carregamento), não morte. Na morte a vida zera, mas o vigor continua na tela."""
        return any(values.get(k, 0) > 0 for k in ("player_hp", "player_fp", "player_stamina"))

    def calibrate_full(self, frame: np.ndarray, names: tuple[str, ...] = ("player_hp", "player_fp", "player_stamina")) -> dict:
        """Grava o comprimento das barras cheias. Rode com vida e vigor cheios."""
        for n in names:
            self.bars[n].full_columns = self.bars[n].filled_columns(frame)
            self.bars[n].calib_width = int(frame.shape[1])
        return {n: self.bars[n].full_columns for n in names}

    def draw(self, frame: np.ndarray) -> np.ndarray:
        """Desenha as regiões e as leituras sobre o quadro, para conferir a calibração."""
        out = frame.copy()
        values = self.read(frame)
        for name, bar in self.bars.items():
            x0, y0, x1, y1 = bar.rect_px(frame)
            cv2.rectangle(out, (x0, y0 - 2), (x1, y1 + 2), (255, 255, 0), 1)
            cv2.putText(out, f"{name}: {values[name]:.0%}", (x1 + 6, y1 + 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 0), 1, cv2.LINE_AA)
        return out

    def save(self, path: Path = CONFIG_PATH) -> None:
        path.write_text(json.dumps({k: asdict(v) for k, v in self.bars.items()}, indent=2))

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "HUD":
        if not Path(path).exists():
            return cls()
        data = json.loads(Path(path).read_text())
        bars = {k: Bar(**v) for k, v in data.items()}
        for b in bars.values():  # configurações antigas foram calibradas em 1280x720
            if b.full_columns and not b.calib_width:
                b.calib_width = 1280
        return cls(bars)


def draw_grid(frame: np.ndarray, step: float = 0.05) -> np.ndarray:
    """Grade com marcas a cada 5% da tela, para achar as coordenadas das barras."""
    out = frame.copy()
    H, W = out.shape[:2]
    for i in range(1, int(1 / step)):
        f = i * step
        x, y = int(f * W), int(f * H)
        cv2.line(out, (x, 0), (x, H), (80, 80, 80), 1)
        cv2.line(out, (0, y), (W, y), (80, 80, 80), 1)
        cv2.putText(out, f"{f:.2f}", (x + 2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
        cv2.putText(out, f"{f:.2f}", (2, y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 255, 255), 1)
    return out


def screen_state(frame: np.ndarray) -> str:
    """Classifica a tela: ``"respawn_prompt"``, ``"black"`` ou ``"game"``.

    A tela de "Escolha o local de renascimento" é toda preta, com uma faixa de texto claro
    entre 76% e 88% da altura. Telas de carregamento e transições são pretas sem texto.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    H = gray.shape[0]
    top = gray[: int(0.70 * H)]
    band = gray[int(0.76 * H): int(0.88 * H)]
    if top.mean() > 8:
        return "game"
    bright = int((band > 150).sum())
    min_bright = 200 * (frame.shape[1] / 1280) * (H / 720)
    return "respawn_prompt" if bright >= min_bright else "black"
