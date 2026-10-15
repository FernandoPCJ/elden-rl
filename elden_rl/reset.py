"""Roteiro de reset: da morte (ou da Estaca de Marika) até o começo da luta com o chefe.

Funciona como uma máquina de estados guiada pelo que aparece na tela:

    tela de renascimento  -> confirma "Estaca de Marika" (opção que já vem selecionada)
    tela preta            -> espera o carregamento
    "Você morreu"         -> espera (vida 0% com o HUD na tela)
    jogo, sem chefe       -> anda para frente apertando "interagir" para atravessar a névoa
    barra do chefe        -> trava a mira no chefe e devolve o controle ao agente

Da Estaca, o personagem renasce de frente para a névoa, em linha reta.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

Observation = tuple[dict[str, float], str]  # (leituras do HUD, estado da tela)


@dataclass
class ResetConfig:
    timeout: float = 60.0           # desiste depois disso (algo inesperado na tela)
    interact_every: float = 0.5     # aperta "interagir" a cada X s enquanto anda até a névoa
    confirm_every: float = 1.0      # repete a confirmação se a tela de renascimento continuar
    confirm_keys: tuple[str, ...] = ("interact", "confirm")  # tenta E; se não sair, Enter
    # Depois que a barra do chefe aparece, anda mais um pouco antes de travar a mira: logo após a
    # névoa o chefe ainda está fora do alcance da trava (treino de 12/10: 22 de 36 lutas sem
    # nenhum golpe acertado).
    walk_after_fog: float = 3.5     # até ~o meio da arena (ajustado com o usuário em 12/10)


class ResetRoutine:
    def __init__(self, observe: Callable[[], Observation], controller, cfg: ResetConfig | None = None,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
                 log: Callable[[str], None] = print):
        self.observe = observe
        self.ctl = controller
        self.cfg = cfg or ResetConfig()
        self.clock = clock
        self.sleep = sleep
        self.log = log

    def run(self) -> bool:
        """Leva o personagem até a luta. Devolve True quando a barra do chefe aparece."""
        c = self.cfg
        start = self.clock()
        last_interact = last_confirm = -1e9
        confirm_tries = 0
        state = None
        try:
            while self.clock() - start < c.timeout:
                values, screen = self.observe()
                now = self.clock()
                hud = any(values.get(k, 0) > 0 for k in ("player_hp", "player_fp", "player_stamina"))

                if screen == "respawn_prompt":
                    new = "renascimento"
                    self.ctl.set_held(set())
                    if now - last_confirm >= c.confirm_every:
                        key = c.confirm_keys[min(confirm_tries // 2, len(c.confirm_keys) - 1)]
                        if key in self.ctl.keys:
                            self.ctl.tap(key, 0.08)
                        confirm_tries += 1
                        last_confirm = now
                elif screen != "game" or not hud:
                    new = "carregando"
                    self.ctl.set_held(set())
                elif values.get("player_hp", 0) <= 0:
                    new = "morto"
                    self.ctl.set_held(set())
                elif values.get("boss_hp", 0) > 0.02:
                    self.ctl.set_held(set())
                    self.log(f"[reset] chefe na tela ({now - start:.1f} s)")
                    if c.walk_after_fog > 0:
                        self.log(f"[reset] andando {c.walk_after_fog:.1f} s até o meio da arena")
                        self.ctl.hold(["forward"], c.walk_after_fog)
                    self.log(f"[reset] travando a mira (tecla {self.ctl.keys.get('lock_on', '?')})")
                    self.ctl.tap("lock_on", 0.15)
                    self.log("[reset] luta começando, controle com o agente")
                    return True
                else:
                    new = "andando até a névoa"
                    self.ctl.set_held({"forward"})
                    if now - last_interact >= c.interact_every:
                        self.ctl.tap("interact", 0.06)
                        last_interact = now

                if new != state:
                    self.log(f"[reset] {new}")
                    state = new
                self.sleep(0.05)
            self.log("[reset] tempo esgotado sem encontrar o chefe")
            return False
        finally:
            self.ctl.release_all()
