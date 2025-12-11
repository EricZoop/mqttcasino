/**************************************************************************
 Class: ECE508 Fall 2025
 Team: 08
 Date: 12/15/2025

 Final Project
 Description: Arduino Nano 33 IoT subscribes via MQTT to a Blackjack table 
  reads incoming cards applying user's chosen algorithim via switch, 
  sends live Discord API message updates and vibration haptic feedback. 
  Publishes heartbeat packet containing strategy, running & true count, 
  latest card, GPS (lat,lon,alt), signal strength (dBm), and uptime.

  Go to MQTT Casino http://157.151.158.181:5000/ to play
  
  GitHub https://github.com/EricZoop/mqttcasino
  Demo https://www.youtube.com/watch?v=y2aZh6rLSks

 Issues: No issues
  **************************************************************************/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <WiFiNINA.h>
#include <WiFiSSLClient.h>
#include <Arduino_JSON.h>
#include <ArduinoMqttClient.h>
#include <TinyGPSPlus.h>

#include "my_library.h"
#include "counting_strategies.h"
#include "heartbeat.h"

// Internet Configuration
const char* wifi_ssid = "GuestZ";     // REPLACE
const char* wifi_pass = "rooster65";  // REPLACE
//*************************************************************

// MQTT Configuration
const char mqttBroker[] = "public.cloud.shiftr.io";
const int mqttPort = 1883;
const char mqttUsername[] = "public";
const char mqttPassword[] = "public";

const char subTopic[] = "gmu/ece508/team08/blkjck_table1";
const char pubTopicHeartbeat[] = "gmu/ece508/team08/player1";
//*************************************************************

// Discord API Configuration
const char webhookHost[] = "discord.com";
const int webhookPort = 443;
const char webhookPath[] = "/api/webhooks/1442641244252803223/lTG5afLzq5f_i0Qw6wy_1lhYNjQlci6zncikj7vuZF80o0du6d35ITz5qeOckVECoLb5";
//*************************************************************




// Configured for ECE508 breakout board
TinyGPSPlus gps;          // GPS RX-TX pins
WiFiSSLClient client;

const int vibOutPin = 5;  // Vibrator actuator
#define SW1_PIN 10        // Switch 

int statusWiFi = WL_IDLE_STATUS;
#define I2C_ADDRESS 0x3C
#define SCREEN_WIDTH 128  // OLED display width, in pixels
#define SCREEN_HEIGHT 64  // OLED display height, in pixels
#define OLED_RESET -1     // Reset pin # (or -1 if sharing Arduino reset pin)

// Initialize the Adafruit OLED display driver
Adafruit_SSD1306 myOled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

WiFiClient wifiClient;
MqttClient mqttClient(wifiClient);

long currMillis, prevMillis;
char tmpBuffer[64];
String oledline[9];

// heartbeat.h
unsigned long lastHeartbeatTime = 0;
const unsigned long heartbeatInterval = 3000;

JSONVar sensorObj;
String stringJson;



// Card Counting state 
double runningCount = 0.0;  // MODIFIED: Changed from int to double to support Halves fractions
double trueCount = 0.0;
const int totalDecks = 6;
const int totalCards = totalDecks * 52;  // 312

String lastCard = "None";  

int cardsDealt = 0;

// Flags to ensure one-time alerts
bool hotAlertSent = false;
bool coldAlertSent = true; // disarmed

// Card counting strategy
CountingStrategy currentStrategy = HILO;
bool lastSwitchState = HIGH; // Default to Hi-Lo

// VIBRATION CONFIG
void vibrate(int duration) {

  oledline[7] = "       VIBRATING!";
  displayTextOLED(oledline);

  digitalWrite(vibOutPin, HIGH);
  delay(duration);
  digitalWrite(vibOutPin, LOW);

  oledline[7] = "";
  displayTextOLED(oledline);
}

// Count is Hot!
void vibrateHot() {
  vibrate(300); 
  delay(150);
  vibrate(300);
  delay(150);
  vibrate(300); 
}

// Count is Reset
void vibrateReset() {
  vibrate(3000); // Long 3-second hold
}

// Count cooled down
void vibrateCold() {
  vibrate(500);
}

void checkStrategySwitch() {
  bool currentSwitchState = digitalRead(SW1_PIN); 
  
  // Detect button press (LOW = pressed)
  if (currentSwitchState == LOW && lastSwitchState == HIGH) {
    delay(50); // Debounce
    
    // Cycle strategy (Hi-Lo -> Omega II -> Halves -> Hi-Lo)
    if (currentStrategy == HILO) {
      currentStrategy = OMEGA_II;
    } else if (currentStrategy == OMEGA_II) { 
      currentStrategy = HALVES;
    } else { 
      currentStrategy = HILO;
    }

    // Reset counts when changing strategy
    runningCount = 0.0;
    trueCount = 0.0;
    cardsDealt = 0;
    hotAlertSent = false;
    coldAlertSent = true;

    // Update
    oledline[3] = "Strategy: " + getStrategyName(currentStrategy);
    oledline[4] = "Last Card: AKQJT98765";
    oledline[5] = "Run Count: " + String(runningCount, 2);  // Show 2 decimal places
    oledline[6] = "True Count: 0.00";

    displayTextOLED(oledline);

    // Haptic feedback
    vibrate(250);
    oledline[7] = "";
    displayTextOLED(oledline);

    Serial.println("Strategy: " + getStrategyName(currentStrategy));
  }

  lastSwitchState = currentSwitchState;
}


void setup() {

  Serial.begin(9600);
  Serial1.begin(9600);  //Serial1 for the GPS module
  Serial.println("Starting GPS on Serial1...");

  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(vibOutPin, OUTPUT);
  pinMode(SW1_PIN, INPUT_PULLUP);

  Wire.begin();
  if (!myOled.begin(SSD1306_SWITCHCAPVCC, I2C_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for (;;)
      ;
    // Don't proceed, loop forever
  }

  // Clear the buffer
  myOled.clearDisplay();
  myOled.display();
  // Show initial blank screen

  myOled.setTextSize(1);
  myOled.setTextColor(SSD1306_WHITE);
  myOled.setFont();

  // Row 1
  oledline[1] = "MQTT Casino";

  // Initialize all lines
  int jj;
  for (jj = 2; jj <= 8; jj++) {
    oledline[jj] = "";
  }

  oledline[3] = "Strategy: " + getStrategyName(currentStrategy);
  oledline[4] = "Last Card: AKQJT98765";
  oledline[5] = "Run Count: 0.00"; 
  oledline[6] = "True Count: 0.00";

  displayTextOLED(oledline);
  // check for the presence of the shield:
  if (WiFi.status() == WL_NO_SHIELD) {
    Serial.println("WiFi shield not present");
    // don't continue:
    while (true)
      ;
  }

  // attempt to connect to Wifi network:
  while (statusWiFi != WL_CONNECTED) {
    Serial.println("Attempting to connect to SSID: " + String(wifi_ssid));
    statusWiFi = WiFi.begin(wifi_ssid, wifi_pass);
  }
  Serial.println("Connected to WiFi");

  Serial.println("Setting up MQTT...");
  mqttClient.onMessage(onMqttMessage);
  mqttClient.setUsernamePassword(mqttUsername, mqttPassword);

  // Connect to the MQTT broker
  Serial.println("Connecting to MQTT broker...");
  while (!mqttClient.connect(mqttBroker, mqttPort)) {
    Serial.println(mqttClient.connectError());
  }
  Serial.println("Connected to MQTT broker!");


  Serial.print("Subscribing to topic: ");
  Serial.println(subTopic);
  if (!mqttClient.subscribe(subTopic)) {
    Serial.println("Subscription failed!");
  } else {
    Serial.println("Subscribed!");
  }


  lastHeartbeatTime = millis();

  // Send Discord connection notification
  long color;
  String content;
  String message;

  color = 2483968;   // Green
  content = "";      // Ping Users or Roles
  message = String("Connected to Discord Server\\n\\n MQTT Configuration: \\n") + "`" + String(mqttBroker) + "` \\n `" + String(mqttPort) + "` \\n `" + String(subTopic) + "`";
  sendDiscordNotification(buildJsonPayload(message, color, content));
}


void onMqttMessage(int messageSize) {

  String msgString = "";
  msgString.reserve(messageSize);
  while (mqttClient.available()) {
    msgString += (char)mqttClient.read();
  }

  Serial.println(msgString);

  msgString.trim();
  if (msgString.length() > 0) {
    char card = msgString.charAt(0);

    lastCard = msgString;

    long color;
    String content;
    String message;
    switch (card) {

      // Reset case
      case '0':              
        runningCount = 0.0; 
        trueCount = 0.0;
        cardsDealt = 0;
        lastCard = "Shuffle";

        // Reset alert flags
        hotAlertSent = false;
        coldAlertSent = true;

        vibrateReset();
        
        // Send Shuffle Notification
        color = 0; // Black
        content = "";
        message = "Dealer shuffled cards! Table's count is reset.";
        sendDiscordNotification(buildJsonPayload(message, color, content));

        break;
      default:

        // CARD COUNTING ALGORITHM

        double cardValue = getCardValue(card, currentStrategy);
        runningCount += cardValue;
        break;
    }

    // Increment cards dealt unless reset command
    if (card != '0') {
      cardsDealt++;
    }

    // True count calculation
    double decksRemaining = (double)(totalCards - cardsDealt) / 52.0;
    // Protect against division by zero
    if (decksRemaining > 0) {
      trueCount = runningCount / decksRemaining;
    } else {
      trueCount = 0.0;
      // Shoe is over, reset count
    }


    // Update OLED lines
    oledline[4] = "Last Card: " + msgString;
    oledline[5] = "Run Count: " + String(runningCount, 2);  // Show 2 decimal places
    oledline[6] = "True Count: " + String(trueCount, 2);
    
    // Hot alert
    if (runningCount > 4.0 && !hotAlertSent) {  // MODIFIED: Comparison to double
      hotAlertSent = true;
      coldAlertSent = false;

      vibrateHot();

      color = 16732672;  // Red Orange
      content = "<@&1434702820430581892> please join the table.";
      message = "The running count is __**+5**__! 🔥";
      sendDiscordNotification(buildJsonPayload(message, color, content));
    }

    // Cold alert
    else if (runningCount < 1.0 && !coldAlertSent) {  // MODIFIED: Comparison to double
      coldAlertSent = true;
      hotAlertSent = false;

      vibrateCold();

      color = 3325951;  // Blue
      content = "";
      message = "The running count is back to __**0**__. 🥶";
      sendDiscordNotification(buildJsonPayload(message, color, content));
    }
  }

  displayTextOLED(oledline);
}

void loop() {

  while (Serial1.available() > 0) {
    char c = Serial1.read();
    gps.encode(c);
  }

  // Check for strategy switch
  checkStrategySwitch();

  // MQTT subscription polling
  mqttClient.poll();
  currMillis = millis();

  // Heartbeat packets
  checkAndPublishHeartbeat(currMillis);

  if (currMillis - prevMillis > 1000) {
    prevMillis = currMillis;
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));

    // Row 2: WiFi RSSI and IP address
    getWiFiRSSI(tmpBuffer);
    oledline[2] = String(tmpBuffer);
    
    // Row 8: Show subscription topic
    oledline[8] = subTopic;

    displayTextOLED(oledline);
  }
}