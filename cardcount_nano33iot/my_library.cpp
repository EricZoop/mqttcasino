#include "my_library.h"
#include <WiFiNINA.h> 
#include <time.h>     
#include <stdio.h>    

void convDDHHMMSS(unsigned long currSeconds, char *uptimeDDHHMMSS) 
{
  int dd, hh, mm, ss;

  ss = currSeconds; //258320.0 2 23:45:20
  dd = (ss/86400);
  hh = (ss-(86400*dd))/3600; 
  mm = (ss-(86400*dd)-(3600*hh))/60;
  ss = (ss-(86400*dd)-(3600*hh)-(60*mm));

  sprintf(uptimeDDHHMMSS, "%02d %02d:%02d:%02d", dd, hh ,mm, ss);
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