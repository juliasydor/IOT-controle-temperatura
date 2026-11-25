"""
Mede os tempos de resposta do protótipo via MQTT (item 7 da atividade A4).

Pré-requisito: a simulação do Wokwi (ou a placa real) deve estar RODANDO e conectada ao broker.

O que é medido (N repetições de cada, padrão N = 4):
  1. Ping (ida e volta da rede): o script publica em diagnostico/ping e o ESP32 devolve
     o mesmo conteúdo em diagnostico/pong. RTT_ping = tempo de ida e volta.
  2. Atuador (relé): o script publica LIGAR/DESLIGAR em ventilador/comando e espera a
     confirmação em ventilador/estado (o ESP32 só publica depois de comutar o relé).
        tempo comando -> atuador  ~=  RTT_comando - RTT_ping_médio / 2
  3. Sensor (DHT22): o script publica um id em diagnostico/medir; o ESP32 lê o sensor
     na hora e publica a leitura (com o mesmo id) em diagnostico/leitura.
        tempo detecção -> plataforma MQTT  ~=  RTT_medição - RTT_ping_médio / 2
     (a metade do ping desconta a ida do pedido do computador até o ESP32)

Saídas (pasta resultados/):
  medicoes.csv        todas as medições individuais
  tabela_tempos.md    tabela pronta para o artigo
  grafico_tempos.png  gráfico (gerado por gerar_graficos.py)

Uso:
  pip install -r requirements.txt
  python medir_tempos.py            # 4 medições de cada
  python medir_tempos.py --n 10     # mais repetições
"""

import argparse
import csv
import json
import queue
import statistics
import sys
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt

from config import BROKER, PORTA, PREFIXO, topicos

PASTA_RESULTADOS = Path(__file__).resolve().parent.parent / "resultados"
TIMEOUT_S = 10


class Medidor:
    def __init__(self, broker, porta, prefixo):
        self.t = topicos(prefixo)
        self.fila = queue.Queue()
        self.cliente = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id=f"medidor-{uuid.uuid4().hex[:8]}")
        self.cliente.on_message = self._on_message
        self.cliente.connect(broker, porta, keepalive=30)
        self.cliente.loop_start()
        for nome in ("estado", "pong", "leitura", "status"):
            self.cliente.subscribe(self.t[nome], qos=0)
        time.sleep(1.0)  # aguarda as assinaturas serem confirmadas

    def _on_message(self, _cliente, _dados, msg):
        # registra o instante de chegada o mais cedo possível
        self.fila.put((time.perf_counter(), msg.topic, msg.payload.decode(errors="replace")))

    def _limpar_fila(self):
        while not self.fila.empty():
            self.fila.get_nowait()

    def _esperar(self, topico, condicao, desde):
        limite = time.time() + TIMEOUT_S
        while time.time() < limite:
            try:
                t, top, payload = self.fila.get(timeout=0.5)
            except queue.Empty:
                continue
            if top == topico and t >= desde and condicao(payload):
                return t, payload
        return None, None

    def ping(self):
        self._limpar_fila()
        ident = uuid.uuid4().hex[:8]
        t0 = time.perf_counter()
        self.cliente.publish(self.t["ping"], ident)
        t1, _ = self._esperar(self.t["pong"], lambda p: p == ident, t0)
        return None if t1 is None else (t1 - t0) * 1000

    def comando(self, acao, esperado):
        self._limpar_fila()
        t0 = time.perf_counter()
        self.cliente.publish(self.t["comando"], acao)
        t1, _ = self._esperar(self.t["estado"], lambda p: p == esperado, t0)
        return None if t1 is None else (t1 - t0) * 1000

    def medir_sensor(self):
        self._limpar_fila()
        ident = uuid.uuid4().hex[:8]
        t0 = time.perf_counter()
        self.cliente.publish(self.t["medir"], ident)

        def confere(p):
            try:
                return json.loads(p).get("id") == ident
            except ValueError:
                return False

        t1, payload = self._esperar(self.t["leitura"], confere, t0)
        if t1 is None:
            return None, None
        return (t1 - t0) * 1000, json.loads(payload)

    def encerrar(self):
        self.cliente.loop_stop()
        self.cliente.disconnect()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=4, help="repetições por medição (padrão 4)")
    ap.add_argument("--broker", default=BROKER)
    ap.add_argument("--porta", type=int, default=PORTA)
    ap.add_argument("--prefixo", default=PREFIXO)
    ap.add_argument("--intervalo", type=float, default=3.0,
                    help="segundos entre medições (>= 2 s por causa do DHT22)")
    args = ap.parse_args()

    PASTA_RESULTADOS.mkdir(exist_ok=True)
    m = Medidor(args.broker, args.porta, args.prefixo)
    print(f"Conectado a {args.broker}:{args.porta}. Verificando se o ESP32 responde...")

    if m.ping() is None:
        print("ERRO: o ESP32 não respondeu ao ping. A simulação do Wokwi está rodando?")
        m.encerrar()
        sys.exit(1)

    # 1) Ping
    pings = []
    for i in range(args.n):
        rtt = m.ping()
        print(f"  ping {i + 1}: {rtt:.0f} ms" if rtt else f"  ping {i + 1}: sem resposta")
        if rtt:
            pings.append(rtt)
        time.sleep(1)
    meia_ida = statistics.mean(pings) / 2
    print(f"RTT médio do ping: {2 * meia_ida:.0f} ms (ida estimada: {meia_ida:.0f} ms)\n")

    linhas = []

    # 2) Atuador: parte de DESLIGADO e alterna LIGAR / DESLIGAR
    m.comando("DESLIGAR", "DESLIGADO")
    time.sleep(args.intervalo)
    for i in range(args.n):
        acao, esperado = ("LIGAR", "LIGADO") if i % 2 == 0 else ("DESLIGAR", "DESLIGADO")
        rtt = m.comando(acao, esperado)
        if rtt is None:
            print(f"  atuador {i + 1} ({acao}): sem resposta")
        else:
            est = rtt - meia_ida
            print(f"  atuador {i + 1} ({acao}): ida e volta {rtt:.0f} ms -> comando->relé ~ {est:.0f} ms")
            linhas.append({"tipo": "Atuador", "dispositivo": "Relé (ventilador)", "acao": acao,
                           "rtt_ms": round(rtt, 1), "tempo_ms": round(est, 1), "leitura_ms": ""})
        time.sleep(args.intervalo)
    m.cliente.publish(m.t["comando"], "AUTO")  # devolve o controle ao modo automático
    time.sleep(args.intervalo)

    # 3) Sensor
    for i in range(args.n):
        rtt, dados = m.medir_sensor()
        if rtt is None:
            print(f"  sensor {i + 1}: sem resposta")
        else:
            est = rtt - meia_ida
            print(f"  sensor {i + 1}: {dados['temperatura']} °C / {dados['umidade']} % | "
                  f"ida e volta {rtt:.0f} ms -> leitura->broker->cliente ~ {est:.0f} ms "
                  f"(leitura no ESP32: {dados['leitura_ms']} ms)")
            linhas.append({"tipo": "Sensor", "dispositivo": "DHT22", "acao": "Leitura",
                           "rtt_ms": round(rtt, 1), "tempo_ms": round(est, 1),
                           "leitura_ms": dados["leitura_ms"]})
        time.sleep(args.intervalo)

    m.encerrar()

    # Arquivos de saída
    campos = ["num", "tipo", "dispositivo", "acao", "rtt_ms", "tempo_ms", "leitura_ms"]
    with open(PASTA_RESULTADOS / "medicoes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for n, l in enumerate(linhas, 1):
            w.writerow({"num": n, **l})
    with open(PASTA_RESULTADOS / "ping.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["num", "rtt_ms"])
        for n, p in enumerate(pings, 1):
            w.writerow([n, round(p, 1)])

    md = ["| Núm. medida | Sensor/atuador | Tempo de resposta |", "|---|---|---|"]
    for n, l in enumerate(linhas, 1):
        nome = f"{l['dispositivo']} - {l['acao']}"
        md.append(f"| {n} | {nome} | {l['tempo_ms']:.0f} ms |")
    for tipo in ("Sensor", "Atuador"):
        vals = [l["tempo_ms"] for l in linhas if l["tipo"] == tipo]
        if vals:
            md.append(f"| Média | {tipo} | {statistics.mean(vals):.0f} ms |")
    md.append("")
    md.append(f"RTT médio do ping: {2 * meia_ida:.0f} ms (n = {len(pings)}). "
              f"Broker: {args.broker}:{args.porta}. Data: {time.strftime('%d/%m/%Y %H:%M')}.")
    (PASTA_RESULTADOS / "tabela_tempos.md").write_text("\n".join(md), encoding="utf-8")

    print("\n" + "\n".join(md))
    print(f"\nArquivos salvos em {PASTA_RESULTADOS}")

    try:
        import gerar_graficos
        gerar_graficos.grafico_tempos()
    except Exception as e:  # o gráfico pode ser gerado depois
        print(f"Não foi possível gerar o gráfico agora: {e}")


if __name__ == "__main__":
    main()
