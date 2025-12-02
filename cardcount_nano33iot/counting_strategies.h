#ifndef COUNTING_STRATEGIES_H
#define COUNTING_STRATEGIES_H

#include <Arduino.h> // FIX: Added this include to define the String type

// Enum for selecting the card counting strategy
enum CountingStrategy {
  HILO,
  OMEGA_II,
  HALVES
};

// Function declarations
int getHiLoValue(char card);
int getOmegaIIValue(char card);
double getHalvesValue(char card); 

// Get the count value for a card based on the selected strategy
double getCardValue(char card, CountingStrategy strategy); 

// Get strategy name for display
String getStrategyName(CountingStrategy strategy); // No more error on String
#endif // COUNTING_STRATEGIES_H