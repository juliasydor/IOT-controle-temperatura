# Resultados

Arquivos gerados pelos scripts durante os testes com a simulação no Wokwi:

| Arquivo | Gerado por | Conteúdo |
|---|---|---|
| `medicoes.csv` | `scripts/medir_tempos.py` | cada medição de tempo de resposta (sensor e atuador) |
| `ping.csv` | `scripts/medir_tempos.py` | tempos de ida e volta do ping |
| `tabela_tempos.md` | `scripts/medir_tempos.py` | tabela do artigo, com as médias |
| `grafico_tempos.png` | `scripts/gerar_graficos.py` | gráfico dos tempos de resposta |
| `log_mqtt.csv` | `scripts/monitor_mqtt.py` | todas as mensagens MQTT do teste de funcionamento |
| `grafico_leituras.png` | `scripts/gerar_graficos.py` | temperatura, limite e estado do ventilador ao longo do tempo |
