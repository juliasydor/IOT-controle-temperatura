"""
Monitor MQTT do protótipo: mostra no terminal todas as mensagens do projeto e grava um log.

Uso:
  python monitor_mqtt.py              # roda até Ctrl+C
  python monitor_mqtt.py --minutos 5  # para sozinho depois de 5 minutos

O log (resultados/log_mqtt.csv) é usado por gerar_graficos.py para desenhar o gráfico
de temperatura x estado do ventilador (teste do controle automático com histerese).
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

from config import BROKER, PORTA, PREFIXO

PASTA_RESULTADOS = Path(__file__).resolve().parent.parent / "resultados"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--broker", default=BROKER)
    ap.add_argument("--porta", type=int, default=PORTA)
    ap.add_argument("--prefixo", default=PREFIXO)
    ap.add_argument("--minutos", type=float, default=0, help="0 = até Ctrl+C")
    ap.add_argument("--saida", default=str(PASTA_RESULTADOS / "log_mqtt.csv"))
    args = ap.parse_args()

    Path(args.saida).parent.mkdir(exist_ok=True)
    arquivo = open(args.saida, "w", newline="", encoding="utf-8")
    log = csv.writer(arquivo)
    log.writerow(["data_hora", "segundos", "topico", "mensagem"])
    inicio = time.time()

    def on_connect(cliente, _dados, _flags, codigo, _props):
        print(f"Conectado a {args.broker}:{args.porta} (código {codigo}). Assinando {args.prefixo}/#\n")
        cliente.subscribe(f"{args.prefixo}/#")

    def on_message(_cliente, _dados, msg):
        agora = time.time()
        texto = msg.payload.decode(errors="replace")
        retida = " (retida)" if msg.retain else ""
        print(f"{datetime.now():%H:%M:%S.%f}"[:-3] + f"  {msg.topic:<45} {texto}{retida}")
        log.writerow([datetime.now().isoformat(timespec="milliseconds"),
                      round(agora - inicio, 3), msg.topic, texto])
        arquivo.flush()

    cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    cliente.on_connect = on_connect
    cliente.on_message = on_message
    cliente.connect(args.broker, args.porta, keepalive=30)
    cliente.loop_start()
    try:
        while args.minutos == 0 or time.time() - inicio < args.minutos * 60:
            time.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        cliente.loop_stop()
        cliente.disconnect()
        arquivo.close()
        print(f"\nLog salvo em {args.saida}")


if __name__ == "__main__":
    main()
