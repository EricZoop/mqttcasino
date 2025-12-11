#include "heartbeat.h"
#include <Arduino_JSON.h>
#include "my_library.h" // convHHMMSS

void publishHeartbeat() {
  // Uptime
  unsigned long ms = millis();
  unsigned long seconds = ms / 1000;
  
  char uptimeBuffer[30];
  convHHMMSS(seconds, uptimeBuffer);

  long rssi = WiFi.RSSI();
  
  // Prepare JSON payload
  JSONVar heartbeatObj;
  heartbeatObj["class"] = "ece508";
  heartbeatObj["team"] = "08";
  heartbeatObj["device"] = "nano33iot";
  heartbeatObj["uptime"] = String(uptimeBuffer);
  heartbeatObj["rssi"] = String(rssi);
  heartbeatObj["strategy"] = getStrategyName(currentStrategy); // Added card counting strategy
  heartbeatObj["last_card"] = lastCard; // Use extern global
  heartbeatObj["running_count"] = String(runningCount); // Use extern global
  heartbeatObj["true_count"] = String(trueCount, 2); // Use extern global

  
  // GPS Data (no decimals!)
  if (gps.location.isValid()) {
    heartbeatObj["lat"] = String(gps.location.lat(), 0);
    heartbeatObj["lon"] = String(gps.location.lng(), 0);
  } else {
    heartbeatObj["lat"] = "N/A";
    heartbeatObj["lon"] = "N/A";
  }

  if (gps.altitude.isValid()) {
    heartbeatObj["alt"] = String(gps.altitude.meters(), 1); 
  } else {
    heartbeatObj["alt"] = "N/A";
  }
  
  String jsonString = JSON.stringify(heartbeatObj);
  
  // Publish & Print
  if (mqttClient.connected()) {
    mqttClient.beginMessage(pubTopicHeartbeat); // Use extern global
    mqttClient.print(jsonString);
    mqttClient.endMessage();
    Serial.print("Heartbeat packet: ");
    Serial.println(jsonString);
  } else {
    Serial.println("MQTT Client not connected. Cannot publish heartbeat.");
  }

  lastHeartbeatTime = millis();
}

void checkAndPublishHeartbeat(unsigned long currentMillis) {
  if (currentMillis - lastHeartbeatTime >= heartbeatInterval) {
    publishHeartbeat();
  }
}