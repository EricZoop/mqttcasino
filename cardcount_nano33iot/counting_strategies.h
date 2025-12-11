#ifndef COUNTING_STRATEGIES_H
#define COUNTING_STRATEGIES_H

#include <Arduino.h> 

// Enum counting strategy
enum CountingStrategy {
  HILO,
  OMEGA_II,
  HALVES
};

// Function declarations
int getHiLoValue(char card);
int getOmegaIIValue(char card);
double getHalvesValue(char card); 

double getCardValue(char card, CountingStrategy strategy); 
String getStrategyName(CountingStrategy strategy); 

#endif // COUNTING_STRATEGIES_H