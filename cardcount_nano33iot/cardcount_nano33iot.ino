/**************************************************************************
 Class: ECE508 Fall 2025
 Team 8
 Date: 12/15/2025

 Final Project
 Description:
 Issues: No issues
 **************************************************************************/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFiNINA.h>
#include <WiFiSSLClient.h>
#include <Arduino_JSON.h>
#include <ArduinoMqttClient.h>

#include "my_library.h"

// Internet Configuration
//*************************************************************
const char teamNumber[11] = "Team8";
const char* wifi_ssid = "GuestZ";                   // REPLACE
const char* wifi_pass = "rooster65";                // REPLACE

const char webhookHost[] = "discord.com";
const int webhookPort = 443;
const char webhookPath[] = "/api/webhooks/1434709618071703612/7Amx_ltzl0QsI4aSBa1_XJqNyuelmp4YTuAcucVVK9jL5yPut61slkljkB7F3-Aqn9An";
//*************************************************************

// MQTT Configuration
//*************************************************************
const char mqttBroker[] = "broker.hivemq.com";
const int mqttPort = 1883;
const char subTopic[] = "arduino/blackjack_table1";
//*************************************************************

WiFiSSLClient client;

int statusWiFi = WL_IDLE_STATUS;

#define I2C_ADDRESS 0x3C
#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels
#define OLED_RESET    -1 // Reset pin # (or -1 if sharing Arduino reset pin)

// Initialize the Adafruit OLED display driver
Adafruit_SSD1306 myOled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

WiFiClient wifiClient;
MqttClient mqttClient(wifiClient); // Instantiate the client

long currMillis, prevMillis;
char tmpBuffer[64];
String oledline[9];

JSONVar sensorObj;
String stringJson;



// MQTT Message
void onMqttMessage(int messageSize) {

  char msg[messageSize + 1];
  int i = 0;
  for (i = 0; i < messageSize; i++) {
    msg[i] = (char)mqttClient.read();
  }
  msg[i] = '\0'; 

  String msgString = String(msg);
  Serial.println(msgString);

  oledline[5] = "Table: " + msgString;
  displayTextOLED(oledline);
}


void setup() {
  //Initialize serial:
  Serial.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT);
  // --- pinMode for SW1_PIN Removed ---

  Wire.begin();

  // NEW: Initialize the Adafruit OLED
  if (!myOled.begin(SSD1306_SWITCHCAPVCC, I2C_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for (;;); // Don't proceed, loop forever
  }

  // Clear the buffer
  myOled.clearDisplay();
  myOled.display(); // Show initial blank screen

  myOled.setTextSize(1);
  myOled.setTextColor(SSD1306_WHITE);
  myOled.setFont(); // Use default Adafruit font

  // Row 1
  oledline[1] = String(teamNumber) + " ECE508";

  // Initialize all lines
  int jj; for (jj = 2; jj <= 8; jj++) {
    oledline[jj] = "";
  }
  
  displayTextOLED(oledline);

  // check for the presence of the shield:
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("WiFi shield not present");
    // don't continue:
    while (true);
  }

  // attempt to connect to Wifi network:
  while ( statusWiFi != WL_CONNECTED) {
    Serial.println("Attempting to connect to SSID: " + String(wifi_ssid));
    statusWiFi = WiFi.begin(wifi_ssid, wifi_pass);
  }
  Serial.println("Connected to WiFi");

  // --- MQTT Setup (NEW) ---
  Serial.println("Setting up MQTT...");
  // Set the message callback function
  mqttClient.onMessage(onMqttMessage);
  
  // Connect to the MQTT broker
  Serial.println("Connecting to MQTT broker...");
  while (!mqttClient.connect(mqttBroker, mqttPort)) {
    Serial.print("MQTT connection failed! Error code = ");
    Serial.println(mqttClient.connectError());
    Serial.println("Retrying in 5 seconds...");
    delay(5000);
  }
  Serial.println("Connected to MQTT broker!");

  Serial.print("Subscribing to topic: ");
  Serial.println(subTopic);
  if (!mqttClient.subscribe(subTopic)) {
     Serial.println("Subscription failed!");
  } else {
     Serial.println("Subscribed!");
  }

  
  
  // Send Discord connection notification
  long color;
  String content;
  String message;


  color = 2483968; // Green
  content = ""; // Ping Users or Roles
  message = "Connected to Discord Server";

  sendDiscordNotification(buildJsonPayload(message, color, content));
}




void loop() {

  // MQTT polling
  mqttClient.poll();

  currMillis = millis();
  if (currMillis - prevMillis > 1000) {
    prevMillis = currMillis;
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));

    // Row 2: WiFi RSSI and IP address
    getWiFiRSSI(tmpBuffer);
    oledline[2] = String(tmpBuffer);

    // Row 3: SSID
    oledline[3] = "SSID: " + String(WiFi.SSID());


    // Row 7: UTC yyyy-mm-dd hh:mm:ss
    unsigned long epoch = WiFi.getTime();
    convCurrentTime(epoch, tmpBuffer);
    oledline[7] = String(tmpBuffer);

    // Row 8: Uptime dd hh:mm:ss
    convDDHHMMSS(millis() / 1000, tmpBuffer);
    oledline[8] = "Uptime: " + String(tmpBuffer);

    displayTextOLED(oledline);
  }
}

String buildJsonPayload(const String& message, long color, const String& content) {
  return "{"
         "\"content\":\"" + content + "\","
         "\"embeds\":[{"
         "\"description\":\"" + message + "\","
         "\"color\":" + String(color) + ","
         "\"author\":{"
         "\"name\":\"Player1 (Arduino Nano 33 IoT)\","
         "\"icon_url\":\"https://media.discordapp.net/attachments/1435025106564022465/1436926911988105368/zC60TAAAAAZJREFUAwBJUcPv7WJDOgAAAABJRU5ErkJggg.png?ex=69120ab8&is=6910b938&hm=55dfaa1e127e035e815e00293841f1249d3954615cb62c400133f0f4d0860d06&=&format=webp&quality=lossless\""
         "}"
         "}],"
         "\"username\":\"Le Chiffre\","
         "\"allowed_mentions\":{\"parse\":[\"roles\"]},"
         "\"attachments\":[]"
         "}";
}

void sendDiscordNotification(String jsonPayload) {
  Serial.println("Sending Discord notification...");

  if (client.connect(webhookHost, webhookPort)) {
    client.println("POST " + String(webhookPath) + " HTTP/1.1");
    client.println("Host: " + String(webhookHost));
    client.println("Content-Type: application/json");
    client.println("Content-Length: " + String(jsonPayload.length()));
    client.println("Connection: close");
    client.println();
    client.println(jsonPayload); // Send the payload

    delay(250);

    while (client.available()) {
      String line = client.readStringUntil('\r');
      Serial.print(line);
    }

    client.stop();
    Serial.println("Discord notification sent!");
  } else {
    Serial.println("Failed to connect to Discord webhook");
  }
}

void displayTextOLED(String oledline[]) {
  myOled.clearDisplay();
  myOled.setTextSize(1);
  myOled.setTextColor(SSD1306_WHITE);
  myOled.setCursor(0, 0);
  myOled.print(oledline[1]);

  // Draw pixel art card suits
  int x = myOled.getCursorX() + 6;
  int y = myOled.getCursorY();

  myOled.drawBitmap(x, y, club_bitmap, 8, 8, SSD1306_WHITE);
  x += 12;
  myOled.drawBitmap(x, y, diamond_bitmap, 8, 8, SSD1306_WHITE);
  x += 12;
  myOled.drawBitmap(x, y, heart_bitmap, 8, 8, SSD1306_WHITE);
  x += 12;
  myOled.drawBitmap(x, y, spade_bitmap, 8, 8, SSD1306_WHITE);

  myOled.println();
  for (int jj = 2; jj <= 8; jj++) myOled.println(oledline[jj]);
  myOled.display();
}