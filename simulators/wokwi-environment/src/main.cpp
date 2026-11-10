// DHT22 virtual sensor and thermostat indicators. Sensor values come from Wokwi;
// thermostat changes indicators only, never invents new sensor readings.
#include <Arduino.h>
#include <DHTesp.h>
DHTesp dht;
float target=22.0,temperature=0,humidity=0;
bool reading=false;
char ack[9]="",line[96];
size_t used=0;
unsigned long last=0;
void report() {
  if(!reading)return;
  const char *mode=temperature<target-.2?"heating":temperature>target+.2?"cooling":"idle";
  digitalWrite(26,!strcmp(mode,"heating"));digitalWrite(27,!strcmp(mode,"cooling"));
  Serial.printf("EW2 climate {\"temperature\":%.1f,\"humidity\":%.1f}\n",temperature,humidity);
  Serial.printf("EW2 thermostat {\"current\":%.1f,\"target\":%.1f,\"mode\":\"%s\"%s%s%s}\n",temperature,target,mode,ack[0]?",\"ack\":\"":"",ack,ack[0]?"\"":"");
}
void setup() {Serial.begin(115200);dht.setup(15,DHTesp::DHT22);pinMode(26,OUTPUT);pinMode(27,OUTPUT);}
void loop() {
  while(Serial.available()) {
    char c=Serial.read();if(c=='\r')continue;
    if(c!='\n'){if(used<sizeof(line)-1)line[used++]=c;else used=sizeof(line);continue;}
    if(used<sizeof(line)) {
      line[used]=0;float value;char id[9]={0},tail;
      if(sscanf(line,"EW2 thermostat target %f %8[0-9a-f]%c",&value,id,&tail)==2 && strlen(id)==8 && value>=10&&value<=30) {target=value;strcpy(ack,id);report();}
    }
    used=0;
  }
  if(millis()-last>=3000) {
    last=millis();TempAndHumidity v=dht.getTempAndHumidity();
    if(dht.getStatus()==DHTesp::ERROR_NONE){temperature=v.temperature;humidity=v.humidity;reading=true;report();}
  }
  delay(25);
}
