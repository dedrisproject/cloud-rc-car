/*
 * Cloud RC Car - Arduino motor-shield firmware
 *
 * Receives commands from the Raspberry Pi over the serial link as ASCII codes
 * terminated by '|', e.g. "7|". Channel A drives the rear motor (throttle /
 * reverse), Channel B drives the steering motor (left / center / right).
 *
 * Protocol (must stay in sync with server/motor.py SERIAL_CODES):
 *    7  -> forward      6  -> brake/stop      1  -> reverse
 *   14  -> steer left  12  -> wheels center  15  -> steer right
 */

// Channel A - drive motor
const int A_DIR   = 12;  // direction
const int A_BRAKE = 9;   // brake
const int A_PWM   = 3;   // speed (PWM)

// Channel B - steering motor
const int B_DIR   = 13;  // direction
const int B_BRAKE = 8;   // brake
const int B_PWM   = 11;  // speed (PWM)

String buffer = "";

void setup() {
  Serial.begin(115200);
  pinMode(A_DIR, OUTPUT);
  pinMode(A_BRAKE, OUTPUT);
  pinMode(B_DIR, OUTPUT);
  pinMode(B_BRAKE, OUTPUT);
  stopAll();
  Serial.println("RC car firmware ready");
}

void loop() {
  // Read characters until a full '|'-terminated command is available.
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '|') {
      handleCommand(buffer);
      buffer = "";
    } else if (c != '\r' && c != '\n') {
      buffer += c;
    }
  }
}

void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  Serial.println("cmd: " + cmd);

  if (cmd == "7") {            // forward
    digitalWrite(A_DIR, HIGH);
    digitalWrite(A_BRAKE, LOW);
    analogWrite(A_PWM, 255);
  } else if (cmd == "1") {     // reverse (opposite direction)
    digitalWrite(A_DIR, LOW);
    digitalWrite(A_BRAKE, LOW);
    analogWrite(A_PWM, 255);
  } else if (cmd == "6") {     // brake / stop
    digitalWrite(A_BRAKE, HIGH);
    analogWrite(A_PWM, 0);
  } else if (cmd == "14") {    // steer left
    digitalWrite(B_DIR, HIGH);
    digitalWrite(B_BRAKE, LOW);
    analogWrite(B_PWM, 255);
  } else if (cmd == "15") {    // steer right
    digitalWrite(B_DIR, LOW);
    digitalWrite(B_BRAKE, LOW);
    analogWrite(B_PWM, 255);
  } else if (cmd == "12") {    // wheels center
    digitalWrite(B_BRAKE, HIGH);
    analogWrite(B_PWM, 0);
  }
}

void stopAll() {
  digitalWrite(A_BRAKE, HIGH);
  analogWrite(A_PWM, 0);
  digitalWrite(B_BRAKE, HIGH);
  analogWrite(B_PWM, 0);
}
