"""Conexão com o broker MQTT, usada por todos os scripts."""

import socket
import threading

ESPERA_S = 30


def conectar(cliente, broker, porta, keepalive=30):
    """
    Conecta, inicia a thread de rede e só retorna depois que o broker aceita a conexão (CONNACK).

    - Publicar ou assinar antes do CONNACK faz o broker público descartar mensagens.
    - O endereço é resolvido em IPv4: em redes sem IPv6, a tentativa por IPv6 atrasa a conexão em segundos.
    """
    conectado = threading.Event()
    on_connect_do_script = cliente.on_connect

    def on_connect(c, dados, flags, codigo, props):
        if on_connect_do_script:
            on_connect_do_script(c, dados, flags, codigo, props)
        if not codigo.is_failure:
            conectado.set()

    cliente.on_connect = on_connect
    print(f"Conectando a {broker}:{porta}...", flush=True)
    try:
        ip = socket.getaddrinfo(broker, porta, socket.AF_INET, socket.SOCK_STREAM)[0][4][0]
        cliente.connect(ip, porta, keepalive=keepalive)
    except OSError as erro:
        raise SystemExit(f"ERRO: não foi possível conectar a {broker}:{porta} ({erro}). Verifique a Internet.")
    cliente.loop_start()
    if not conectado.wait(ESPERA_S):
        cliente.loop_stop()
        raise SystemExit(f"ERRO: {broker}:{porta} não respondeu em {ESPERA_S} s. Tente de novo.")
