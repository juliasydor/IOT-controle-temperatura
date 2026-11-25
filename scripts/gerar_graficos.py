"""
Gera os gráficos dos Resultados a partir dos arquivos da pasta resultados/.

  grafico_tempos.png     tempos de resposta de cada medição (medicoes.csv, de medir_tempos.py)
  grafico_leituras.png   temperatura, limite e estado do ventilador ao longo do tempo
                         (log_mqtt.csv, de monitor_mqtt.py)

Uso:
  python gerar_graficos.py
"""

import csv
import statistics
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent / "resultados"
COR_SENSOR = "#2a6fb0"
COR_ATUADOR = "#d0603a"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False})


def grafico_tempos():
    arq = PASTA / "medicoes.csv"
    if not arq.exists():
        print(f"{arq} não encontrado: rode medir_tempos.py antes.")
        return
    with open(arq, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))

    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
    rotulos, valores, cores = [], [], []
    for l in linhas:
        sensor = l["tipo"] == "Sensor"
        rotulos.append(f"{l['num']}\n{'DHT22' if sensor else l['acao'].capitalize()}")
        valores.append(float(l["tempo_ms"]))
        cores.append(COR_SENSOR if sensor else COR_ATUADOR)
    barras = ax.bar(range(len(valores)), valores, color=cores, width=0.65)
    for b, v in zip(barras, valores):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)

    for tipo, cor in (("Sensor", COR_SENSOR), ("Atuador", COR_ATUADOR)):
        idx = [i for i, l in enumerate(linhas) if l["tipo"] == tipo]
        if idx:
            media = statistics.mean(valores[i] for i in idx)
            ax.hlines(media, min(idx) - 0.4, max(idx) + 0.4, colors=cor, linestyles="--", linewidth=1.2)
            if tipo == "Sensor":  # últimas barras: rótulo à direita
                ax.text(max(idx) + 0.45, media, f"média\n{media:.0f} ms", color=cor, va="center", fontsize=8)
            else:  # primeiras barras: rótulo acima da linha, à esquerda
                ax.text(min(idx) - 0.4, media + 4, f"média {media:.0f} ms", color=cor, va="bottom", fontsize=8)

    ax.set_xticks(range(len(valores)), rotulos, fontsize=8)
    ax.set_ylabel("Tempo de resposta (ms)")
    ax.set_xlabel("Número da medida")
    ax.set_title("Tempo de resposta via MQTT: sensor (azul) e atuador (laranja)", fontsize=10)
    ax.set_xlim(-0.6, len(valores) + 0.6)
    fig.tight_layout()
    fig.savefig(PASTA / "grafico_tempos.png")
    plt.close(fig)
    print(f"Gráfico salvo em {PASTA / 'grafico_tempos.png'}")


def grafico_leituras():
    arq = PASTA / "log_mqtt.csv"
    if not arq.exists():
        print(f"{arq} não encontrado: rode monitor_mqtt.py durante o teste.")
        return
    temp, umid, estado, limite = [], [], [], []
    with open(arq, encoding="utf-8") as f:
        for l in csv.DictReader(f):
            t = datetime.fromisoformat(l["data_hora"])
            topico, msg = l["topico"], l["mensagem"]
            try:
                if topico.endswith("/clima/temperatura"):
                    temp.append((t, float(msg)))
                elif topico.endswith("/clima/umidade"):
                    umid.append((t, float(msg)))
                elif topico.endswith("/clima/limite_atual"):
                    limite.append((t, float(msg)))
                elif topico.endswith("/ventilador/estado"):
                    estado.append((t, 1 if msg == "LIGADO" else 0))
            except ValueError:
                continue
    if not temp:
        print("Nenhuma leitura de temperatura no log.")
        return

    t0 = temp[0][0]
    seg = lambda serie: [(p[0] - t0).total_seconds() for p in serie]  # noqa: E731

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 5), dpi=200, sharex=True,
                                   gridspec_kw={"height_ratios": [3, 1]})
    ax1.plot(seg(temp), [p[1] for p in temp], color=COR_ATUADOR, marker="o", ms=3, label="Temperatura (°C)")
    if limite:
        ax1.step(seg(limite) + [seg(temp)[-1]], [p[1] for p in limite] + [limite[-1][1]],
                 where="post", color="gray", linestyle="--", label="Limite (°C)")
        ax1.step(seg(limite) + [seg(temp)[-1]], [p[1] - 1 for p in limite] + [limite[-1][1] - 1],
                 where="post", color="gray", linestyle=":", label="Limite - 1 °C (histerese)")
    ax1.set_ylabel("Temperatura (°C)")
    ax1.legend(loc="best", fontsize=8, frameon=False)
    if umid:
        axu = ax1.twinx()
        axu.plot(seg(umid), [p[1] for p in umid], color=COR_SENSOR, alpha=0.5, linewidth=1)
        axu.set_ylabel("Umidade (%)", color=COR_SENSOR)
        axu.spines["right"].set_visible(True)
    if estado:
        ax2.step(seg(estado) + [seg(temp)[-1]], [p[1] for p in estado] + [estado[-1][1]],
                 where="post", color="#3a8a4a")
    ax2.set_yticks([0, 1], ["Desligado", "Ligado"])
    ax2.set_ylim(-0.2, 1.2)
    ax2.set_ylabel("Ventilador")
    ax2.set_xlabel("Tempo desde a primeira leitura (s)")
    ax1.set_title("Leituras publicadas no broker MQTT e estado do ventilador", fontsize=10)
    fig.tight_layout()
    fig.savefig(PASTA / "grafico_leituras.png")
    plt.close(fig)
    print(f"Gráfico salvo em {PASTA / 'grafico_leituras.png'}")


if __name__ == "__main__":
    grafico_tempos()
    grafico_leituras()
