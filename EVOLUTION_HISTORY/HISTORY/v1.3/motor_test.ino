// ESP32-S3 motor spin test (L298N / TB6612FNG)
#define PWM 19
#define IN1 20
#define IN2 21
#define STBY 22
void setup(){
  pinMode(PWM, OUTPUT); pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT); pinMode(STBY, OUTPUT);
  digitalWrite(STBY, HIGH);
}
void loop(){
  digitalWrite(IN1, HIGH); digitalWrite(IN2, LOW);
  analogWrite(PWM, 200); delay(1500);      // forward
  analogWrite(PWM, 0);   delay(500);
  digitalWrite(IN1, LOW);  digitalWrite(IN2, HIGH);
  analogWrite(PWM, 200); delay(1500);      // reverse
  analogWrite(PWM, 0);   delay(1000);
}