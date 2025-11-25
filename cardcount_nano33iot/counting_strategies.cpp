#include "counting_strategies.h"

// Get the count value for a card based on the selected strategy
int getCardValue(char card, CountingStrategy strategy) {
  switch (strategy) {
    case HILO:
      return getHiLoValue(card);
    
    case OMEGA_II:
      return getOmegaIIValue(card);
    
    default:
      return 0;
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

// Get strategy name for display
String getStrategyName(CountingStrategy strategy) {
  switch (strategy) {
    case HILO:
      return "Hi-Lo";
    case OMEGA_II:
      return "Omega II";
    default:
      return "Unknown";
  }
}