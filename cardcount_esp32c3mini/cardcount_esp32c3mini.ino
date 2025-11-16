// Try this sketch before removing the // from your file
// #include "arduino_secrets.h" 
// #include "thingProperties.h"
#include <WiFi.h>
#include <esp_wifi.h>

//Time in seconds
#define CONNECTION_TIMEOUT 20  // Increased timeout
#define DEEP_SLEEP_DURATION 10

// Paste your SSID and PASSWORD from your internet provider or settings
const char SSID[31] = "GuestZ";     //Update with your WiFi SSID
const char PASS[31] = "rooster65"; //Update with your WiFi password

void setup() {
  Serial.begin(115200);
  delay(1500);
  
  // Configure strapping pins after boot
  pinMode(2, INPUT);   // or INPUT_PULLUP if needed
  pinMode(8, INPUT);
  pinMode(9, INPUT);
  
  Serial.println("Strapping pins configured");
  
  // Now proceed with WiFi
  scanNetworks();
  connectToWiFi();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nConnected to the WiFi network");
    get_network_info();
  }
}

void scanNetworks() {
  Serial.println("Scanning for networks...");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  
  int n = WiFi.scanNetworks();
  Serial.println("Scan complete");
  
  if (n == 0) {
    Serial.println("No networks found");
  } else {
    Serial.print(n);
    Serial.println(" networks found:");
    for (int i = 0; i < n; ++i) {
      Serial.print(i + 1);
      Serial.print(": ");
      Serial.print(WiFi.SSID(i));
      Serial.print(" (");
      Serial.print(WiFi.RSSI(i));
      Serial.print(" dBm) ");
      Serial.print((WiFi.encryptionType(i) == WIFI_AUTH_OPEN) ? "Open" : "Encrypted");
      
      // Check if this is your network
      if (WiFi.SSID(i) == SSID) {
        Serial.print(" <- YOUR NETWORK FOUND!");
      }
      Serial.println();
    }
  }
  Serial.println();
}

void connectToWiFi() {
  Serial.print("Connecting to: ");
  Serial.println(SSID);
  
  WiFi.disconnect(true);
  delay(1000);  // Longer delay
  WiFi.mode(WIFI_STA);
  
  // Configure WiFi before connecting
  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);
  
  // Start connection
  WiFi.begin(SSID, PASS);
  
  unsigned long startAttemptTime = millis();
  int dotCount = 0;
  
  while (WiFi.status() != WL_CONNECTED && 
         millis() - startAttemptTime < CONNECTION_TIMEOUT * 1000) {
    
    // Print status every 2 seconds
    if (dotCount % 4 == 0) {
      Serial.print(" [");
      Serial.print(wl_status_to_string(WiFi.status()));
      Serial.print("]");
    }
    
    Serial.print(".");
    dotCount++;
    if (dotCount % 20 == 0) {
      Serial.println();
    }
    delay(500);
  }
  Serial.println();
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Connection failed!");
    Serial.print("Final WiFi Status: ");
    Serial.println(wl_status_to_string(WiFi.status()));
    Serial.println("\nRestarting in 5 seconds...");
    delay(5000);
    ESP.restart();
  } else {
    Serial.println("Connected successfully!");
  }
}

const char *wl_status_to_string(wl_status_t status) {
  switch (status) {
    case WL_NO_SHIELD: return "WL_NO_SHIELD";
    case WL_IDLE_STATUS: return "WL_IDLE_STATUS";
    case WL_NO_SSID_AVAIL: return "WL_NO_SSID_AVAIL";
    case WL_SCAN_COMPLETED: return "WL_SCAN_COMPLETED";
    case WL_CONNECTED: return "WL_CONNECTED";
    case WL_CONNECT_FAILED: return "WL_CONNECT_FAILED";
    case WL_CONNECTION_LOST: return "WL_CONNECTION_LOST";
    case WL_DISCONNECTED: return "WL_DISCONNECTED";
    default: return "UNKNOWN";
  }
}

void get_network_info() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("[*] Network information for ");
    Serial.println(SSID);
    Serial.println("[+] BSSID : " + WiFi.BSSIDstr());
    Serial.print("[+] Gateway IP : ");
    Serial.println(WiFi.gatewayIP());
    Serial.print("[+] Subnet Mask : ");
    Serial.println(WiFi.subnetMask());
    Serial.println((String) "[+] RSSI : " + WiFi.RSSI() + " dB");
    Serial.print("[+] ESP32 IP : ");
    Serial.println(WiFi.localIP());
  }
}