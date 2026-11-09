// Edge Watch virtual smart home node (Wokwi ESP32): reads a DHT22 and a PIR, drives a smart-light LED.
//
// Two transports, one behaviour:
//  * default (env esp32dev): structured serial lines, relayed to MQTT by `python -m lab.home serial-bridge`
//    through Wokwi's RFC2217 serial server. The ESP32 itself does not speak MQTT here; the bridge publishes for it.
//  * EW_WIFI_MQTT (env esp32dev-wifi): MQTT over Wokwi WiFi to host.wokwi.internal (needs the paid Private IoT Gateway).
//
// Serial protocol, one line each, 115200 baud (mirrored in lab/home.py):
//   device -> host:  "EW1 temperature 22.5" | "EW1 humidity 45.0" | "EW1 motion 1|0" | "EW1 light ON|OFF" | "EW1 status online"
//   host -> device:  "EW1 light ON|OFF"
// MQTT topics: edgewatch/home/{temperature,humidity,motion,light/state,device/status}; commands on edgewatch/home/light/set.
#include <Arduino.h>
#include <DHTesp.h>

static const int PIN_DHT = 15, PIN_PIR = 13, PIN_LIGHT = 26;
static const unsigned long TELEMETRY_MS = 10000;

DHTesp dht;
bool light = false;
int motion = -1;  // unknown until the first read, so the first state is always reported
unsigned long lastTelemetry = 0;

void report(const char *field, const char *value, bool retained);

// Shared by both transports: "ON"/"OFF"/"1"/"0", case-insensitive; anything else is ignored.
void applyLight(const char *text, unsigned int length) {
  char cmd[8] = {0};
  if (length == 0 || length >= sizeof(cmd)) { Serial.println("light: ignored invalid command"); return; }
  for (unsigned int i = 0; i < length; i++) cmd[i] = toupper(text[i]);
  if (!strcmp(cmd, "ON") || !strcmp(cmd, "1")) light = true;
  else if (!strcmp(cmd, "OFF") || !strcmp(cmd, "0")) light = false;
  else { Serial.printf("light: ignored invalid command '%s'\n", cmd); return; }
  digitalWrite(PIN_LIGHT, light ? HIGH : LOW);
  report("light", light ? "ON" : "OFF", true);
}

void readSensors() {
  int m = digitalRead(PIN_PIR);
  if (m != motion) {
    motion = m;
    report("motion", m ? "1" : "0", false);
  }
  if (lastTelemetry && millis() - lastTelemetry < TELEMETRY_MS) return;
  lastTelemetry = millis();
  TempAndHumidity r = dht.getTempAndHumidity();
  if (dht.getStatus() != DHTesp::ERROR_NONE) { Serial.printf("DHT22 read failed: %s\n", dht.getStatusString()); return; }
  char t[12], h[12];
  snprintf(t, sizeof t, "%.1f", r.temperature);
  snprintf(h, sizeof h, "%.1f", r.humidity);
  report("temperature", t, false);
  report("humidity", h, false);
}

#ifdef EW_WIFI_MQTT
// ---- MQTT over Wokwi WiFi (Private IoT Gateway) ---------------------------------------------------------------------------
#include <WiFi.h>
#include <PubSubClient.h>
#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "include/secrets.h is missing: run  python -m lab.home init  from the repository root"
#endif
static const unsigned long RETRY_MS = 5000;
WiFiClient net;
PubSubClient mqtt(net);
unsigned long lastRetry = 0;

void report(const char *field, const char *value, bool retained) {
  char topic[48];
  snprintf(topic, sizeof topic, "edgewatch/home/%s", !strcmp(field, "light") ? "light/state" : !strcmp(field, "status") ? "device/status" : field);
  mqtt.publish(topic, value, retained);
  Serial.printf("%s: %s\n", field, value);
}

void onMessage(char *topic, byte *payload, unsigned int length) {
  if (!strcmp(topic, "edgewatch/home/light/set")) applyLight((const char *)payload, length);
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.print("WiFi: connecting to Wokwi-GUEST");
  WiFi.begin("Wokwi-GUEST", "", 6);  // channel 6 skips the scan
  while (WiFi.status() != WL_CONNECTED) { delay(250); Serial.print('.'); }
  Serial.printf(" connected, IP %s\n", WiFi.localIP().toString().c_str());
}

bool ensureTransport() {
  ensureWifi();
  if (mqtt.connected()) { mqtt.loop(); return true; }
  if (lastRetry && millis() - lastRetry < RETRY_MS) return false;  // bounded reconnect rate
  lastRetry = millis();
  Serial.printf("MQTT: connecting to %s:%d ... ", EW_MQTT_HOST, EW_MQTT_PORT);
  // Last will: the broker marks the device offline if the simulation stops without a goodbye.
  if (!mqtt.connect("wokwi-esp32-home", EW_MQTT_USER, EW_MQTT_PASSWORD, "edgewatch/home/device/status", 1, true, "offline")) {
    Serial.printf("failed, state %d\n", mqtt.state());
    return false;
  }
  Serial.println("connected");
  report("status", "online", true);
  mqtt.subscribe("edgewatch/home/light/set", 1);
  report("light", light ? "ON" : "OFF", true);
  motion = -1;
  lastTelemetry = 0;
  return true;
}

void setupTransport() {
  mqtt.setServer(EW_MQTT_HOST, EW_MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setKeepAlive(30);
}
#else
// ---- Structured serial lines for the RFC2217 bridge (free) -----------------------------------------------------------------
char line[40];
size_t used = 0;

void report(const char *field, const char *value, bool) { Serial.printf("EW1 %s %s\n", field, value); }

bool ensureTransport() {
  // Bounded line buffer; an over-long line is dropped whole instead of being parsed in pieces.
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') { if (used < sizeof(line) - 1) line[used++] = c; else used = sizeof(line); continue; }
    if (used < sizeof(line)) {
      line[used] = 0;
      if (!strncmp(line, "EW1 light ", 10)) applyLight(line + 10, strlen(line + 10));
    }
    used = 0;
  }
  return true;
}

void setupTransport() {
  report("status", "online", false);
  report("light", "OFF", false);
}
#endif

void setup() {
  Serial.begin(115200);
  pinMode(PIN_PIR, INPUT);
  pinMode(PIN_LIGHT, OUTPUT);
  digitalWrite(PIN_LIGHT, LOW);
  dht.setup(PIN_DHT, DHTesp::DHT22);
  Serial.println("Edge Watch virtual smart home starting");
  setupTransport();
}

void loop() {
  if (!ensureTransport()) { delay(100); return; }
  readSensors();
  delay(50);
}
