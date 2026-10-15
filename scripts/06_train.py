"""Etapa 5: treino PPO contra o chefe.

Rode como administrador, com o personagem na Estaca de Marika:

    python scripts/06_train.py --run treino01 --hours 2
    python scripts/06_train.py --run treino01 --hours 8 --resume   # continua de onde parou

- O modelo é salvo a cada ``--save-every`` passos e ao sair (Ctrl+C também salva).
- Vídeos (vitórias + 1 a cada 50 derrotas) e episodes.csv ficam em runs/<run>/.
- Na primeira vitória o treino para sozinho e salva tudo: restaure o backup do save para
  continuar (o chefe não volta depois de derrotado).

Observação: durante a atualização da rede (alguns segundos a cada ``--n-steps`` passos) o
jogo continua rodando sem comandos. O Elden Ring não tem pausa; é uma limitação aceita.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from elden_rl.env import BossDefeated  # noqa: E402
from elden_rl.factory import make_env  # noqa: E402

RUNS = Path(__file__).resolve().parents[1] / "runs"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, help="nome do treino (pasta em runs/)")
    parser.add_argument("--hours", type=float, default=1.0, help="tempo máximo de treino")
    parser.add_argument("--resume", action="store_true", help="continua do último modelo salvo")
    parser.add_argument("--n-steps", type=int, default=512, help="passos entre atualizações da rede")
    parser.add_argument("--save-every", type=int, default=2048)
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu", "auto"])
    args = parser.parse_args()

    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback, CheckpointCallback

    if args.device == "cuda" and not torch.cuda.is_available():
        print("Aviso: PyTorch não está vendo a placa de vídeo; usando CPU (mais lento).")
        args.device = "cpu"

    run_dir = RUNS / args.run
    ckpt_dir = run_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    latest = run_dir / "model_latest.zip"

    class TimeLimit(BaseCallback):
        def __init__(self, seconds: float):
            super().__init__()
            self.end = time.time() + seconds

        def _on_step(self) -> bool:
            return time.time() < self.end

    print("Clique na janela do jogo. Começando em 5 s... (Ctrl+C para parar e salvar)")
    time.sleep(5)
    env = make_env(run_dir, keep_every=50)

    try:
        import tensorboard  # noqa: F401
        tb = str(run_dir / "tb")
    except ImportError:
        tb = None

    if args.resume and latest.exists():
        print(f"Continuando de {latest}")
        model = PPO.load(latest, env=env, device=args.device, tensorboard_log=tb)
    else:
        model = PPO(
            "MultiInputPolicy", env,
            n_steps=args.n_steps, batch_size=64, n_epochs=4,
            learning_rate=2.5e-4, gamma=0.99, gae_lambda=0.95,
            clip_range=0.2, ent_coef=0.01,
            device=args.device, verbose=1, tensorboard_log=tb,
        )

    callbacks = [CheckpointCallback(args.save_every, str(ckpt_dir), name_prefix="ppo"),
                 TimeLimit(args.hours * 3600)]
    reason = "tempo esgotado"
    try:
        model.learn(total_timesteps=10**9, callback=callbacks,
                    reset_num_timesteps=not args.resume, progress_bar=False)
    except BossDefeated:
        reason = "VITÓRIA! O chefe foi derrotado"
    except KeyboardInterrupt:
        reason = "interrompido (Ctrl+C)"
    finally:
        model.save(latest)
        env.close()
    print(f"\n{reason}. Modelo salvo em {latest}")
    print(f"Lutas registradas em {run_dir / 'episodes.csv'}")
    if reason.startswith("VITÓRIA"):
        print("Para continuar treinando: feche o jogo, restaure o backup do save e rode com --resume.")


if __name__ == "__main__":
    main()
