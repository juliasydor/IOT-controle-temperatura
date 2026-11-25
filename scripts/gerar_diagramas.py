"""
Gera os diagramas do artigo na pasta docs/diagramas/:

  esquema_eletronico.png   esquema elétrico do circuito (biblioteca schemdraw)
  arquitetura.png          arquitetura da solução (ESP32, broker MQTT e clientes)
  sequencia_mqtt.png       diagrama de sequência das mensagens MQTT

Uso:
  python gerar_diagramas.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
import schemdraw  # noqa: E402
import schemdraw.elements as elm  # noqa: E402

PASTA = Path(__file__).resolve().parent.parent / "docs" / "diagramas"
PASTA.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans"})


# ---------------------------------------------------------------- esquema elétrico
def esquema_eletronico():
    schemdraw.config(fontsize=11, lw=1.3)
    vermelho, verde, azul = "#c0392b", "#1e8449", "#2457a6"

    def ic(nome_pinos_esq, nome_pinos_dir, centro, rotulo, larg):
        pinos = []
        for lado, nomes in (("left", nome_pinos_esq), ("right", nome_pinos_dir)):
            n = len(nomes)
            for i, (nome, ancora) in enumerate(nomes):  # nomes de cima para baixo
                pinos.append(elm.IcPin(name=nome, side=lado, slot=f"{n - i}/{n}", anchorname=ancora))
        return (elm.Ic(pins=pinos, size=(larg, 4), pinspacing=1.4, edgepadH=0.6)
                .theta(0).at(centro).anchor("center").label(rotulo, "top", fontsize=10, ofst=0.25))

    with schemdraw.Drawing(show=False) as d:
        esp = ic([("VIN (5V)", "VIN"), ("GPIO26", "G26"), ("GND", "GNDL")],
                 [("3V3", "V33"), ("GPIO4", "G4"), ("GND", "GNDR")],
                 (0, 0), "ESP32-DevKitC V4\n(ESP32-WROOM-32)", 4.4)
        dht = ic([("VCC (1)", "VCC"), ("DATA (2)", "DATA"), ("GND (4)", "GND")], [],
                 (9.0, 0), "DHT22 (AM2302)\npino 3: NC", 2.8)
        rel = ic([("COM", "COM"), ("NA", "NA"), ("NF", "NF")],
                 [("VCC", "VCC"), ("IN", "IN"), ("GND", "GND")],
                 (-9.0, 0), "Módulo relé 1 canal\nSRD-05VDC-SL-C", 3.2)

        # ESP32 <-> DHT22
        elm.Line().at(esp.V33).to(dht.VCC).color(vermelho).label("3,3 V", loc="top")
        elm.Line().at(esp.G4).to(dht.DATA).color(verde)
        elm.Line().at(esp.GNDR).to(dht.GND)
        xr = (esp.V33[0] + dht.VCC[0]) / 2
        elm.Dot().at((xr, esp.V33[1]))
        elm.Resistor().at((xr, esp.V33[1])).to((xr, esp.G4[1])).label("R1 10 kΩ\n(pull-up)", loc="bottom", ofst=0.15)
        elm.Dot().at((xr, esp.G4[1]))

        # ESP32 <-> relé
        elm.Line().at(rel.VCC).to(esp.VIN).color(vermelho).label("5 V", loc="top")
        elm.Line().at(rel.IN).to(esp.G26).color(azul).label("sinal", loc="top")
        elm.Line().at(rel.GND).to(esp.GNDL)

        # terra comum
        xg = (rel.GND[0] + esp.GNDL[0]) / 2
        elm.Dot().at((xg, esp.GNDL[1]))
        elm.Line().at((xg, esp.GNDL[1])).to((xg, esp.GNDL[1] - 1.4))
        elm.Ground()

        # COM do relé ligado ao 5 V
        x5 = (rel.VCC[0] + esp.VIN[0]) / 2 + 1.0
        ytopo = rel.COM[1] + 3.2
        xcom = rel.COM[0] - 1.0
        elm.Dot().at((x5, esp.VIN[1]))
        elm.Line().at(rel.COM).to((xcom, rel.COM[1])).color(vermelho)
        elm.Line().at((xcom, rel.COM[1])).to((xcom, ytopo)).color(vermelho)
        elm.Line().at((xcom, ytopo)).to((x5, ytopo)).color(vermelho).label("COM ligado ao +5 V", loc="top")
        elm.Line().at((x5, ytopo)).to((x5, esp.VIN[1])).color(vermelho)

        # NA -> R2 -> LED -> GND (carga que representa o ventilador)
        xna = rel.NA[0] - 2.2
        elm.Line().at(rel.NA).to((xna, rel.NA[1]))
        elm.Resistor().at((xna, rel.NA[1])).down(2.0).label("R2\n220 Ω", loc="bottom", ofst=0.15)
        elm.LED().down(2.0).label("LED\n(ventilador)", loc="bottom", ofst=0.15)
        elm.Ground()

        d.save(str(PASTA / "esquema_eletronico.png"), dpi=220)
    print("esquema_eletronico.png")


# ---------------------------------------------------------------- utilidades de desenho
def caixa(ax, x, y, w, h, titulo, texto="", cor="#e8f0fa", borda="#2a6fb0"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15",
                                fc=cor, ec=borda, lw=1.5))
    ax.text(x + w / 2, y + h - 0.32, titulo, ha="center", va="top", fontsize=11, weight="bold")
    if texto:
        ax.text(x + w / 2, y + h - 0.8, texto, ha="center", va="top", fontsize=8.5, linespacing=1.4)


def seta(ax, x1, y1, x2, y2, texto="", cor="#333", ofst=(0, 0.15), fs=8.5, ha="center"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=cor, lw=1.4, shrinkA=0, shrinkB=0))
    if texto:
        ax.text((x1 + x2) / 2 + ofst[0], (y1 + y2) / 2 + ofst[1], texto, ha=ha, va="bottom",
                fontsize=fs, color=cor)


# ---------------------------------------------------------------- arquitetura
def arquitetura():
    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=200)
    ax.set_xlim(0, 22)
    ax.set_ylim(0, 11)
    ax.axis("off")

    # camada de percepção / dispositivo
    caixa(ax, 0.3, 6.6, 3.2, 2.2, "DHT22", "Sensor de temperatura\ne umidade\n(protocolo de 1 fio)",
          "#fdf2e9", "#d0603a")
    caixa(ax, 0.3, 2.4, 3.2, 2.2, "Módulo relé", "Atuador: liga o\nventilador (LED no\nsimulador)",
          "#fdf2e9", "#d0603a")
    caixa(ax, 5.0, 3.0, 4.6, 5.4, "ESP32", "Leitura do sensor a cada 5 s\nControle com histerese\n"
          "(liga ≥ limite,\ndesliga ≤ limite − 1 °C)\nModo AUTO / MANUAL\nCliente MQTT\n(PubSubClient)\n"
          "Wi-Fi 802.11 b/g/n")
    seta(ax, 3.5, 7.7, 5.0, 7.7, "GPIO 4", ofst=(0, 0.1))
    seta(ax, 5.0, 3.5, 3.5, 3.5, "GPIO 26", ofst=(0, 0.1))

    # rede
    caixa(ax, 11.0, 4.0, 3.2, 3.4, "Internet", "Wi-Fi (Wokwi-GUEST)\nTCP/IP\nporta 1883 (MQTT)\n"
          "porta 8884 (MQTT\nsobre WebSocket TLS)", "#f4f6f7", "#7f8c8d")
    seta(ax, 9.6, 6.2, 11.0, 6.2, "publica", cor="#1e8449", ofst=(0, 0.1))
    seta(ax, 11.0, 5.0, 9.6, 5.0, "assina", cor="#2457a6", ofst=(0, 0.1))

    caixa(ax, 15.4, 4.0, 3.0, 3.4, "Broker MQTT", "HiveMQ público\nbroker.hivemq.com\n\nencaminha cada\nmensagem aos\nassinantes",
          "#eafaf1", "#1e8449")
    seta(ax, 14.2, 5.7, 15.4, 5.7)

    # clientes
    caixa(ax, 19.3, 8.0, 2.6, 2.6, "MQTT\nExplorer", "\n\nvisualiza e\nenvia comandos", "#e8f0fa")
    caixa(ax, 19.3, 4.3, 2.6, 2.8, "Painel web", "\nHTML + MQTT.js\nWebSocket\ngráfico e\nbotões", "#e8f0fa")
    caixa(ax, 19.3, 0.4, 2.6, 3.0, "Scripts\nPython", "\n\npaho-mqtt\nmonitor, comandos\ne medição de\ntempos", "#e8f0fa")
    for y in (9.3, 5.7, 1.9):
        ax.annotate("", xy=(19.3, y), xytext=(18.4, 5.7),
                    arrowprops=dict(arrowstyle="<|-|>", color="#333", lw=1.2))

    ax.text(1.9, 10.3, "Dispositivo (percepção e atuação)", fontsize=10, ha="left", style="italic")
    ax.text(12.6, 10.3, "Rede e serviço MQTT", fontsize=10, ha="center", style="italic")
    ax.text(20.6, 10.85, "Aplicação", fontsize=10, ha="center", style="italic")
    fig.tight_layout()
    fig.savefig(PASTA / "arquitetura.png", bbox_inches="tight")
    plt.close(fig)
    print("arquitetura.png")


# ---------------------------------------------------------------- sequência MQTT
def sequencia_mqtt():
    atores = ["DHT22", "ESP32", "Relé", "Broker MQTT\n(HiveMQ)", "Cliente\n(MQTT Explorer /\nPainel web)"]
    xs = [1, 4, 7, 10.5, 14.5]
    fig, ax = plt.subplots(figsize=(11, 8.8), dpi=200)
    ax.set_xlim(0, 16)
    ax.set_ylim(1.5, 19.7)
    ax.axis("off")
    for x, a in zip(xs, atores):
        ax.add_patch(FancyBboxPatch((x - 1.4, 18.0), 2.8, 1.5, boxstyle="round,pad=0.02",
                                    fc="#e8f0fa", ec="#2a6fb0", lw=1.4))
        ax.text(x, 18.75, a, ha="center", va="center", fontsize=8.5, weight="bold")
        ax.plot([x, x], [1.7, 18.0], color="#999", lw=1, ls="--")

    D, E, R, B, C = xs
    y = 17.4
    passos = [
        ("nota", "1. Conexão"),
        (E, B, "CONNECT (Last Will: sistema/status = offline, retida)", "#333"),
        (B, E, "CONNACK", "#333"),
        (E, B, "PUBLISH sistema/status = online (retida)", "#1e8449"),
        (E, B, "SUBSCRIBE ventilador/comando, clima/limite, diagnostico/ping, diagnostico/medir", "#2457a6"),
        ("nota", "2. Ciclo de leitura (a cada 5 s)"),
        (E, D, "pulso de início", "#333"),
        (D, E, "40 bits: umidade, temperatura, verificação", "#333"),
        (E, R, "GPIO 26 = ALTO se T ≥ limite (modo AUTO)", "#d0603a"),
        (E, B, "PUBLISH clima/temperatura, clima/umidade, ventilador/estado", "#1e8449"),
        (B, C, "encaminha às assinaturas mackenzie/jsydor/#", "#1e8449"),
        ("nota", "3. Comando remoto"),
        (C, B, "PUBLISH ventilador/comando = LIGAR", "#2457a6"),
        (B, E, "encaminha o comando (callback tratarMensagem)", "#2457a6"),
        (E, R, "GPIO 26 = ALTO (modo MANUAL)", "#d0603a"),
        (E, B, "PUBLISH ventilador/estado = LIGADO (confirmação)", "#1e8449"),
        (B, C, "encaminha a confirmação", "#1e8449"),
        ("nota", "4. Queda da conexão"),
        (B, C, "broker publica a Last Will: sistema/status = offline", "#c0392b"),
    ]
    for p in passos:
        if p[0] == "nota":
            y -= 0.25
            ax.add_patch(FancyBboxPatch((0.2, y - 0.3), 15.6, 0.55, boxstyle="round,pad=0.02",
                                        fc="#fbfbfb", ec="#ccc", lw=0.8))
            ax.text(0.4, y - 0.02, p[1], fontsize=9.5, weight="bold", va="center")
            y -= 0.75
            continue
        x1, x2, texto, cor = p
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="-|>", color=cor, lw=1.3))
        meio = (x1 + x2) / 2
        ax.text(meio, y + 0.08, texto, ha="center", va="bottom", fontsize=7.8, color=cor,
                bbox=dict(fc="white", ec="none", pad=0.6), zorder=5)
        y -= 0.78
    fig.savefig(PASTA / "sequencia_mqtt.png", bbox_inches="tight")
    plt.close(fig)
    print("sequencia_mqtt.png")


if __name__ == "__main__":
    esquema_eletronico()
    arquitetura()
    sequencia_mqtt()
