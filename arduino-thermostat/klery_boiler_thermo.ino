
//web page buttons make pin 5 high/low
//use the ' in html instead of " to prevent having to escape the "
//address will look like http://192.168.1.200:90 when submited
//for use with W5100 based ethernet shields
//note that the below bug fix may be required
// http://code.google.com/p/arduino/issues/detail?id=605
/*
 * I can't explain WHY this is necessary, but something among the various
 * libraries here appears to be wreaking inexplicable havoc with the
 * 'ARDUINO' definition, making the usual version test unusable (BOTH
 * Tutorial is at http://www.ladyada.net/learn/arduino/ethfiles.html
 * Pull requests should go to http://github.com/adafruit/SDWebBrowse

Light/Soil/Temp/Humid sensor/relay + timer relay.

http://www.ebay.co.uk/itm/Chinduino-Shield-Smoke-Gas-Sensor-Module-MQ2-free-Cable-/270965556096?pt=LH_DefaultDomain_0&hash=item3f16ce4380#ht_3405wt_756
http://www.ebay.co.uk/itm/High-Sensitivity-Light-Sensor-Module-good-performance-arduino-compatible-/270960245669?pt=LH_DefaultDomain_0&hash=item3f167d3ba5#ht_3950wt_877
http://www.ladyada.net/learn/sensors/dht.html
http://www.ladyada.net/learn/breakoutplus/ds1307rtc.html
 */
 
#include "DHT.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include "RTClib.h"
#include <SPI.h>
#include <Ethernet.h>

char identification[] = "GHdevelopment";

byte mac[] = {0xAA, 0xAA, 0xAA, 0xAA, 0xAA, 0xA0 }; //assign arduino mac address
byte ip[] = {192, 168, 88, 201 }; // ip in lan assigned to arduino
char myip[] = "http://192.168.88.201:90/"; //changes with the above ip manually... :(
byte gateway[] = {192, 168, 88, 1 }; // internet access via router
byte subnet[] = {255, 255, 255, 0 }; //subnet mask
EthernetServer server(90); //server port arduino server will use
EthernetClient client;
char serverName[] = "192.168.88.41"; // (DNS) Home's test web page server (Database Server)
//byte serverName[] = { 208, 104, 2, 86 }; // (IP) zoomkat web page server IP address

String readString; //used by server to capture GET request 

unsigned long lastConnectionTime = 0;          // last time you connected to the server, in milliseconds
boolean lastConnected = false;                 // state of the connection last time through the main loop
const unsigned long postingInterval = 30*1000;  // delay between updates, in milliseconds
//////////////////////

/********************* SENSORS STUFF **********************/
RTC_DS1307 RTC;

#define ONE_WIRE_BUS 2  // Dallas Sensors ********************
OneWire oneWire(ONE_WIRE_BUS); // Setup a oneWire instance to communicate with any OneWire devices
DallasTemperature sensors(&oneWire);

#define DHTPIN 3     // what pin we're connected to   
#define DHTTYPE DHT22   // DHT 22  (AM2302)
DHT dht(DHTPIN, DHTTYPE);

int ledPin = 13;               // choose pin for the LED
int MQ2_Pin = 15;            // Soil
int lightSensorPin = 14;      // Light
int Relay1 = 6;   // Mains
int Relay2 = 7;   // Fan
int Relay3 = 8;   // Heater
int Relay4 = 9;   // Lights
// pin 10~13 used for the ethernet 
int RelayMaster = 5;

int lightonhour = 23;    // Turn on the lights at...
int lightonmin = 0;
int lighttotalmin = 720;    // Lights on for... mins
boolean lighton = 0;

// Environmental controller vars
int SOScounter = 0; // Counts total shutdowns
boolean fanTStat = 1;  //fan relay status according to T
boolean fanHumStat = 0; // fan according to humidity
boolean heatStat = 0;
float tempSOS = 35;
float tempSOSdiff = 5;
float tempDayMin = 23.7;
float tempDayDiff = 0.7;
float tempNightMin = 18;
//float tempNightDiff = 0.5;
float humMax = 65;
float humDiff = 5;

int senseNoLight = 50;
int maxLightReboots = 3;
//float temporc = 25; // for webserver form devel
//float tempord = 2;
//float temporh = 99;

//int maxTemp = 0;
//int minTemp = 50;
//int maxHum = 0;
//int minHum = 100;

char warning[ ] = "";  //used for gas leak!

// int inputPin = 2;        // choose input pin (for Push Button)
/***************************************************************/

void setup(){
  Serial.begin(9600); 

/****SENSORS SETUP****/
  pinMode(ledPin, OUTPUT);      // declare LED 13 as output
  pinMode(Relay1, OUTPUT);      //pin6 
  pinMode(Relay2, OUTPUT);      //pin7
  pinMode(Relay3, OUTPUT);      //pin8   
  pinMode(Relay4, OUTPUT); 
  
  digitalWrite(Relay1, LOW);
  digitalWrite(Relay2, LOW);
  digitalWrite(Relay3, HIGH);
  digitalWrite(Relay4, LOW);
//  pinMode(inputPin, INPUT);     // declare magnetic switch as input

// power up rtc ** interfering with input??
  pinMode(18, OUTPUT);      //pin7
  pinMode(19, OUTPUT);      //pin8 
  digitalWrite(19, HIGH);
  digitalWrite(18, LOW);
  
  
  sensors.begin();
  dht.begin();
  Wire.begin();

  
  // give some modules time to boot up:
  delay(500);
  RTC.begin();
  //pinMode(5, OUTPUT); //pin 5 selected to control
  Ethernet.begin(mac,ip,gateway,gateway,subnet); 
  server.begin();
  delay(500);
  
  Serial.println("Mega client/server, GH Monitor, Fan Controller 09/12/13, GHMon_fanCntrl_websrv"); // keep track of what is loaded
  Serial.println(identification);
  Serial.print("Free RAM: ");
  Serial.println(FreeRam());  
  if (! RTC.isrunning()) {
    Serial.println("RTC is NOT running!");
    // following line sets the RTC to the date & time this sketch was compiled
    RTC.adjust(DateTime(__DATE__, __TIME__));  
  }
  Serial.println("Send an g in serial monitor to test client"); // what to do to test client
  
}

int FreeRam () {   // Not needed with SD libraries!!! Have to comment then...
  extern int __heap_start, *__brkval; 
  int v; 
  return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval); 
}

/****** TIMER RELAY HANDLING ********/
boolean timerIsOn(DateTime dateObj, int turnOnAtHr, float turnOnAtMin, float minutesOn) {
  float timerOn = turnOnAtHr + turnOnAtMin/60;  // format: hh.mm, #Dec mm
  float timerOff = timerOn + minutesOn/60;
  float nowMinute = dateObj.minute();
  float timerNow = dateObj.hour() + nowMinute/60;
//  Serial.print(timerOn);
//  Serial.print(timerOff);
//  Serial.println(timerNow);
  if (timerOff < 24) {
   if (timerNow<timerOff && timerNow>=timerOn) {
     return 1;
   } else {
     return 0;
   }
  } else {
    if (timerNow>=(timerOff-24) && timerNow<timerOn) {
      return 0;
    } else {
      return 1;
    }
  }
}
    
void setRelay(int relay, boolean pos) {
  if (pos) {
    digitalWrite(relay, HIGH);
  } else {
    digitalWrite(relay, LOW);
  }
}

/****************************************/

// Dump sensor readings
void CurrentSensors(EthernetClient client, int light, DateTime currently, int Soil, float hum, float Tan, float Td1, float Td2, float Td3, float Td4, float Troom, boolean fanStat, boolean heatStat) {
  client.print(warning);
  
  if (!lighton) {
      client.print("Night, ");
      if (light>100) {
        client.print("(!Light leak!), ");
      }
    } else {
      client.print("Day, ");
      if (light<100) {
       client.print("(!Broken lamps!), ");
      }
    }
    
//  // Light sensor...
//  if (light>100) {      // light in the room
//    if (!lighton) {
//      client.print(" !Light leak! ");
//    } else {
//      client.print("Day__ ");
//    }
//  } else {     // darkness
//    if (lighton) {
//      client.print(" !Broken lamps! ");
//    } else {
//      client.print("Night__ ");
//    }
//  } 

  client.print(currently.month(), DEC);
  client.print('/');
  client.print(currently.day(), DEC);
  client.print(' ');
  client.print(currently.hour(), DEC);
  client.print(':');
  client.print(currently.minute(), DEC);
  client.print(':');
  client.print(currently.second(), DEC);
  client.print("<br/>");
  
  client.print("Soil: "); 
  client.print(Soil);
  client.print("  ");
  
  client.print("<br/>Light: "); 
  client.print(light);
  client.print("  ");
  
  client.print("<br/>Humidity: <b>"); 
  client.print(hum, 1);
  client.print("%</b>");
//  client.print("(");
//  client.print(minHum);
//  client.print("~");
//  client.print(maxHum);
//  client.print(") %  ");

  client.print("<br/>Troom: <b>"); 
  client.print(Troom, 1);
  client.print(" *C </b>"); 
  if (fanStat) {
    client.print("<span style=\"color:blue;\"> fan</span>");
  }
  if (heatStat) {
    client.print("<span style=\"color:red;\"> heat</span>");
  }
  
  client.print("<br/>T(A_D): "); 
  client.print(Tan, 1);
  client.print("(");
//  client.print(minTemp);
//  client.print("~");
//  client.print(maxTemp);  
//  client.print(")_");
  
  client.print(Td1, 2); // Why "byIndex"? You can have more than one IC on the same bus. 0 refers to the first IC on the wire
  client.print("/"); // Why "byIndex"? You can have more than one IC on the same bus. 0 refers to the first IC on the wire
  client.print(Td2, 2); // Why "byIndex"? You can have more than one IC on the same bus. 0 refers to the first IC on the wire
  client.print("/"); // Why "byIndex"? You can have more than one IC on the same bus. 0 refers to the first IC on the wire
  client.print(Td3, 2); // Why "byIndex"? You can have more than one IC on the same bus. 0 refers to the first IC on the wire
  client.print("/"); // Why "byIndex"? You can have more than one IC on the same bus. 0 refers to the first IC on the wire
  client.print(Td4, 2); // Why "byIndex"? You can have more than one IC on the same bus. 0 refers to the first IC on the wire
  client.println(") *C<br/>");
  
}

float StrToFloat(String str){   // http://forums.adafruit.com/viewtopic.php?f=8&t=22083
  char carray[str.length() + 1]; //determine size of the array
  str.toCharArray(carray, sizeof(carray)); //put str into an array
  return atof(carray);
}

boolean TsensorOk(float reading) {
  if (reading<85 && reading>-127) { // I have seen these errors on Dallas sensors
    return 1;
  } else {
    return 0;
  }
}

void loop(){
  /******************** SENSOR READING ******************/
    DateTime currently = RTC.now();
  int Soil = analogRead(MQ2_Pin);
  int light = analogRead(lightSensorPin);
  float Tan = dht.readTemperature();
  float hum = dht.readHumidity();
  
  sensors.requestTemperatures(); // Send the command to get temperatures
  float Td1 = sensors.getTempCByIndex(0); // 0 refers to the first IC on the wire
  float Td2 = sensors.getTempCByIndex(1); // 0 refers to the first IC on the wire
  float Td3 = sensors.getTempCByIndex(2); // 0 refers to the first IC on the wire
  float Td4 = sensors.getTempCByIndex(3); // 0 refers to the first IC on the wire
 
  float Troom = (Td4*TsensorOk(Td4)+Td2*TsensorOk(Td2))/(TsensorOk(Td4)+TsensorOk(Td2));
  
  //SOS shut down everything
  if (Troom >= tempSOS) {
    setRelay(Relay1, 0);
    SOScounter += 1;
  } else {
    if ( Troom<(tempSOS-tempSOSdiff) && SOScounter < maxLightReboots ) {
      setRelay(Relay1, 1);
    }
  }
      
  // Fan Controller 
  if ( TsensorOk(Troom) ) {  
    if (Troom >= tempDayMin) {
      fanTStat = 1;
    } else {
      if (Troom < (tempDayMin-tempDayDiff)) { //if temperature too low (at Day, but no fan at night)
      fanTStat = 0;
      }
    }
  } else {  // if the sensors are out, fan should be on
    fanTStat = 1;
  }
  
  if (hum >= humMax) {
    fanHumStat = 1;
  } else {
    if ( hum > 0 && hum < (humMax-humDiff) ) {
      fanHumStat = 0;
    }       
  }  
  
  boolean fanStat = fanTStat || fanHumStat;
  setRelay(Relay2, fanStat);
  
  // Heater controller
  if (Troom <= tempNightMin) {
    heatStat = 1;
  } else {
    if (Troom > (tempNightMin + tempDayDiff) || light > senseNoLight) {  // same diff with day...
      heatStat = 0;
    }
//  Serial.print(digitalRead(Relay4));
  }
  setRelay(Relay3, heatStat);
    
//  maxTemp = max(maxTemp, t);
//  minTemp = min(minTemp, t);
//  maxHum = max(maxHum, h);
//  minHum = min(minHum, h);
  
// Soil sensor...
//  if (gas > 400) {
//    digitalWrite(ledPin, HIGH);
//    digitalWrite(Relay2, HIGH);     //master relay (fans, lights)
//    char warning[ ] = "GAS leak!!!";
//  } else {
//    digitalWrite(ledPin, LOW); // turn LED OFF
//    digitalWrite(Relay2, LOW);
//    char warning[ ] = "";  //used for gas leak!
//  }

// Lights on Relay 1...
//  if (timerIsOn(currently, lightonhour, lightonmin, lighttotalmin)) {
//    if (lighton == 0) {  
//      Serial.println("Turning on the lights...");
//    }
//    setRelay(Relay4, 1);
//    lighton = 1;
//  } else {
//    if (lighton == 1) {
//      Serial.println("Turning off the lights...");
//    }
//    setRelay(Relay4, 0);
//    lighton = 0;
//  }
  /*****************************************************************************/
  
  //serial dump sensor readings:
  Serial.print(Soil);
  Serial.print(" soil | ");
  Serial.print(light);
  Serial.print(" fire | ");
  Serial.print(hum);
  Serial.print(" % | ");
  Serial.print(Troom);
  Serial.print("Troom | "); 
  Serial.print(Tan);
  Serial.print(" Tan | ");
  Serial.print(Td1);
  Serial.print(" Td1 | ");
  Serial.print(Td2);
  Serial.print(" Td2 | ");
  Serial.print(Td3);
  Serial.print(" Td3 | ");
  Serial.print(Td4);
  Serial.print(" Td4 | ");
//  Serial.print(currently);
  Serial.print(currently.month(), DEC);
  Serial.print("/");
  Serial.print(currently.day(), DEC);
  Serial.print(" ");
  Serial.print(currently.hour(), DEC);
  Serial.print(":");
  Serial.print(currently.minute(), DEC);
  Serial.print(":");
  Serial.println(currently.second(), DEC);
//  Serial.print(" | ");

  // check for serial input
  if (Serial.available() > 0) 
  {
    byte inChar;
    inChar = Serial.read();
    if(inChar == 'g')
    {
      sendGET(light, currently, Soil, hum, Tan, Td1, Td2, Td3, Td4); // call client sendGET function
    }
  }  
  
  // if you're not connected, and ten seconds have passed since
  // your last connection, then connect again and send data:  
  if(!client.connected() && (millis() - lastConnectionTime > postingInterval*4)) { //2 minutes logging period
    Serial.println((millis() - lastConnectionTime > postingInterval));
    sendGET(light, currently, Soil, hum, Tan, Td1, Td2, Td3, Td4); // call client sendGET function
  }
  lastConnected = client.connected();

  // Incoming connections
  EthernetClient client = server.available();
  if (client) {
    while (client.connected()) {
      if (client.available()) {
        char c = client.read();

        //read char by char HTTP request
        if (readString.length() < 100) {

          //store characters to string 
          readString += c; 
          //Serial.print(c);
        } 

        //if HTTP request has ended
        if (c == '\n') {

          ///////////////
          Serial.print(readString); //print to serial monitor for debuging 

          // Changing environment limit values 
          // http://forum.arduino.cc/index.php/topic,8685.0.html
          if(readString.indexOf('?') >=0 && readString.indexOf("c") >0) {
            int Pos_c = readString.indexOf("c");
            int Pos_d = readString.indexOf("d");
            int Pos_h = readString.indexOf("h");
            int Pos_w = readString.indexOf("w");
            int Pos_e = readString.indexOf("e");
            int End = readString.indexOf("H");
            float Tcool = StrToFloat(readString.substring((Pos_c+2), (Pos_d-1))); 
            if ( Tcool <= 30 && Tcool >= 15 ) {
              tempDayMin = Tcool;
            } 
            float Tdiff = StrToFloat(readString.substring((Pos_d+2), (Pos_h-1)));
            if ( Tdiff > 0 && Tdiff < 4 ) {
              tempDayDiff = Tdiff;
            }
            float Theat = StrToFloat(readString.substring((Pos_h+2), (Pos_w-1)));
            if ( Theat > 10 & Theat <= 25 ) {
              if ( Theat + Tdiff < Tcool ) { // no heating && cooling
                tempNightMin = Theat;
              } else {
                tempNightMin = tempDayMin - tempDayDiff; 
              }
            }  
            float humfoo = StrToFloat(readString.substring((Pos_w+2), (Pos_e+2)));
            if ( humfoo >= 0 & humfoo <= 100 ) {
              humMax = humfoo;
            }  
            float humfoo2 = StrToFloat(readString.substring((Pos_e+2), (End-1)));
            if ( humfoo2 > 0 & humfoo2 <= 40 ) {
              humDiff = humfoo2;
            }  
           }          
            //now output HTML data header
//          if(readString.indexOf('?') >=0) { //don't send new page
//            client.println(F("HTTP/1.1 204 Zoomkat"));
//            client.println();
//            client.println();  
//          }
//          else {   
          client.println(F("HTTP/1.1 200 OK")); //send new page on browser request
          client.println(F("Content-Type: text/html"));
          client.println();

          client.println(F("<HTML>"));
          client.println(F("<HEAD>"));
          client.println(F("<TITLE>GH controller</TITLE>"));
          
          client.println(F("<SCRIPT language=\"JavaScript\">"));
          client.println(F("function httpGet(theUrl) {"));
          client.println(F("var xmlHttp = null;"));
          client.println(F("xmlHttp = new XMLHttpRequest();"));
          client.println(F("xmlHttp.open( \"GET\", theUrl, false );"));
          client.println(F("xmlHttp.send( null );"));
          client.println(F("return xmlHttp.responseText;}"));
          client.println(F("</SCRIPT>"));       
          
          client.println(F("</HEAD>"));
          client.println(F("<BODY>"));
          
          // print sensor info (helper)
          CurrentSensors(client, light, currently, Soil, hum, Tan, Td1, Td2, Td3, Td4, Troom, fanStat, heatStat); 
              
          // Adjusting values form

          client.print("<form onsubmit=\"httpGet("); //for javascript call specifically myip
          client.print(myip);
          client.print(");\">");
//          client.print("<form method=get>");
          client.print("Tcool:<input type=text size=3 name=c value=");
          client.print(tempDayMin);
          client.print(">Tdiff:<input type=text size=3 name=d value=");
          client.print(tempDayDiff);
          client.print(">Theat:<input type=text size=3 name=h value=");
          client.print(tempNightMin);
          client.print("><br/>Hum:<input type=text size=3 name=w value=");
          client.print(humMax);
          client.print(">Hdiff:<input type=text size=3 name=e value=");
          client.print(humDiff);
          client.println(">&nbsp;<input name=H type=submit value=submit></form>");   

//          // DIY buttons
//          client.println(F("Pin4"));
//          client.println(F("<a href=/?on2 target=inlineframe>ON</a>")); 
//          client.println(F("<a href=/?off3 target=inlineframe>OFF</a><br><br>")); 
//
//          client.println(F("Pin5"));
//          client.println(F("<a href=/?on4 target=inlineframe>ON</a>")); 
//          client.println(F("<a href=/?off5 target=inlineframe>OFF</a><br><br>")); 
//
//          client.println(F("Pin6"));
//          client.println(F("<a href=/?on6 target=inlineframe>ON</a>")); 
//          client.println(F("<a href=/?off7 target=inlineframe>OFF</a><br><br>")); 
//
//          client.println(F("Pin7"));
//          client.println(F("<a href=/?on8 target=inlineframe>ON</a>")); 
//          client.println(F("<a href=/?off9 target=inlineframe>OFF</a><br><br>")); 
//
//          client.println(F("Pins"));
//          client.println(F("&nbsp;<a href=/?off2468 target=inlineframe>ALL ON</a>")); 
//          client.println(F("&nbsp;<a href=/?off3579 target=inlineframe>ALL OFF</a><br><br>")); 
//
//            
//            
//                      // mousedown buttons
//          client.println(F("<input type=button value=ON onmousedown=location.href='/?on4;' target=inlineframe>")); 
//          client.println(F("<input type=button value=OFF onmousedown=location.href='/?off5;' target=inlineframe>"));        
//          client.println(F("&nbsp;<input type=button value='ALL OFF' onmousedown=location.href='/?off3579;' target=inlineframe><br><br>"));        
//                   
//          // mousedown radio buttons
//          client.println(F("<input type=radio onmousedown=location.href='/?on6;' target=inlineframe>ON</>")); 
//          client.println(F("<input type=radio onmousedown=location.href='/?off7; target=inlineframe'>OFF</>")); 
//          client.println(F("&nbsp;<input type=radio onmousedown=location.href='/?off3579;' target=inlineframe>ALL OFF</><br><br>"));    
//   
//          
//          // custom buttons
//          client.print(F("<input type=submit value=ON target=inlineframe style=width:100px;height:45px onClick=location.href='/?on8;'>"));
//          client.print(F("<input type=submit value=OFF target=inlineframe style=width:100px;height:45px onClick=location.href='/?off9;' target=inlineframe>"));
//          client.print(F("&nbsp;<input type=submit value='ALL OFF' target=inlineframe style=width:100px;height:45px onClick=location.href='/?off3579;' target=inlineframe>"));
//
//            
//          client.println(F("<IFRAME name=inlineframe style='display:none'>"));          
//          client.println(F("</IFRAME>"));
//
//          client.println(F("</BODY>"));
//          client.println(F("</HTML>"));
//          }

          delay(1);
          //stopping client
          client.stop();
          
//          ///////////////////// control arduino pin
//          if(readString.indexOf('2') >0)//checks for 2
//          {
//            digitalWrite(5, HIGH);    // set pin 5 high
//            Serial.println("Led 5 On");
//            Serial.println();
//          }
//          if(readString.indexOf('3') >0)//checks for 3
//          {
//            digitalWrite(5, LOW);    // set pin 5 low
//            Serial.println("Led 5 Off");
//            Serial.println();
//          }
//          if(readString.indexOf('4') >0)//checks for 4
//          {
//            digitalWrite(6, HIGH);    // set pin 6 high
//            Serial.println("Led 6 On");
//            Serial.println();
//          }
//          if(readString.indexOf('5') >0)//checks for 5
//          {
//            digitalWrite(6, LOW);    // set pin 6 low
//            Serial.println("Led 6 Off");
//            Serial.println();
//          }
//          if(readString.indexOf('6') >0)//checks for 6
//          {
//            digitalWrite(7, HIGH);    // set pin 7 high
//            Serial.println("Led 7 On");
//            Serial.println();
//          }
//          if(readString.indexOf('7') >0)//checks for 7
//          {
//            digitalWrite(7, LOW);    // set pin 7 low
//            Serial.println("Led 7 Off");
//            Serial.println();
//          }     
//          if(readString.indexOf('8') >0)//checks for 8
//          {
//            digitalWrite(8, HIGH);    // set pin 8 high
//            Serial.println("Led 8 On");
//            Serial.println();
//          }
//          if(readString.indexOf('9') >0)//checks for 9
//          {
//            digitalWrite(8, LOW);    // set pin 8 low
//            Serial.println("Led 8 Off");
//            Serial.println();
//          }         

          //clearing string for next read
          readString="";

        }
      }
    }
  }
} 

//////////////////////////
void sendGET(int light, DateTime currently, int Soil, float hum, float Tan, float Td1, float Td2, float Td3, float Td4) //client function to send and receive GET data from external server.
{
  if (client.connect(serverName, 80)) {
    Serial.println("connected");
    // send the HTTP PUT request:
    client.print("GET /cgi-bin/MongoServer.py?");
    client.print("Controller=");
    client.print(identification);
    client.print("&&");
    client.print("month=");
    client.print(currently.month(), DEC);
    client.print("&&");
    client.print("day=");
    client.print(currently.day(), DEC);
    client.print("&&");
    client.print("time=");
    String timestr = String(currently.hour());
    timestr =  timestr + ':' + currently.minute() + ':' +String(currently.second());
    client.print(timestr);    
    client.print("&&");
    client.print("Soil="); 
    client.print(Soil);
    client.print("&&");    
    client.print("Light="); 
    client.print(light);
    client.print("&&");    
    client.print("Humidity="); 
    client.print(hum, 1);
    client.print("&&");
    client.print("Tanalog=");
    client.print(Tan, 1);
    client.print("&&");
    client.print("Tdigital1="); 
    client.print(Td1, 2);
    client.print("&&");
    client.print("Tdigital2="); 
    client.print(Td2, 2);
    client.print("&&");
    client.print("Tdigital3="); 
    client.print(Td3, 2);
    client.print("&&");
    client.print("Tdigital4="); 
    client.print(Td4, 2);
    client.print("&&");

    client.println(" HTTP/1.1");
    client.println("Host: 192.168.1.7");
    client.println("User-Agent: arduino-ethernet");
    client.println("Connection: close");
    client.println();
    
    // note the time that the connection was made:
    lastConnectionTime = millis();
  } 
  else {
    Serial.println("connection failed");
    Serial.println();
    lastConnectionTime = millis()-postingInterval/2;
  }

  while(client.connected() && !client.available()) delay(1); //waits for data
  while (client.connected() || client.available()) { //connected or data available
    char c = client.read();
    Serial.print(c);
  }

  Serial.println();
  Serial.println("disconnecting.");
  Serial.println("==================");
  Serial.println();
  client.stop();

}
