/*
 * Sistema IoT de Monitoramento e Controle Automático de Temperatura Ambiente
 * com ESP32 e Protocolo MQTT
 * Autora: Julia Sydor - Universidade Presbiteriana Mackenzie
 *
 * Hardware (ver diagram.json):
 *   DHT22  -> DATA no GPIO 4 (pull-up de 10 kOhm para 3V3)
 *   Relé   -> IN no GPIO 26 (LED + resistor de 220 Ohm no contato NA representam o ventilador)
 *
 * Bibliotecas: WiFi (pacote ESP32), PubSubClient, DHT sensor library, Adafruit Unified Sensor
 * Documentação completa dos tópicos e mensagens: docs/mqtt.md
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>

// ---------- Rede e broker ----------
const char* WIFI_SSID     = "Wokwi-GUEST";      // rede do simulador Wokwi (sem senha)
const char* WIFI_PASSWORD = "";
const char* MQTT_BROKER   = "broker.hivemq.com"; // broker público (uso didático)
const int   MQTT_PORT     = 1883;                // MQTT sobre TCP, sem TLS

// ---------- Tópicos MQTT (Tabela 3 do artigo) ----------
// Publicados pelo ESP32
const char* TOPICO_TEMPERATURA = "mackenzie/jsydor/clima/temperatura";
const char* TOPICO_UMIDADE     = "mackenzie/jsydor/clima/umidade";
const char* TOPICO_LIMITE_ATUAL= "mackenzie/jsydor/clima/limite_atual";
const char* TOPICO_ESTADO      = "mackenzie/jsydor/ventilador/estado";
const char* TOPICO_MODO        = "mackenzie/jsydor/ventilador/modo";
const char* TOPICO_STATUS      = "mackenzie/jsydor/sistema/status";     // retido + Last Will
const char* TOPICO_PONG        = "mackenzie/jsydor/diagnostico/pong";
const char* TOPICO_LEITURA_DIAG= "mackenzie/jsydor/diagnostico/leitura";
// Assinados pelo ESP32
const char* TOPICO_COMANDO     = "mackenzie/jsydor/ventilador/comando";
const char* TOPICO_LIMITE      = "mackenzie/jsydor/clima/limite";
const char* TOPICO_PING        = "mackenzie/jsydor/diagnostico/ping";
const char* TOPICO_MEDIR       = "mackenzie/jsydor/diagnostico/medir";

// ---------- Pinos ----------
const int PINO_DHT  = 4;
const int PINO_RELE = 26;

// ---------- Parâmetros de controle ----------
const unsigned long INTERVALO_LEITURA_MS    = 5000;  // DHT22 exige no mínimo 2 s
const unsigned long INTERVALO_RECONEXAO_MS  = 5000;
const float HISTERESE      = 1.0;   // °C abaixo do limite para desligar
const float LIMITE_MINIMO  = 10.0;  // faixa aceita para o limite recebido por MQTT
const float LIMITE_MAXIMO  = 50.0;

DHT dht(PINO_DHT, DHT22);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

float limite = 28.0;              // limite inicial de temperatura (°C)
bool modoAutomatico = true;       // modo inicial: automático
bool ventiladorLigado = false;
unsigned long ultimaLeitura = 0;
unsigned long ultimaTentativaMqtt = 0;
String idMedicaoPendente = "";    // id recebido em diagnostico/medir, respondido na próxima leitura

// Liga ou desliga o relé; só mexe no pino quando o estado precisa mudar.
void acionarVentilador(bool ligar) {
  if (ligar == ventiladorLigado) return;
  ventiladorLigado = ligar;
  digitalWrite(PINO_RELE, ligar ? HIGH : LOW);
  Serial.printf("[%lu ms] Rele %s\n", millis(), ligar ? "LIGADO" : "DESLIGADO");
}

// Publica estado do ventilador, modo de operação e limite vigente.
void publicarEstado() {
  if (!mqtt.connected()) return;
  mqtt.publish(TOPICO_ESTADO, ventiladorLigado ? "LIGADO" : "DESLIGADO");
  mqtt.publish(TOPICO_MODO, modoAutomatico ? "AUTO" : "MANUAL");
  mqtt.publish(TOPICO_LIMITE_ATUAL, String(limite, 1).c_str());
}

// Callback do PubSubClient: chamado para cada mensagem recebida nos tópicos assinados.
void tratarMensagem(char* topico, byte* payload, unsigned int tamanho) {
  String mensagem;
  for (unsigned int i = 0; i < tamanho; i++) mensagem += (char)payload[i];
  mensagem.trim();

  // Diagnóstico: devolve o mesmo conteúdo imediatamente (medição do tempo de ida e volta).
  if (strcmp(topico, TOPICO_PING) == 0) {
    mqtt.publish(TOPICO_PONG, mensagem.c_str());
    return;
  }

  Serial.printf("[%lu ms] Mensagem em %s: %s\n", millis(), topico, mensagem.c_str());

  if (strcmp(topico, TOPICO_COMANDO) == 0) {
    mensagem.toUpperCase();
    if (mensagem == "LIGAR") {
      modoAutomatico = false;
      acionarVentilador(true);
    } else if (mensagem == "DESLIGAR") {
      modoAutomatico = false;
      acionarVentilador(false);
    } else if (mensagem == "AUTO") {
      modoAutomatico = true;
      ultimaLeitura = 0;  // força nova leitura e decisão imediata
    } else {
      Serial.println("Comando desconhecido, ignorado.");
      return;
    }
    publicarEstado();  // confirmação do comando para o usuário
  } else if (strcmp(topico, TOPICO_LIMITE) == 0) {
    float novoLimite = mensagem.toFloat();
    if (novoLimite >= LIMITE_MINIMO && novoLimite <= LIMITE_MAXIMO) {
      limite = novoLimite;
      Serial.printf("Novo limite: %.1f C\n", limite);
      publicarEstado();
    } else {
      Serial.println("Limite fora da faixa de 10 a 50 C, ignorado.");
    }
  } else if (strcmp(topico, TOPICO_MEDIR) == 0) {
    // Diagnóstico: força uma leitura imediata do sensor e responde com o id recebido.
    idMedicaoPendente = mensagem;
    ultimaLeitura = 0;
  }
}

void conectarWiFi() {
  Serial.print("Conectando ao Wi-Fi");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD, 6);  // canal 6: canal do ponto de acesso do Wokwi
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
  }
  Serial.print(" conectado. IP: ");
  Serial.println(WiFi.localIP());
}

// Tentativa não bloqueante: o controle local continua rodando enquanto o broker estiver fora.
void manterMqtt() {
  if (mqtt.connected()) return;
  if (millis() - ultimaTentativaMqtt < INTERVALO_RECONEXAO_MS) return;
  ultimaTentativaMqtt = millis();

  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    return;
  }
  String clientId = "esp32-jsydor-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  Serial.print("Conectando ao broker MQTT... ");
  // Last Will: se a conexão cair sem aviso, o broker publica "offline" (retido) no tópico de status.
  if (mqtt.connect(clientId.c_str(), TOPICO_STATUS, 0, true, "offline")) {
    Serial.println("conectado.");
    mqtt.publish(TOPICO_STATUS, "online", true);
    mqtt.subscribe(TOPICO_COMANDO);
    mqtt.subscribe(TOPICO_LIMITE);
    mqtt.subscribe(TOPICO_PING);
    mqtt.subscribe(TOPICO_MEDIR);
    publicarEstado();
  } else {
    Serial.printf("falhou (estado %d).\n", mqtt.state());
  }
}

void lerSensorEControlar() {
  unsigned long inicio = millis();
  bool forcar = idMedicaoPendente.length() > 0;  // ignora o cache de 2 s da biblioteca
  float temperatura = dht.readTemperature(false, forcar);
  float umidade = dht.readHumidity();
  if (isnan(temperatura) || isnan(umidade)) {
    Serial.println("Leitura invalida do DHT22, descartada.");
    return;
  }
  Serial.printf("[%lu ms] Temperatura: %.1f C | Umidade: %.1f %% | Limite: %.1f C | Modo: %s\n",
                millis(), temperatura, umidade, limite, modoAutomatico ? "AUTO" : "MANUAL");

  if (modoAutomatico) {
    if (temperatura >= limite) {
      acionarVentilador(true);
    } else if (temperatura <= limite - HISTERESE) {
      acionarVentilador(false);
    }
  }

  if (mqtt.connected()) {
    mqtt.publish(TOPICO_TEMPERATURA, String(temperatura, 1).c_str());
    mqtt.publish(TOPICO_UMIDADE, String(umidade, 1).c_str());
    publicarEstado();
    if (forcar) {
      // Resposta da medição: id, valores e tempo gasto entre o início da leitura e a publicação.
      char json[160];
      snprintf(json, sizeof(json),
               "{\"id\":\"%s\",\"temperatura\":%.1f,\"umidade\":%.1f,\"leitura_ms\":%lu}",
               idMedicaoPendente.c_str(), temperatura, umidade, millis() - inicio);
      mqtt.publish(TOPICO_LEITURA_DIAG, json);
    }
    Serial.printf("[%lu ms] Mensagens publicadas\n", millis());
  }
  idMedicaoPendente = "";
}

void setup() {
  Serial.begin(115200);
  pinMode(PINO_RELE, OUTPUT);
  digitalWrite(PINO_RELE, LOW);  // ventilador começa desligado
  dht.begin();
  conectarWiFi();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(tratarMensagem);
}

void loop() {
  manterMqtt();
  mqtt.loop();
  if (ultimaLeitura == 0 || millis() - ultimaLeitura >= INTERVALO_LEITURA_MS) {
    ultimaLeitura = millis();
    lerSensorEControlar();
  }
}
