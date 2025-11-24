// Button on ESP32-C3 Super Mini
// Pin D7 is GPIO20
const int buttonPin = 20;  // GPIO20 = D7

void setup() {
  Serial.begin(115200);

  // Use INPUT_PULLUP because button goes to GND
  pinMode(buttonPin, INPUT_PULLUP);

  Serial.println("Button test on GPIO20 (D7)");
}

void loop() {
  int state = digitalRead(buttonPin);

  if (state == LOW) {  
    // Button pressed
    Serial.println("Button pressed");
  } else {
    // Button released
    Serial.println("Button released");
  }

  delay(200);
}
