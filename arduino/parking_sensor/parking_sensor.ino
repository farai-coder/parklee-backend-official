// Parklee — single ultrasonic sensor (HC-SR04) for one parking spot.
// Wiring (Arduino Nano):
//   HC-SR04 VCC  -> 5V
//   HC-SR04 GND  -> GND
//   HC-SR04 TRIG -> D9
//   HC-SR04 ECHO -> D10
//
// Output: prints one CSV line per measurement, one second apart:
//   <SPOT_NUMBER>,<distance_cm>
// e.g. "A12,23.4"
//
// The host-side sensor_bridge.py reads these lines and POSTs them to the API.

const int TRIG_PIN = 9;
const int ECHO_PIN = 10;

// Set this to whatever spot_number the backend has stored for this physical spot.
const char* SPOT_NUMBER = "A12";

// Sample interval in milliseconds.
const unsigned long SAMPLE_INTERVAL_MS = 1000;

void setup() {
  Serial.begin(9600);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // pulseIn timeout 30 ms => max ~5 m round trip.
  unsigned long duration_us = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration_us == 0) return -1.0;          // no echo
  return (duration_us * 0.0343f) / 2.0f;      // speed of sound 343 m/s
}

void loop() {
  float cm = readDistanceCm();
  if (cm > 0) {
    Serial.print(SPOT_NUMBER);
    Serial.print(",");
    Serial.println(cm, 1);
  }
  delay(SAMPLE_INTERVAL_MS);
}
