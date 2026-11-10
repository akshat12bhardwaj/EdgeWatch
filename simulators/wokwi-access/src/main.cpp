// Virtual PIR, door switch and servo lock. EW2 carries sensor state over serial;
// WiFi/MQTT is not used by this firmware. Remote inputs cannot fake PIR or door readings.
#include <Arduino.h>
const int PIR=13, DOOR=14, SERVO=26;
bool locked=true;
char ack[9]="", line[96];
size_t used=0;
unsigned long last=0;
int motion=-1, door=-1;
void report() {
  Serial.printf("EW2 motion {\"motion\":%s}\n",digitalRead(PIR)?"true":"false");
  Serial.printf("EW2 door {\"open\":%s}\n",digitalRead(DOOR)?"true":"false");
  Serial.printf("EW2 lock {\"locked\":%s%s%s%s}\n",locked?"true":"false",ack[0]?",\"ack\":\"":"",ack,ack[0]?"\"":"");
}
void actuator() {
  // Servo PWM: 50 Hz, 16-bit. 0 degrees (locked), 90 degrees (unlocked).
  ledcWrite(0, locked?1638:4915);
}
void setup() {
  Serial.begin(115200);pinMode(PIR,INPUT);pinMode(DOOR,INPUT_PULLUP);
  ledcSetup(0,50,16);ledcAttachPin(SERVO,0);actuator();
}
void loop() {
  while(Serial.available()) {
    char c=Serial.read();if(c=='\r')continue;
    if(c!='\n'){if(used<sizeof(line)-1)line[used++]=c;else used=sizeof(line);continue;}
    if(used<sizeof(line)) {
      line[used]=0;int value=-1;char id[9]={0},tail;
      if(sscanf(line,"EW2 lock locked %d %8[0-9a-f]%c",&value,id,&tail)==2 && strlen(id)==8 && (value==0||value==1)) {
        locked=value==1;strcpy(ack,id);actuator();report();
      }
    }
    used=0;
  }
  int m=digitalRead(PIR),d=digitalRead(DOOR);
  if(m!=motion||d!=door||millis()-last>=5000) {motion=m;door=d;last=millis();report();}
  delay(25);
}
