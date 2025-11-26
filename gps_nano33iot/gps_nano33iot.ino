#include <TinyGPSPlus.h>

TinyGPSPlus gps;

void setup() {
  Serial.begin(115200);   // USB Serial for monitor
  Serial1.begin(9600);    // GPS module on Serial1
  Serial.println("Starting GPS on Serial1...");
}

void loop() {
while (Serial1.available() > 0) {
  char c = Serial1.read();
  Serial.write(c);  // <-- Print raw GPS data to Serial Monitor
  gps.encode(c);    // Still feed TinyGPS++ the same data
}

}
