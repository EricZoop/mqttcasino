#ifndef HEARTBEAT_H
#define HEARTBEAT_H

#include <Arduino.h>
#include <ArduinoMqttClient.h>
#include <TinyGPSPlus.h>
#include <WiFiNINA.h> // Needed for WiFi.RSSI()
#include "counting_strategies.h" // Assuming this is needed for CountingStrategy type

// --- External Global Variables (Defined in cardcount_nano33iot.ino) ---
// Complex objects are declared extern so they can be accessed.
extern MqttClient mqttClient;
extern TinyGPSPlus gps; 

// Hardware, Topic, and State Variables.
extern const int vibOutPin;
extern const char pubTopicHeartbeat[];

// Card Counting State
extern double runningCount;
extern double trueCount;
extern String lastCard;
extern CountingStrategy currentStrategy; // NEW: Added to access the strategy

// Heartbeat Timing
extern unsigned long lastHeartbeatTime;
extern const unsigned long heartbeatInterval;

// --- Function Prototypes ---
extern String getStrategyName(CountingStrategy strategy); // Assuming this is globally visible (e.g., in counting_strategies.h)

/**
 * @brief Checks if the heartbeat interval has passed and publishes a new status message.
 * @param currentMillis The current value of millis().
 */
void checkAndPublishHeartbeat(unsigned long currentMillis);

#endif