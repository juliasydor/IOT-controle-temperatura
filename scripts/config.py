"""Configuração comum aos scripts: broker e tópicos MQTT (iguais aos do firmware)."""

BROKER = "broker.hivemq.com"
PORTA = 1883
PREFIXO = "mackenzie/jsydor"


def topicos(prefixo: str = PREFIXO) -> dict:
    return {
        "temperatura": f"{prefixo}/clima/temperatura",
        "umidade": f"{prefixo}/clima/umidade",
        "limite_atual": f"{prefixo}/clima/limite_atual",
        "limite": f"{prefixo}/clima/limite",
        "estado": f"{prefixo}/ventilador/estado",
        "modo": f"{prefixo}/ventilador/modo",
        "comando": f"{prefixo}/ventilador/comando",
        "status": f"{prefixo}/sistema/status",
        "ping": f"{prefixo}/diagnostico/ping",
        "pong": f"{prefixo}/diagnostico/pong",
        "medir": f"{prefixo}/diagnostico/medir",
        "leitura": f"{prefixo}/diagnostico/leitura",
    }
