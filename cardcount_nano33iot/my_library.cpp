#include "my_library.h"
#include <WiFiNINA.h> 
#include <time.h>     
#include <stdio.h> 

// NEW INCLUDES FOR MOVED FUNCTIONS
#include <Adafruit_SSD1306.h>
#include <WiFiSSLClient.h> 


void convHHMMSS(unsigned long currSeconds, char *uptimeDDHHMMSS) 
{
  int dd, hh, mm, ss;

  ss = currSeconds; //258320.0 2 23:45:20
  dd = (ss/86400);
  hh = (ss-(86400*dd))/3600; 
  mm = (ss-(86400*dd)-(3600*hh))/60;
  ss = (ss-(86400*dd)-(3600*hh)-(60*mm));

  sprintf(uptimeDDHHMMSS, "%02d:%02d:%02d", hh ,mm, ss);
};

void convCurrentTime(unsigned long currSeconds, char *timeStr) 
{
    time_t rawtime = currSeconds;
    struct tm  ts;
    char buf[70];

    ts = *gmtime(&rawtime); 
  
    strftime(buf, sizeof(buf), "%Y-%m-%d %H:%M:%S", &ts);
    sprintf(timeStr, buf);
};

void getWiFiRSSI(char *wifiRSSI) 
{
    sprintf(wifiRSSI, "%lddBm %d.%d.%d.%d", WiFi.RSSI(), WiFi.localIP()[0], WiFi.localIP()[1], WiFi.localIP()[2], WiFi.localIP()[3]);
};



String buildJsonPayload(const String& message, long color, const String& content) {
  
  convHHMMSS(millis() / 1000, tmpBuffer);
  String timestampedMessage = message  + "\\n\\n" + "-# Uptime: " + tmpBuffer;
  return "{"
         "\"content\":\"" + content + "\","
         "\"embeds\":[{"
         "\"description\":\"" + timestampedMessage + "\","
         "\"color\":" + String(color) + ","
         "\"author\":{"
         "\"name\":\"Player1 (Arduino Nano 33 IoT)\","
         "\"icon_url\":\"https://media.discordapp.net/attachments/1435025106564022465/1436926911988105368/zC60TAAAAAZJREFUAwBJUcPv7WJDOgAAAABJRU5ErkJggg.png?ex=69120ab8&is=6910b938&hm=55dfaa1e127e035e815e00293841f1249d3954615cb62c400133f0f4d0860d06&=&format=webp&quality=lossless\""
  
         "}"
    
         "}],"
         "\"username\":\"James Bond\","
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
    client.println(jsonPayload);
    // Send the payload

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