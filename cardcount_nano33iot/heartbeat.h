#ifndef HEARTBEAT_H
#define HEARTBEAT_H

#include <Arduino.h>
#include <ArduinoMqttClient.h>
#include <TinyGPSPlus.h>
#include <WiFiNINA.h>

#include "counting_strategies.h" 

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

extern String getStrategyName(CountingStrategy strategy); // Assuming this is globally visible (e.g., in counting_strategies.h)

void checkAndPublishHeartbeat(unsigned long currentMillis);

#endif