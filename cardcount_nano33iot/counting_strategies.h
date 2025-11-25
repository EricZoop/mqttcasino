/*
 * Card Counting Strategies Library - Header File
 * Contains different card counting systems for blackjack
 */

#ifndef COUNTING_STRATEGIES_H
#define COUNTING_STRATEGIES_H

#include <Arduino.h>

// Strategy types
enum CountingStrategy {
  HILO = 0,
  OMEGA_II = 1
};

// FUNCTION PROTOTYPES
int getCardValue(char card, CountingStrategy strategy);
int getHiLoValue(char card);
int getOmegaIIValue(char card);
String getStrategyName(CountingStrategy strategy);

#endif // COUNTING_STRATEGIES_H