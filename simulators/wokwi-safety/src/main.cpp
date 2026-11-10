// Smoke-level substitute: virtual potentiometer, not a gas sensor. Alarm is a
// device safety event. Camera is status/motion-event logic, never image/video.
#include <Arduino.h>
float level=0,threshold=30,injected=0;
bool alarmActive=false,monitoring=true;
unsigned int motionEvents=0;
char smokeAck[9]="",cameraAck[9]="",line[112];
size_t used=0;
unsigned long last=0,lastTick=0;
void report() {
  Serial.printf("EW2 smoke {\"level\":%.1f,\"threshold\":%.1f,\"alarm\":%s%s%s%s}\n",level,threshold,alarmActive?"true":"false",smokeAck[0]?",\"ack\":\"":"",smokeAck,smokeAck[0]?"\"":"");
  Serial.printf("EW2 camera {\"monitoring\":%s,\"motion_events\":%u%s%s%s}\n",monitoring?"true":"false",motionEvents,cameraAck[0]?",\"ack\":\"":"",cameraAck,cameraAck[0]?"\"":"");
}
void indicators() {
  digitalWrite(26,monitoring?HIGH:LOW);
  // Use an explicitly initialized PWM channel. The Arduino tone helper queries
  // an uninitialized LEDC channel and can flood this serial transport with errors.
  static bool sounding=false;
  if(alarmActive!=sounding) {
    ledcWriteTone(0,alarmActive?880:0);
    sounding=alarmActive;
  }
}
void setup() {Serial.begin(115200);pinMode(34,INPUT);pinMode(26,OUTPUT);ledcSetup(0,880,10);ledcAttachPin(25,0);ledcWriteTone(0,0);indicators();}
void loop() {
  while(Serial.available()) {
    char c=Serial.read();if(c=='\r')continue;
    if(c!='\n'){if(used<sizeof(line)-1)line[used++]=c;else used=sizeof(line);continue;}
    if(used<sizeof(line)) {
      line[used]=0;char channel[12]={0},field[20]={0},id[9]={0},tail;float value;
      if(sscanf(line,"EW2 %11s %19s %f %8[0-9a-f]%c",channel,field,&value,id,&tail)==4&&strlen(id)==8) {
        bool applied=false;
        if(!strcmp(channel,"smoke")) {
          if(!strcmp(field,"smoke")&&(value==0||value==1)){if(value==1)injected=100;applied=true;}
          if(!strcmp(field,"reset")&&(value==0||value==1)){if(value==1){injected=0;alarmActive=false;}applied=true;}
          if(!strcmp(field,"threshold")&&value>=10&&value<=50){threshold=value;applied=true;}
          if(applied)strcpy(smokeAck,id);
        }
        if(!strcmp(channel,"camera")) {
          if(!strcmp(field,"monitoring")&&(value==0||value==1)){monitoring=value;applied=true;}
          if(!strcmp(field,"simulate_motion")&&(value==0||value==1)&&monitoring){if(value==1&&motionEvents<1000000)motionEvents++;applied=true;}
          if(applied)strcpy(cameraAck,id);
        }
        if(applied){level=max(analogRead(34)*100.0f/4095.0f,injected);if(level>=threshold)alarmActive=true;indicators();report();}
      }
    }
    used=0;
  }
  unsigned long now=millis();
  if(now-lastTick>=200) {
    float old=level;bool oldAlarm=alarmActive;
    injected=max(0.0f,injected-(now-lastTick)/1000.0f);lastTick=now;
    level=max(analogRead(34)*100.0f/4095.0f,injected);if(level>=threshold)alarmActive=true;indicators();
    if(fabs(old-level)>=1||oldAlarm!=alarmActive||now-last>=5000){last=now;report();}
  }
  delay(25);
}
