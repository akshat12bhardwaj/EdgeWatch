// Virtual LED and relay actuation. Power and energy are explicitly simulated,
// not electrical measurements. Firmware emits an ack only after GPIO changes.
#include <Arduino.h>
bool light=false,plug=false;
double energy=0;
char lightAck[9]="",plugAck[9]="",line[96];
size_t used=0;
unsigned long last=0,lastEnergy=0;
void report() {
  Serial.printf("EW2 light {\"on\":%s%s%s%s}\n",light?"true":"false",lightAck[0]?",\"ack\":\"":"",lightAck,lightAck[0]?"\"":"");
  Serial.printf("EW2 plug {\"on\":%s,\"power_w\":%d,\"energy_wh\":%.4f,\"appliance_w\":60%s%s%s}\n",plug?"true":"false",plug?60:0,energy,plugAck[0]?",\"ack\":\"":"",plugAck,plugAck[0]?"\"":"");
}
void setup() {Serial.begin(115200);pinMode(26,OUTPUT);pinMode(27,OUTPUT);digitalWrite(26,LOW);digitalWrite(27,LOW);}
void loop() {
  while(Serial.available()) {
    char c=Serial.read();if(c=='\r')continue;
    if(c!='\n'){if(used<sizeof(line)-1)line[used++]=c;else used=sizeof(line);continue;}
    if(used<sizeof(line)) {
      line[used]=0;char channel[12]={0},id[9]={0},tail;int value=-1;
      if(sscanf(line,"EW2 %11s on %d %8[0-9a-f]%c",channel,&value,id,&tail)==3&&strlen(id)==8&&(value==0||value==1)) {
        if(!strcmp(channel,"light")){light=value;strcpy(lightAck,id);digitalWrite(26,light?HIGH:LOW);report();}
        if(!strcmp(channel,"plug")){plug=value;strcpy(plugAck,id);digitalWrite(27,plug?HIGH:LOW);report();}
      }
    }
    used=0;
  }
  unsigned long now=millis();
  if(plug&&lastEnergy)energy+=60.0*(now-lastEnergy)/3600000.0;
  lastEnergy=now;
  if(now-last>=5000){last=now;report();}
  delay(25);
}
