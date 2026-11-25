"""
Envia um comando ou um novo limite ao ESP32 pela linha de comando (alternativa ao MQTT Explorer).

Exemplos:
  python enviar_comando.py LIGAR
  python enviar_comando.py DESLIGAR
  python enviar_comando.py AUTO
  python enviar_comando.py --limite 26.5
"""

import argparse
import time

import paho.mqtt.client as mqtt

from conexao import conectar
from config import BROKER, PORTA, PREFIXO, topicos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("comando", nargs="?", choices=["LIGAR", "DESLIGAR", "AUTO"])
    ap.add_argument("--limite", type=float, help="novo limite de temperatura em °C (10 a 50)")
    ap.add_argument("--broker", default=BROKER)
    ap.add_argument("--porta", type=int, default=PORTA)
    ap.add_argument("--prefixo", default=PREFIXO)
    args = ap.parse_args()
    if not args.comando and args.limite is None:
        ap.error("informe um comando (LIGAR, DESLIGAR, AUTO) e/ou --limite")

    t = topicos(args.prefixo)
    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    conectar(cliente, args.broker, args.porta)
    if args.comando:
        cliente.publish(t["comando"], args.comando).wait_for_publish()
        print(f"Publicado '{args.comando}' em {t['comando']}")
    if args.limite is not None:
        cliente.publish(t["limite"], f"{args.limite:.1f}").wait_for_publish()
        print(f"Publicado '{args.limite:.1f}' em {t['limite']}")
    time.sleep(0.5)
    cliente.disconnect()
    cliente.loop_stop()


if __name__ == "__main__":
    main()
