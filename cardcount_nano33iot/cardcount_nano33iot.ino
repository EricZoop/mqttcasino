/**************************************************************************
 Class: ECE508 Fall 2025
 Team 8
 Date: 12/15/2025

 Final Project
 Description: Card counting system with multiple strategies
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
#include "counting_strategies.h"

// Internet Configuration
const char* wifi_ssid = "GuestZ";               // REPLACE
const char* wifi_pass = "rooster65";            // REPLACE
//*************************************************************

// Discord Configuration
const char webhookHost[] = "discord.com";
const int webhookPort = 443;
const char webhookPath[] = "/api/webhooks/1442641244252803223/lTG5afLzq5f_i0Qw6wy_1lhYNjQlci6zncikj7vuZF80o0du6d35ITz5qeOckVECoLb5";
//*************************************************************

// MQTT Configuration
const char mqttBroker[] = "broker.hivemq.com";
const int mqttPort = 1883;
const char subTopic[] = "gmu/ece508/team08/blkjck_table1";

// const char subTopicHeartbeat[] = " gmu/ece508/team08/player1";
//*************************************************************


WiFiSSLClient client;

#define vibOutPin 5 // Vibrator actuator
#define SW1_PIN 10 // Switch

int statusWiFi = WL_IDLE_STATUS;
#define I2C_ADDRESS 0x3C
#define SCREEN_WIDTH 128 // OLED display width, in pixels
#define SCREEN_HEIGHT 64 // OLED display height, in pixels
#define OLED_RESET    -1 // Reset pin # (or -1 if sharing Arduino reset pin)

// Initialize the Adafruit OLED display driver
Adafruit_SSD1306 myOled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
WiFiClient wifiClient;
MqttClient mqttClient(wifiClient); // Instantiate the client

int scrollPosition = 0;
unsigned long lastScrollTime = 0;
const int scrollDelay = 250; // ms between scroll steps
const int maxDisplayChars = 21; // Max characters that fit on one line (128px / 6px per char)

long currMillis, prevMillis;
char tmpBuffer[64];
String oledline[9];

JSONVar sensorObj;
String stringJson;
int runningCount = 0;
double trueCount = 0.0;

const int totalDecks = 6;
const int totalCards = totalDecks * 52; // 312

int cardsDealt = 0;

// Flags to ensure one-time alerts
bool hotAlertSent = false;
bool coldAlertSent = true; // START "cold" alert as already sent (disarmed)

// Card counting strategy
CountingStrategy currentStrategy = HILO; // Default to Hi-Lo
bool lastSwitchState = HIGH;

void vibrate(int duration) {

  oledline[7] = "       VIBRATING!"; 
  displayTextOLED(oledline);

  digitalWrite(vibOutPin, HIGH);
  delay(duration);
  digitalWrite(vibOutPin, LOW);
  

  oledline[7] = ""; 
  displayTextOLED(oledline); 
}

// VIBRATION CONFIG

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
  vibrate(500); // Very short blip
}

void checkStrategySwitch() {
  bool currentSwitchState = digitalRead(SW1_PIN);
  
  // Detect button press (assuming pull-up, so LOW = pressed)
  if (currentSwitchState == LOW && lastSwitchState == HIGH) {
    delay(50); // Debounce
    
    // Toggle strategy
    if (currentStrategy == HILO) {
      currentStrategy = OMEGA_II;
    } else {
      currentStrategy = HILO;
    }
    
    // Reset counts when changing strategy
    runningCount = 0;
    trueCount = 0.0;
    cardsDealt = 0;
    hotAlertSent = false;
    coldAlertSent = true;
    
    // Update all relevant OLED lines
    oledline[3] = "Strategy: " + getStrategyName(currentStrategy);
    oledline[4] = "Last Card: AKQJT98765";
    oledline[5] = "Run Count: 0";
    oledline[6] = "True Count: 0.00";
    
    displayTextOLED(oledline);
    
    // Haptic feedback
    vibrate(125);
    
    oledline[7] = "";
    displayTextOLED(oledline);
    
    Serial.println("Strategy: " + getStrategyName(currentStrategy));
  }
  
  lastSwitchState = currentSwitchState;
}

void setup() {
  //Initialize serial:
  Serial.begin(9600);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(vibOutPin, OUTPUT); 
  pinMode(SW1_PIN, INPUT_PULLUP); // Configure switch with internal pull-up

  Wire.begin();
  if (!myOled.begin(SSD1306_SWITCHCAPVCC, I2C_ADDRESS)) {
    Serial.println(F("SSD1306 allocation failed"));
    for (;;);
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
  int jj; for (jj = 2; jj <= 8; jj++) {
    oledline[jj] = "";
  }

  oledline[3] = "Strategy: " + getStrategyName(currentStrategy);
  oledline[4] = "Last Card: AKQJT9876";
  oledline[5] = "Run Count: 0";
  oledline[6] = "True Count: 0.00";
  
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

  Serial.println("Setting up MQTT...");
  mqttClient.onMessage(onMqttMessage);
  
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


  // Send Discord connection notification
  long color;
  String content;
  String message;

  color = 2483968; // Green
  content = ""; // Ping Users or Roles
  message = String("Connected to Discord Server\\n\\n MQTT Configuration: \\n") +
          "`" + String(mqttBroker) + "` \\n `" + String(mqttPort) + "` \\n `" + String(subTopic) + "`";
  sendDiscordNotification(buildJsonPayload(message, color, content));
}


void onMqttMessage(int messageSize) {

  String msgString = "";
  msgString.reserve(messageSize);
  while (mqttClient.available()) {
    msgString += (char)mqttClient.read();
  }

  Serial.println(msgString);
  
  // CARD COUNTING ALGORITHM

  msgString.trim();
  if (msgString.length() > 0) {
    char card = msgString.charAt(0);
    // Local variables for Discord message
    long color;
    String content;
    String message;

    switch (card) {
      case '0': // Reset case
        runningCount = 0;
        trueCount = 0.0;
        cardsDealt = 0;
        
        // Reset alert flags
        hotAlertSent = false;
        coldAlertSent = true; // Set to true to prevent "back to 0" alert

        
        vibrateReset(); 
        
        // Send Shuffle Notification
        color = 0; // Black
        content = "";
        message = "Dealer shuffled cards! Table's count is reset.";
        sendDiscordNotification(buildJsonPayload(message, color, content));

        break;

      default:
        // Use the strategy system to get card value
        int cardValue = getCardValue(card, currentStrategy);
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
      trueCount = (double)runningCount / decksRemaining;
    } else {
      trueCount = 0.0;
      // Shoe is over, reset count
    }


    // Update OLED lines
    oledline[4] = "Last Card: " + msgString;
    oledline[5] = "Run Count: " + String(runningCount);
    oledline[6] = "True Count: " + String(trueCount, 2);


    // Hot alert (threshold may need adjustment for Omega II)
    if (runningCount > 4 && !hotAlertSent) {
      hotAlertSent = true;
      coldAlertSent = false;

      vibrateHot(); 

      color = 16732672; // Red Orange
      content = "<@&1434702820430581892> please join the table.";
      message = "The running count is __**+5**__! 🔥";
      sendDiscordNotification(buildJsonPayload(message, color, content));
    }

    // Cold alert
    else if (runningCount < 1 && !coldAlertSent) {
      coldAlertSent = true;
      hotAlertSent = false;

      vibrateCold(); 

      color = 3325951; // Blue
      content = "";
      message = "The running count is back to __**0**__. 🥶";
      sendDiscordNotification(buildJsonPayload(message, color, content));
    }
  
  } 

  displayTextOLED(oledline); // Refresh the display
}

void loop() {

  // Check for strategy switch
  checkStrategySwitch();
  
  // MQTT polling
  mqttClient.poll();
  currMillis = millis();

  if (currMillis - prevMillis > 1000) {
    prevMillis = currMillis;
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    
    // Row 2: WiFi RSSI and IP address
    getWiFiRSSI(tmpBuffer);
    oledline[2] = String(tmpBuffer);
    
    // Row 8: Show subscription
    oledline[8] = subTopic;

    displayTextOLED(oledline);
  }
}