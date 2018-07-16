#include "EmonLib.h"                   // Include Emon Library
EnergyMonitor emon0;                   // Create an instance
EnergyMonitor emon1;                   // Create an instance
EnergyMonitor emon2;                   // Create an instance

void setup()
{  
  Serial.begin(115200);
  
  emon0.current(0, 61.5);             // Current: input pin, calibration = 2000/Rburden. (Rburden=Vcc/2/0.0707
  emon1.current(1, 61.5);             
  emon2.current(2, 61.5);             
}

void loop()
{
  double Irms0 = emon0.calcIrms(1480);  // Calculate Irms only
  double Irms1 = emon1.calcIrms(1480);  // Calculate Irms only
  double Irms2 = emon2.calcIrms(1480);  // Calculate Irms only
  
//  Serial.print(Irms*230.0);	       // Apparent power
//  Serial.print(" ");
  Serial.print("I1=");
  Serial.print(Irms0);		       // Irms
  Serial.print(";I2=");
  Serial.print(Irms1);		       // Irms
  Serial.print(";I3=");
  Serial.print(Irms2);		       // Irms
  Serial.println(";");
}
