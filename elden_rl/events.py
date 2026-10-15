"""Detecta os eventos da luta a partir das leituras do HUD, quadro a quadro.

Padrões observados no jogo (12/10/2026):
- morte: vida em 0% com mana/vigor ainda na tela, por vários segundos ("Você morreu");
- HUD oculto: vida, mana e vigor em 0% ao mesmo tempo (menus, telas pretas, renascimento);
- chefe presente: barra do chefe acima de 0% (aparece ao atravessar a névoa);
- vitória: a barra do chefe some com o personagem vivo e o HUD visível.

Cada evento só é confirmado depois de durar um tempo mínimo, para ignorar os quadros de
transição em que o HUD aparece ou some aos poucos.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EpisodeTracker:
    # segundos com vida 0% (HUD visível) para confirmar morte. A tela "Você morreu" dura ~16 s;
    # 0,5 s gerou mortes falsas no treino de 12/10 (lutas de 5-7 s), por isso 1,5 s.
    death_after: float = 1.5
    boss_after: float = 0.3       # segundos com a barra do chefe na tela para confirmar a luta
    victory_after: float = 2.0    # segundos sem a barra do chefe (vivo, HUD visível) = vitória
    boss_in_fight: bool = False
    last_boss_hp: float = 0.0
    _since: dict = field(default_factory=dict)

    def _hold(self, key: str, active: bool, now: float, needed: float) -> bool:
        """True quando a condição ``key`` está ativa há pelo menos ``needed`` segundos."""
        if not active:
            self._since.pop(key, None)
            return False
        start = self._since.setdefault(key, now)
        return now - start >= needed

    def reset(self) -> None:
        self.boss_in_fight = False
        self.last_boss_hp = 0.0
        self._since.clear()

    def update(self, values: dict[str, float], screen: str, now: float) -> str | None:
        """Recebe as leituras de um quadro e devolve o evento confirmado neste quadro, se houver.

        Eventos: ``"boss_start"``, ``"death"``, ``"victory"``, ``"respawn_prompt"``.
        Cada evento é devolvido uma única vez, na transição.
        """
        if screen == "respawn_prompt":
            if self._hold("prompt", True, now, 0.2) and not self._since.get("prompt_sent"):
                self._since["prompt_sent"] = now
                return "respawn_prompt"
            return None
        self._since.pop("prompt", None)
        self._since.pop("prompt_sent", None)

        hud = any(values.get(k, 0) > 0 for k in ("player_hp", "player_fp", "player_stamina"))
        if not hud or screen != "game":
            return None

        hp, boss = values.get("player_hp", 0.0), values.get("boss_hp", 0.0)

        if self._hold("dead", hp <= 0.0, now, self.death_after):
            if not self._since.get("dead_sent"):
                self._since["dead_sent"] = now
                self.boss_in_fight = False
                return "death"
            return None
        if hp > 0:
            self._since.pop("dead_sent", None)

        if not self.boss_in_fight:
            if self._hold("boss", boss > 0.02, now, self.boss_after):
                self.boss_in_fight = True
                self.last_boss_hp = boss
                return "boss_start"
            return None

        if boss > 0.0:
            self.last_boss_hp = boss
        if self._hold("boss_gone", boss <= 0.0 and hp > 0, now, self.victory_after):
            self.boss_in_fight = False
            return "victory"
        return None
