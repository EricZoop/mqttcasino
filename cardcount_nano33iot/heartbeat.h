#ifndef HEARTBEAT_H
#define HEARTBEAT_H

#include <Arduino.h>
#include <ArduinoMqttClient.h>
#include <TinyGPSPlus.h>
#include <WiFiNINA.h>

#include "counting_strategies.h" 

extern MqttClient mqttClient;
extern TinyGPSPlus gps; 

extern const int vibOutPin;
extern const char pubTopicHeartbeat[];

extern double runningCount;
extern double trueCount;
extern String lastCard;
extern CountingStrategy currentStrategy; // Access the strategy

// Heartbeat Timing
extern unsigned long lastHeartbeatTime;
extern const unsigned long heartbeatInterval;

extern String getStrategyName(CountingStrategy strategy);

void checkAndPublishHeartbeat(unsigned long currentMillis);

#endif // HEARTBEAT_H