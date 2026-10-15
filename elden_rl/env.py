"""Ambiente Gymnasium: a luta contra o chefe vista como um problema de aprendizado por reforço.

A cada passo (``step_seconds``, padrão 0,2 s, ou seja 5 decisões por segundo):
  1. o agente escolhe uma ação (andar, rolar, atacar, defender, curar...);
  2. o ambiente segura/aperta as teclas durante o passo;
  3. no fim do passo captura a tela, lê o HUD e calcula a recompensa.

Observação (dicionário):
  - ``image``: últimos 4 quadros em tons de cinza, 96x96 (o "que a IA vê");
  - ``stats``: vida, vigor e vida do chefe (0 a 1) + a última ação (one-hot).

Recompensa por passo:
  + dano causado ao chefe (fração da barra x ``w_damage``)
  - dano recebido (fração da barra x ``w_hurt``)
  + cura (fração recuperada x ``w_heal``)
  - pequena penalidade por tempo (incentiva lutar em vez de fugir)
  fim: ``r_victory`` na vitória, ``-r_death`` na morte.

Depois de uma vitória o chefe não volta: o próximo ``reset`` avisa para restaurar o save.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Callable

import cv2
import gymnasium as gym
import numpy as np

from .events import EpisodeTracker

# (nome, teclas seguradas durante o passo, tecla tocada no início do passo)
ACTIONS: list[tuple[str, tuple[str, ...], str | None]] = [
    ("parado", (), None),
    ("frente", ("forward",), None),
    ("tras", ("back",), None),
    ("esquerda", ("left",), None),
    ("direita", ("right",), None),
    ("ataque", (), "attack"),
    ("ataque_forte", (), "heavy"),
    ("rolar_frente", ("forward",), "dodge"),
    ("rolar_tras", ("back",), "dodge"),
    ("rolar_esquerda", ("left",), "dodge"),
    ("rolar_direita", ("right",), "dodge"),
    ("defender", ("guard",), None),
    ("curar", (), "flask"),
]
ACTION_NAMES = [a[0] for a in ACTIONS]


class BossDefeated(RuntimeError):
    """O chefe foi derrotado: restaure o backup do save para continuar treinando."""


@dataclass
class EnvConfig:
    step_seconds: float = 0.2
    max_steps: int = 1500            # ~5 min de luta: depois disso o episódio é truncado
    image_size: int = 96
    frame_stack: int = 4
    w_damage: float = 10.0           # barra inteira do chefe = +10
    w_hurt: float = 5.0              # barra inteira do personagem = -5
    w_heal: float = 1.0
    time_penalty: float = 0.002
    r_victory: float = 20.0
    r_death: float = 5.0
    noise: float = 0.005             # variações menores que isso nas barras são ignoradas


class EldenBossEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, grab: Callable[[], np.ndarray], hud, controller, reset_routine,
                 screen_state: Callable[[np.ndarray], str], cfg: EnvConfig | None = None,
                 recorder=None, clock: Callable[[], float] = time.time,
                 sleep: Callable[[float], None] = time.sleep):
        super().__init__()
        self.grab, self.hud, self.ctl = grab, hud, controller
        self.reset_routine = reset_routine
        self.screen_state = screen_state
        self.cfg = cfg or EnvConfig()
        self.recorder = recorder
        self.clock, self.sleep = clock, sleep
        n, s = len(ACTIONS), self.cfg.image_size
        self.action_space = gym.spaces.Discrete(n)
        self.observation_space = gym.spaces.Dict({
            "image": gym.spaces.Box(0, 255, shape=(self.cfg.frame_stack, s, s), dtype=np.uint8),
            "stats": gym.spaces.Box(0.0, 1.0, shape=(3 + n,), dtype=np.float32),
        })
        self.tracker = EpisodeTracker()
        self.frames: deque = deque(maxlen=self.cfg.frame_stack)
        self.boss_defeated = False
        self._values: dict[str, float] = {}
        self._last_action = 0
        self._steps = 0
        self._next_t = 0.0

    # ---------- observação ----------
    def _small(self, frame: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        s = self.cfg.image_size
        return cv2.resize(gray, (s, s), interpolation=cv2.INTER_AREA)

    def _obs(self) -> dict:
        n = len(ACTIONS)
        onehot = np.zeros(n, np.float32)
        onehot[self._last_action] = 1.0
        v = self._values
        stats = np.array([v.get("player_hp", 0), v.get("player_stamina", 0), v.get("boss_hp", 0)],
                         np.float32)
        return {"image": np.stack(list(self.frames), 0),
                "stats": np.clip(np.concatenate([stats, onehot]), 0.0, 1.0)}

    def _observe(self) -> tuple[np.ndarray, dict, str]:
        frame = self.grab()
        return frame, self.hud.read(frame), self.screen_state(frame)

    # ---------- API Gymnasium ----------
    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.ctl.release_all()
        if self.boss_defeated:
            raise BossDefeated("O chefe foi derrotado. Feche o jogo, restaure o backup do save "
                               "(saves/) e recomece o treino com --resume.")
        if not self.reset_routine.run():
            raise RuntimeError("O reset não conseguiu chegar ao chefe (veja as mensagens [reset]).")
        self.tracker.reset()
        frame, values, _ = self._observe()
        self._values = values
        self.frames.clear()
        small = self._small(frame)
        for _ in range(self.cfg.frame_stack):
            self.frames.append(small)
        self._last_action = 0
        self._steps = 0
        self._next_t = self.clock()
        if self.recorder is not None:
            self.recorder.start()
        return self._obs(), {"values": dict(values)}

    def _apply(self, action: int) -> None:
        _, held, tap = ACTIONS[action]
        self.ctl.set_held(set(held))
        if tap:
            self.ctl.tap(tap, 0.06)

    def _reward(self, prev: dict, cur: dict) -> float:
        c = self.cfg
        r = -c.time_penalty
        d_boss = prev.get("boss_hp", 0) - cur.get("boss_hp", 0)
        if d_boss > c.noise and cur.get("boss_hp", 0) > 0:     # barra sumida não conta como dano
            r += c.w_damage * d_boss
        d_hp = cur.get("player_hp", 0) - prev.get("player_hp", 0)
        if d_hp < -c.noise:
            r += c.w_hurt * d_hp
        elif d_hp > c.noise:
            r += c.w_heal * d_hp
        return float(r)

    def step(self, action):
        action = int(action)
        self._apply(action)
        self._next_t += self.cfg.step_seconds
        wait = self._next_t - self.clock()
        if wait > 0:
            self.sleep(wait)
        else:                                  # atrasou (PC ocupado): não acumula atraso
            self._next_t = self.clock()

        frame, values, screen = self._observe()
        hud_visible = any(values.get(k, 0) > 0 for k in ("player_hp", "player_fp", "player_stamina"))
        event = self.tracker.update(values, screen, self.clock())

        reward = 0.0
        if hud_visible and screen == "game":
            reward = self._reward(self._values, values)
            self._values = values
            self.frames.append(self._small(frame))
        self._last_action = action
        self._steps += 1

        terminated = event in ("death", "victory")
        if event == "death":
            reward -= self.cfg.r_death
        elif event == "victory":
            reward += self.cfg.r_victory
            self.boss_defeated = True
        truncated = not terminated and self._steps >= self.cfg.max_steps

        if self.recorder is not None:
            self.recorder.add(frame, values, ai_view=self.frames[-1], action=ACTION_NAMES[action],
                              reward=reward)
            if terminated or truncated:
                self.recorder.end(event if terminated else "timeout")
        if terminated or truncated:
            # Num truncamento o personagem continua vivo na arena: o próximo reset vê a barra
            # do chefe e devolve o controle na hora, e a luta segue como um novo episódio.
            self.ctl.release_all()

        info = {"event": event, "values": dict(values), "action_name": ACTION_NAMES[action]}
        return self._obs(), reward, terminated, truncated, info

    def close(self):
        self.ctl.release_all()
        if self.recorder is not None:
            self.recorder.end("interrupted")
