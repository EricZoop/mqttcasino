let gameState = null;
let previousState = null; // Track previous state to detect new cards

function createCard(rank, hidden = false, shouldAnimate = true) {
    const card = document.createElement('div');
    card.className = 'card';
    
    if (shouldAnimate) {
        card.style.opacity = '0'; // Start invisible for animation
        card.style.transform = 'translateX(-20px) translateY(-15px) rotate(-3deg) scale(0.9)';
        // Trigger animation after a brief moment
        setTimeout(() => {
            card.classList.add('card-enter');
        }, 10);
    } else {
        // Card already exists, show immediately with final position
        card.style.opacity = '1';
        card.style.transform = 'translateX(0) translateY(0) rotate(0deg) scale(1)';
    }

    const img = document.createElement('img');
    img.className = 'card-image';

    if (hidden) {
        img.src = '/static/images/back.png'; // Corrected path for back.png
        img.alt = 'Hidden Card';
    } else {
        // Map suit character (H, D, C, S) to folder name
        const suitMap = {
            'H': 'hearts',
            'D': 'diamonds',
            'C': 'clubs',
            'S': 'spades'
        };
        
        // rank is expected to be like "2H", "KS", "AD"
        const suitChar = rank.slice(-1); // Get last character (the suit)
        const suitFolder = suitMap[suitChar] || 'hearts'; // Default to hearts if invalid

        // Construct the correct path e.g., /static/images/clubs/KC.png
        img.src = `/static/images/${suitFolder}/${rank}.png`; 
        
        // Create a more descriptive alt text
        const rankMap = {
            'A': 'Ace', 'K': 'King', 'Q': 'Queen', 'J': 'Jack', 'T': '10',
            '9': '9', '8': '8', '7': '7', '6': '6', '5': '5', '4': '4', '3': '3', '2': '2'
        };
        const rankValue = rank.slice(0, -1); // Get rank part (e.g., "K", "2", "A")
        const altRank = rankMap[rankValue] || rankValue;
        const altSuit = suitMap[suitChar] ? suitMap[suitChar].charAt(0).toUpperCase() + suitMap[suitChar].slice(1) : '';
        
        img.alt = `${altRank} of ${altSuit}`;
    }

    card.appendChild(img);
    return card;
}

function createPlayerHand(handData, index, isActive, previousHand = null) {
    const handContainer = document.createElement('div');
    handContainer.className = 'hand-section player-hand';
    if (isActive) {
        handContainer.classList.add('player-hand-active');
    }

    // Capitalize status
    const status = handData.status.charAt(0).toUpperCase() + handData.status.slice(1);
    
    handContainer.innerHTML = `

        <div class="cards-container" id="player-cards-${index}">
            <!-- Cards for this hand -->
        </div>

        <div class="hand-title">
            <!--<span>Hand ${index + 1}</span>
            <span class="hand-status">${status}</span>-->
            <span class="hand-value">${handData.value}</span>
        </div>
    `;
    
    const cardsContainer = handContainer.querySelector(`#player-cards-${index}`);
    const previousHandLength = previousHand ? previousHand.hand.length : 0;
    
    handData.hand.forEach((card, cardIndex) => {
        // Only animate if this is a new card
        const shouldAnimate = cardIndex >= previousHandLength;
        cardsContainer.appendChild(createCard(card, false, shouldAnimate));
    });
    
    return handContainer;
}

function updateDisplay(state) {
    if (!state || Object.keys(state).length === 0) {
        console.warn("Received empty or invalid state");
        return;
    }
    
    const previousDealerHand = previousState ? previousState.dealer_hand : [];
    const previousPlayerHands = previousState ? previousState.player_hands : [];
    
    gameState = state;
    
    // Update dealer's cards
    const dealerCards = document.getElementById('dealer-cards');
    dealerCards.innerHTML = '';
    
    if (state.dealer_hand && state.dealer_hand.length > 0) {
        state.dealer_hand.forEach((card, index) => {
            // Check if this card existed before
            const isNewCard = index >= previousDealerHand.length;
            // Check if hidden status changed (revealing hole card)
            const wasHidden = previousState && previousState.dealer_hidden && index === 0;
            const nowRevealed = !state.dealer_hidden && index === 0 && wasHidden;
            
            const shouldAnimate = isNewCard || nowRevealed;
            
            if (index === 0 && state.dealer_hidden) {
                dealerCards.appendChild(createCard(card, true, shouldAnimate));
            } else {
                dealerCards.appendChild(createCard(card, false, shouldAnimate));
            }
        });
        
        // Update dealer value
        // Corrected: Extract rank (e.g., "K") from card (e.g., "KH")
        document.getElementById('dealer-value').textContent = 
            state.dealer_hidden ? CARD_VALUES[state.dealer_hand[1].slice(0, -1)] : state.dealer_value;
    } else {
         document.getElementById('dealer-value').textContent = '0';
    }
    
    // Update player's cards - now handles multiple hands
    const playerHands = document.getElementById('player-hands-display');
    playerHands.innerHTML = '';
    if (state.player_hands && state.player_hands.length > 0) {
        state.player_hands.forEach((hand, index) => {
            const isActive = (index === state.active_hand_index);
            const previousHand = previousPlayerHands[index] || null;
            
            playerHands.appendChild(createPlayerHand(hand, index, isActive, previousHand));
        });
    }
    
    // Update status message
    document.getElementById('status-message').textContent = state.message;
    
    // Update button states
    const playing = state.game_status === 'playing';
    document.getElementById('hit-btn').disabled = !playing;
    document.getElementById('stand-btn').disabled = !playing;
    document.getElementById('deal-btn').disabled = playing;
    
    // Enable/disable split and double
    document.getElementById('double-btn').disabled = !state.can_double;
    document.getElementById('split-btn').disabled = !state.can_split;
    
    // Store current state for next comparison
    previousState = JSON.parse(JSON.stringify(state));
}

async function deal() {
    try {
        previousState = null; // Reset on new deal
        const response = await fetch('/deal', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error dealing:', error);
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