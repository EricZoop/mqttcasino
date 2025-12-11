#include "counting_strategies.h"
#include <Arduino.h>

// Get the count value for a card based on the selected strategy
// https://www.qfit.com/card-counting.htm

double getCardValue(char card, CountingStrategy strategy) {
  switch (strategy) {
    case HILO:
      return (double)getHiLoValue(card);
    
    case OMEGA_II:
      return (double)getOmegaIIValue(card);

    case HALVES: 
      return getHalvesValue(card);
    
    default:
      return 0.0;
  }
}

// Hi-Lo System
// 2-6 = +1, 7-9 = 0, T-A = -1
int getHiLoValue(char card) {
  switch (card) {
    case 'A':
    case 'K':
    case 'Q':
    case 'J':
    case 'T':
      return -1;
      
    case '6':
    case '5':
    case '4':
    case '3':
    case '2':
      return 1;
      
    default:
      return 0; // 7, 8, 9
  }
}

// Omega II System
// 2,3,7 = +1, 4,5,6 = +2, 8,A = 0, 9 = -1, T,J,Q,K = -2
int getOmegaIIValue(char card) {
  switch (card) {
    case 'K':
    case 'Q':
    case 'J':
    case 'T':
      return -2;
      
    case '9':
      return -1;
      
    case '8':
    case 'A':
      return 0;
      
    case '7':
    case '3':
    case '2':
      return 1;
      
    case '6':
    case '5':
    case '4':
      return 2;
      
    default:
      return 0;
  }
}

// Halves System
// 2, 7 = +0.5, 3, 4, 6 = +1, 5 = +1.5, 8 = 0, 9 = -0.5, T,J,Q,K,A = -1
double getHalvesValue(char card) {
  switch (card) {
    case 'A':
    case 'K':
    case 'Q':
    case 'J':
    case 'T':
      return -1.0;
      
    case '9':
      return -0.5;
      
    case '8':
      return 0.0;
      
    case '7':
    case '2':
      return 0.5;
      
    case '6':
    case '4':
    case '3':
      return 1.0;
      
    case '5':
      return 1.5;
      
    default:
      return 0.0;
  }
}

// Get strategy name for display
String getStrategyName(CountingStrategy strategy) {
  switch (strategy) {
    case HILO:
      return "Hi-Lo";
    case OMEGA_II:
      return "Omega II";
    case HALVES:
      return "Halves";
    default:
      return "Unknown";
  }
}