#include <ESP8266mDNS.h>
#include <ESP8266WiFi.h>
#include <WebSocketsServer.h>
#include <ESP8266WebServer.h>
#include <DNSServer.h>
#include <ESP_EEPROM.h>

struct WiFiCredentials {
  char ssid[32];
  char password[64];
};

WiFiCredentials creds;

#define RELAY1 14
#define RELAY2 12
#define RELAY3 4
#define RELAY4 5

#define COLD_BOOT_MARKER_ADDR 0
#define RELAY1_STATE_ADDR     1
#define RELAY2_STATE_ADDR     2
#define RELAY3_STATE_ADDR     3
#define RELAY4_STATE_ADDR     4
#define WIFI_CREDS_ADDR       10
#define NAMES_ADDR 120

#define ON 1
#define OFF 0

const byte DNS_PORT = 53;
DNSServer dnsServer;
ESP8266WebServer server(80);
WebSocketsServer webSocket = WebSocketsServer(81);

bool wifiConnected = false;
bool apModeActive = false;
bool webSocketStarted = false;

// HTML page markup served during AP mode
const char CONFIG_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html>
<head>
  <meta name='viewport' content='width=device-width, initial-scale=1.0'>
  <title>ESP Relay Config</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f9; color: #333; }
    .container { max-width: 400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
    h2 { margin-top: 0; color: #007bff; text-align: center; }
    label { font-weight: bold; display: block; margin: 10px 0 5px; }
    input[type='text'], input[type='password'] { width: 100%; padding: 10px; margin-bottom: 15px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
    input[type='submit'] { width: 100%; background-color: #007bff; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
    input[type='submit']:hover { background-color: #0056b3; }
  </style>
</head>
<body>
  <div class='container'>
    <h2>Wi-Fi Configuration</h2>
    <form action='/save' method='POST'>
      <label for='ssid'>Network Name (SSID):</label>
      <input type='text' id='ssid' name='ssid' maxlength='31' required>
      <label for='pass'>Password:</label>
      <input type='password' id='pass' name='pass' maxlength='63'>
      <input type='submit' value='Save & Connect'>
    </form>
  </div>
</body>
</html>
)rawliteral";

struct RelayNames {
  char names[4][24]; // 4 names, max 23 characters each + null terminator
};
RelayNames boardNames;

void setup() {
  Serial.begin(115200);
  EEPROM.begin(512);
  delay(100);

  relaySetup();

  Serial.println("\n--- ESP STARTED ---");
  WiFiSetup();
}

void loop() {
  if (webSocketStarted && wifiConnected) {
    webSocket.loop();
  }
  
  if (apModeActive) {
    dnsServer.processNextRequest(); // Directs Captive Portal intercept requests
    server.handleClient();
  }

  if (!wifiConnected && !apModeActive) {
    static unsigned long lastReconnectAttempt = 0;
    if (millis() - lastReconnectAttempt > 10000) { 
      lastReconnectAttempt = millis();
      if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        if (!webSocketStarted) {
          webSocket.begin();
          webSocket.onEvent(webSocketEvent);
          webSocketStarted = true;
        }
      }
    }
  }
  MDNS.update();
  checkForSerialCommands();
}

void updateRelayState(int addr, uint8_t state) {
  EEPROM.put(addr, state);
  EEPROM.commit();
}

void webSocketEvent(uint8_t num, WStype_t type, uint8_t * payload, size_t length) {
  if (type == WStype_CONNECTED) {
    Serial.printf("[%u] Connected!\n", num);
     
    // 1. Send the standard SYNC state for the relays
    String stateMsg = "SYNC";
    stateMsg += (digitalRead(RELAY1) == ON) ? ":1_ON" : ":1_OFF";
    stateMsg += (digitalRead(RELAY2) == ON) ? ":2_ON" : ":2_OFF";
    stateMsg += (digitalRead(RELAY3) == ON) ? ":3_ON" : ":3_OFF";
    stateMsg += (digitalRead(RELAY4) == ON) ? ":4_ON" : ":4_OFF";
     
    webSocket.sendTXT(num, stateMsg); 
     
    // 2. Immediately send the custom names to the app
    String nameMsg = "NAMES:" + String(boardNames.names[0]) + "|" + 
                     String(boardNames.names[1]) + "|" + 
                     String(boardNames.names[2]) + "|" + 
                     String(boardNames.names[3]);
    webSocket.sendTXT(num, nameMsg);
  }
  else if (type == WStype_TEXT) {
    String cmd = (char*)payload;
    Serial.printf("[%u] Received: %s\n", num, cmd.c_str());
    
    // --- NEW NAME HANDLING LOGIC ---
    if (cmd.startsWith("SET_NAME:")) {
      // Parses format: SET_NAME:1:Desk Lamp
      int idx = cmd.substring(9, 10).toInt() - 1; 
      String newName = cmd.substring(11);
      
      // Ensure index is valid (0 to 3) before writing to memory
      if (idx >= 0 && idx < 4) {
        newName.toCharArray(boardNames.names[idx], 24);
        boardNames.names[idx][23] = '\0'; // Force safety terminator
        
        EEPROM.put(NAMES_ADDR, boardNames);
        EEPROM.commit();
        
        // Broadcast the new names to every connected app immediately
        String nameMsg = "NAMES:" + String(boardNames.names[0]) + "|" + 
                         String(boardNames.names[1]) + "|" + 
                         String(boardNames.names[2]) + "|" + 
                         String(boardNames.names[3]);
        webSocket.broadcastTXT(nameMsg);
        
        Serial.printf("Saved new name for Relay %d: %s\n", idx + 1, newName.c_str());
      }
    } 
    else if (cmd == "GET_NAMES") {
      // Sends the current names when specifically requested
      String nameMsg = "NAMES:" + String(boardNames.names[0]) + "|" + 
                       String(boardNames.names[1]) + "|" + 
                       String(boardNames.names[2]) + "|" + 
                       String(boardNames.names[3]);
      webSocket.sendTXT(num, nameMsg);
    }
    // --- EXISTING RELAY CONTROL LOGIC ---
    else if (cmd == "1_ON") { digitalWrite(RELAY1, ON); updateRelayState(RELAY1_STATE_ADDR, ON); webSocket.broadcastTXT("1_ON"); }
    else if (cmd == "1_OFF") { digitalWrite(RELAY1, OFF); updateRelayState(RELAY1_STATE_ADDR, OFF); webSocket.broadcastTXT("1_OFF"); }
    else if (cmd == "2_ON") { digitalWrite(RELAY2, ON); updateRelayState(RELAY2_STATE_ADDR, ON); webSocket.broadcastTXT("2_ON"); }
    else if (cmd == "2_OFF") { digitalWrite(RELAY2, OFF); updateRelayState(RELAY2_STATE_ADDR, OFF); webSocket.broadcastTXT("2_OFF"); }
    else if (cmd == "3_ON") { digitalWrite(RELAY3, ON); updateRelayState(RELAY3_STATE_ADDR, ON); webSocket.broadcastTXT("3_ON"); }
    else if (cmd == "3_OFF") { digitalWrite(RELAY3, OFF); updateRelayState(RELAY3_STATE_ADDR, OFF); webSocket.broadcastTXT("3_OFF"); }
    else if (cmd == "4_ON") { digitalWrite(RELAY4, ON); updateRelayState(RELAY4_STATE_ADDR, ON); webSocket.broadcastTXT("4_ON"); }
    else if (cmd == "4_OFF") { digitalWrite(RELAY4, OFF); updateRelayState(RELAY4_STATE_ADDR, OFF); webSocket.broadcastTXT("4_OFF"); }
  }
}

String getHostName() {
  String hostname = "ESP_" + String(ESP.getChipId(), HEX);
  hostname.toUpperCase();
  return hostname;
}

void handleWifiSave() {
  if (server.hasArg("ssid")) {
    String s = server.arg("ssid");
    String p = server.arg("pass");
    
    s.trim();
    p.trim();

    if (s.length() > 0 && s.length() < 32 && p.length() < 64) {
      memset(&creds, 0, sizeof(creds));
      s.toCharArray(creds.ssid, 32);
      p.toCharArray(creds.password, 64);
      creds.ssid[31] = '\0';
      creds.password[63] = '\0';

      EEPROM.put(WIFI_CREDS_ADDR, creds);
      EEPROM.write(COLD_BOOT_MARKER_ADDR, 1); 
      EEPROM.commit();

      server.send(200, "text/html", "<html><body><h2>Credentials Saved!</h2><p>The ESP will now restart and connect to your network.</p></body></html>");
      
      Serial.println("CREDS_RECEIVED_VIA_WEB_REBOOTING");
      delay(1000);
      ESP.restart();
    } else {
      server.send(400, "text/plain", "Error: SSID or Password lengths invalid.");
    }
  } else {
    server.send(400, "text/plain", "Bad Request: SSID missing.");
  }
}

void checkForSerialCommands() {
  if (Serial.available() > 0) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    
    if (cmd == "SETUP") {
      Serial.println("ENTERING_SETUP_MODE");
      
      unsigned long startTimeout = millis();
      while (Serial.available() == 0 && millis() - startTimeout < 5000) { delay(10); }
      String s = Serial.readStringUntil('\n');
      s.trim();
      
      startTimeout = millis();
      while (Serial.available() == 0 && millis() - startTimeout < 5000) { delay(10); }
      String p = Serial.readStringUntil('\n');
      p.trim();

      if (s.length() > 0 && s.length() < 32 && p.length() < 64) {
        memset(&creds, 0, sizeof(creds));
        s.toCharArray(creds.ssid, 32);
        p.toCharArray(creds.password, 64);

        EEPROM.put(WIFI_CREDS_ADDR, creds);
        EEPROM.write(COLD_BOOT_MARKER_ADDR, 1); 
        EEPROM.commit();
        
        Serial.println("CREDS_SAVED_REBOOTING");
        delay(500);
        ESP.restart();
      }
    }
  }
}

bool isColdBoot() {
  return (EEPROM.read(COLD_BOOT_MARKER_ADDR) != 1); 
}

void relaySetup() {
  pinMode(RELAY1, OUTPUT);
  pinMode(RELAY2, OUTPUT);
  pinMode(RELAY3, OUTPUT);
  pinMode(RELAY4, OUTPUT);

  if (isColdBoot()) {
    digitalWrite(RELAY1, OFF); digitalWrite(RELAY2, OFF);
    digitalWrite(RELAY3, OFF); digitalWrite(RELAY4, OFF);
    updateRelayState(RELAY1_STATE_ADDR, OFF); updateRelayState(RELAY2_STATE_ADDR, OFF);
    updateRelayState(RELAY3_STATE_ADDR, OFF); updateRelayState(RELAY4_STATE_ADDR, OFF);

    strcpy(boardNames.names[0], "Relay 1");
    strcpy(boardNames.names[1], "Relay 2");
    strcpy(boardNames.names[2], "Relay 3");
    strcpy(boardNames.names[3], "Relay 4");
    EEPROM.put(NAMES_ADDR, boardNames);
    EEPROM.commit();
  } else {
    uint8_t s1, s2, s3, s4;
    EEPROM.get(RELAY1_STATE_ADDR, s1); EEPROM.get(RELAY2_STATE_ADDR, s2);
    EEPROM.get(RELAY3_STATE_ADDR, s3); EEPROM.get(RELAY4_STATE_ADDR, s4);
    digitalWrite(RELAY1, s1 == ON ? ON : OFF); digitalWrite(RELAY2, s2 == ON ? ON : OFF);
    digitalWrite(RELAY3, s3 == ON ? ON : OFF); digitalWrite(RELAY4, s4 == ON ? ON : OFF);

    EEPROM.get(NAMES_ADDR, boardNames);
  }
}

void startAPMode() {
  apModeActive = true;
  wifiConnected = false;
  WiFi.disconnect();
  
  WiFi.mode(WIFI_AP);
  
  IPAddress apIP(192, 168, 4, 1);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
  WiFi.softAP("ESP_Relay_Config");
  
  dnsServer.start(DNS_PORT, "*", apIP);

  Serial.println("\n--- CAPTIVE PORTAL ACTIVE ---");
  Serial.println("Connect to Wi-Fi: ESP_Relay_Config");

  server.on("/", HTTP_GET, []() {
    server.send_P(200, "text/html", CONFIG_HTML);
  });
  
  server.on("/save", HTTP_POST, handleWifiSave);

  server.onNotFound([]() {
    server.sendHeader("Location", String("http://192.168.4.1/"), true);
    server.send(302, "text/plain", ""); 
  });
  
  server.begin();
  Serial.println("HTTP Config Web Server Started.");

  if (!webSocketStarted) {
    webSocket.begin();
    webSocket.onEvent(webSocketEvent);
    webSocketStarted = true;
  }
}

void WiFiSetup() {
  if (isColdBoot()) {
    startAPMode();
    return;
  }

  EEPROM.get(WIFI_CREDS_ADDR, creds);
  creds.ssid[31] = '\0';
  creds.password[63] = '\0';
  
  if (strlen(creds.ssid) == 0) {
    startAPMode();
    return;
  }

  WiFi.mode(WIFI_STA);
  Serial.printf("Connecting to: %s\n", creds.ssid);
  WiFi.begin(creds.ssid, creds.password);

  int retries = 0;
  while(WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(500);
    Serial.print(".");
    checkForSerialCommands(); 
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    apModeActive = false;
    String hostname = getHostName();
    
    if (MDNS.begin(hostname.c_str())) { 
      MDNS.addService("ws", "tcp", 81);
      MDNS.update();
    }

    WiFi.setSleepMode(WIFI_NONE_SLEEP);
    Serial.print("\nWiFi Connected. IP: ");
    Serial.println(WiFi.localIP());

    if (!webSocketStarted) {
      webSocket.begin();
      webSocket.onEvent(webSocketEvent);
      webSocketStarted = true;
    }
  } else {
    Serial.println("\nWiFi Connection Failed.");
    startAPMode();
  }
}