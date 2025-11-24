#define vibOutPin 0

void setup() {
  pinMode(vibOutPin,OUTPUT);// define a pin as output
 
}

void loop() {

    digitalWrite(vibOutPin,HIGH);
    delay(2000);
    digitalWrite(vibOutPin, LOW);
    delay(600); 
    digitalWrite(vibOutPin,HIGH);
    delay(2000);
    digitalWrite(vibOutPin, LOW);
    delay(600);  
    digitalWrite(vibOutPin,HIGH);
    delay(2000);
    digitalWrite(vibOutPin, LOW);
    delay(600);              
  

    delay(5000);
}// loop