"""Disparo 31 Março 2026: 70 leads restantes com 2 números novos.

Usa o scheduler real com Rui (oficinas) e Marco (contabilidade).
Outreach profissional + PDF, dividido por 2 instancias em round-robin.

Uso:
    python disparo_amanha.py                    # producao (espera janela)
    python disparo_amanha.py --dry-run          # simulacao
    python disparo_amanha.py --now              # ignora janela horaria
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Forcar janela 9:00-18:00 para hoje
os.environ["HORARIO_INICIO"] = "09:00"
os.environ["HORARIO_FIM"] = "18:00"
os.environ["MAX_ENVIOS_DIA"] = "95"

from whatsapp.scheduler import send_daily_batch


INSTANCES = ["Percep Tudo AI", "Percep Tudo - AI"]


def main():
    parser = argparse.ArgumentParser(description="Disparo com 2 numeros novos")
    parser.add_argument("--dry-run", action="store_true", help="Simular sem enviar")
    parser.add_argument("--now", action="store_true", help="Ignorar janela horaria")
    args = parser.parse_args()

    if args.now:
        os.environ["HORARIO_INICIO"] = "00:00"
        os.environ["HORARIO_FIM"] = "23:59"

    print(f"\n  Instancias: {', '.join(INSTANCES)}")
    print(f"  Modo: {'DRY-RUN' if args.dry_run else 'PRODUCAO'}")
    print()

    stats = send_daily_batch(
        dry_run=args.dry_run,
        priority_cities=["Lisboa", "Porto"],
        instances=INSTANCES,
    )

    if stats["total"] == 0:
        print("  Nenhum lead na fila (ou fora da janela horaria).")

    return 0 if stats["erros"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
