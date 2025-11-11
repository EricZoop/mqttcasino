#ifndef MY_LIBRARY_H
#define MY_LIBRARY_H

#include <Arduino.h>



// BITMAPS
const unsigned char spade_bitmap[] PROGMEM   = // Hex // Binary
{ 0x10,   // 00010000   
  0x38,   // 00111000   
  0x7C,   // 01111100   
  0xFE,   // 11111110   
  0x6C,   // 01101100   
  0x10,   // 00010000   
  0x7C,   // 01111100   
  0x00    // 00000000   
};
const unsigned char heart_bitmap[] PROGMEM   = {0x66,0xFF,0xFF,0xFF,0x7E,0x3C,0x18,0x00};
const unsigned char club_bitmap[] PROGMEM    = {0x38,0x38,0xFE,0xFE,0x6C,0x10,0x7C,0x00};
const unsigned char diamond_bitmap[] PROGMEM = {0x10,0x38,0x7C,0xFE,0x7C,0x38,0x10,0x00};

// FUNCTION PROTOTYPES
void convDDHHMMSS(unsigned long currSeconds, char *uptimeDDHHMMSS);
void convCurrentTime(unsigned long currSeconds, char *timeStr);
void getWiFiRSSI(char *wifiRSSI);


#endif // MY_LIBRARY_H