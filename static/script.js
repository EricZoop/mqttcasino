let gameState = null;

function createCard(rank, hidden = false) {
    const card = document.createElement('div');
    card.className = 'card card-enter';

    const img = document.createElement('img');
    img.className = 'card-image';

    if (hidden) {
        img.src = '/static/images/cards/back.png';
        img.alt = 'Hidden Card';
    } else {
        img.src = `/static/images/cards/${rank}.png`;
        img.alt = `${rank} of cards`;
    }

    card.appendChild(img);
    return card;
}

function createPlayerHand(handData, index, isActive) {
    const handContainer = document.createElement('div');
    handContainer.className = 'hand-section player-hand';
    if (isActive) {
        handContainer.classList.add('player-hand-active');
    }

    // Capitalize status
    const status = handData.status.charAt(0).toUpperCase() + handData.status.slice(1);
    
    handContainer.innerHTML = `
        <div class="hand-title">
            <span>Hand ${index + 1}</span>
            <span class="hand-status">${status}</span>
            <span class="hand-value">${handData.value}</span>
        </div>
        <div class="cards-container" id="player-cards-${index}">
            <!-- Cards for this hand -->
        </div>
    `;
    
    const cardsContainer = handContainer.querySelector(`#player-cards-${index}`);
    handData.hand.forEach(card => {
        cardsContainer.appendChild(createCard(card));
    });
    
    return handContainer;
}

function updateDisplay(state) {
    if (!state || Object.keys(state).length === 0) {
        console.warn("Received empty or invalid state");
        return;
    }
    gameState = state;
    
    // Update dealer's cards
    const dealerCards = document.getElementById('dealer-cards');
    dealerCards.innerHTML = '';
    
    if (state.dealer_hand && state.dealer_hand.length > 0) {
        state.dealer_hand.forEach((card, index) => {
            if (index === 0 && state.dealer_hidden) {
                dealerCards.appendChild(createCard(card, true));
            } else {
                dealerCards.appendChild(createCard(card));
            }
        });
        
        // Update dealer value
        document.getElementById('dealer-value').textContent = 
            state.dealer_hidden ? CARD_VALUES[state.dealer_hand[1]] : state.dealer_value;
    } else {
         document.getElementById('dealer-value').textContent = '0';
    }
    
    // Update player's cards - now handles multiple hands
    const playerHands = document.getElementById('player-hands-display');
    playerHands.innerHTML = '';
    if (state.player_hands && state.player_hands.length > 0) {
        state.player_hands.forEach((hand, index) => {
            const isActive = (index === state.active_hand_index);
            playerHands.appendChild(createPlayerHand(hand, index, isActive));
        });
    }
    
    // Update status message
    document.getElementById('status-message').textContent = state.message;
    
    // Update button states
    const playing = state.game_status === ' Playing';
    document.getElementById('hit-btn').disabled = !playing;
    document.getElementById('stand-btn').disabled = !playing;
    document.getElementById('deal-btn').disabled = playing;
    
    // Enable/disable split and double
    document.getElementById('double-btn').disabled = !state.can_double;
    document.getElementById('split-btn').disabled = !state.can_split;
}

async function deal() {
    try {
        const response = await fetch('/deal', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error dealing:', error);
        // Use a non-blocking message
        document.getElementById('status-message').textContent = 'Error starting game. Please try again.';
    }
}

async function hit() {
    try {
        const response = await fetch('/hit', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error hitting:', error);
    }
}

async function stand() {
    try {
        const response = await fetch('/stand', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error standing:', error);
    }
}

async function doubleDown() {
    try {
        const response = await fetch('/double', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error doubling:', error);
    }
}

async function split() {
    try {
        const response = await fetch('/split', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error splitting:', error);
    }
}

// Card values for display (matching Python)
const CARD_VALUES = {
    'A': 11, 'K': 10, 'Q': 10, 'J': 10, 'T': 10,
    '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2
};

// Load initial state on page load
window.onload = async function() {
    try {
        const response = await fetch('/state');
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error loading state:', error);
    }
};