let gameState = null;
let previousState = null;

function createCard(rank, hidden = false, shouldAnimate = true) {
    const card = document.createElement('div');
    card.className = 'card';
    
    if (shouldAnimate) {
        card.style.opacity = '0';
        card.style.transform = 'translateX(-20px) translateY(-15px) rotate(-3deg) scale(0.9)';
        setTimeout(() => {
            card.classList.add('card-enter');
        }, 10);
    } else {
        card.style.opacity = '1';
        card.style.transform = 'translateX(0) translateY(0) rotate(0deg) scale(1)';
    }

    const img = document.createElement('img');
    img.className = 'card-image';

    if (hidden) {
        img.src = '/static/images/back.png';
        img.alt = 'Hidden Card';
    } else {
        const suitMap = {
            'H': 'hearts',
            'D': 'diamonds',
            'C': 'clubs',
            'S': 'spades'
        };
        
        const suitChar = rank.slice(-1);
        const suitFolder = suitMap[suitChar] || 'hearts';
        img.src = `/static/images/${suitFolder}/${rank}.png`; 
        
        const rankMap = {
            'A': 'Ace', 'K': 'King', 'Q': 'Queen', 'J': 'Jack', 'T': '10',
            '9': '9', '8': '8', '7': '7', '6': '6', '5': '5', '4': '4', '3': '3', '2': '2'
        };
        const rankValue = rank.slice(0, -1);
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

    const status = handData.status.charAt(0).toUpperCase() + handData.status.slice(1);
    
    handContainer.innerHTML = `
    <span class="hand-value">${handData.value}</span>
        <div class="cards-container" id="player-cards-${index}">
        </div>
        
        <div class="hand-title">
            
            <span class="hand-bet">$${handData.bet}</span>
        </div>
    `;
    
    const cardsContainer = handContainer.querySelector(`#player-cards-${index}`);
    const previousHandLength = previousHand ? previousHand.hand.length : 0;
    
    handData.hand.forEach((card, cardIndex) => {
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
    
    // Update bank display
    document.getElementById('bank-amount').textContent = `$${state.bank}`;
    
    // Update cards remaining
    document.getElementById('cards-remaining').textContent = state.cards_remaining || 312;
    
    // Update dealer's cards
    const dealerCards = document.getElementById('dealer-cards');
    dealerCards.innerHTML = '';
    
    const dealerValueElement = document.getElementById('dealer-value');
    
    if (state.dealer_hand && state.dealer_hand.length > 0) {
        state.dealer_hand.forEach((card, index) => {
            const isNewCard = index >= previousDealerHand.length;
            const wasHidden = previousState && previousState.dealer_hidden && index === 0;
            const nowRevealed = !state.dealer_hidden && index === 0 && wasHidden;
            
            const shouldAnimate = isNewCard || nowRevealed;
            
            if (index === 0 && state.dealer_hidden) {
                dealerCards.appendChild(createCard(card, true, shouldAnimate));
            } else {
                dealerCards.appendChild(createCard(card, false, shouldAnimate));
            }
        });
        
        dealerValueElement.textContent = 
            state.dealer_hidden ? CARD_VALUES[state.dealer_hand[1].slice(0, -1)] : state.dealer_value;
        dealerValueElement.style.display = '';  // <-- ADDED: Show the value when cards exist
    } else {
        dealerValueElement.textContent = '0';
        dealerValueElement.style.display = 'none';  // <-- ADDED: Hide the value when no cards
    }
    
    // Update player's cards
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
    document.getElementById('bet-input').disabled = playing;
    document.querySelectorAll('.bet-quick').forEach(btn => btn.disabled = playing);
    document.getElementById('reset-bank-btn').disabled = playing;
    
    // Enable/disable split and double
    document.getElementById('double-btn').disabled = !state.can_double;
    document.getElementById('split-btn').disabled = !state.can_split;
    
    // Store current state for next comparison
    previousState = JSON.parse(JSON.stringify(state));

    if (state.game_status === 'dealer_turn') {
        // Disable all buttons while dealer is playing
        document.getElementById('hit-btn').disabled = true;
        document.getElementById('stand-btn').disabled = true;
        document.getElementById('double-btn').disabled = true;
        document.getElementById('split-btn').disabled = true;

        // Call the next dealer step after 1 second
        setTimeout(dealerStep, 300); 
    }
}

function setBet(amount) {
    const betInput = document.getElementById('bet-input');
    
    // Get the current value from the input, default to 0 if it's empty
    let currentBet = parseInt(betInput.value) || 0;
    
    // Add the new amount
    let newBet = currentBet + amount;
    
    // Ensure the new bet doesn't exceed the player's bank
    betInput.value = Math.min(newBet, gameState.bank);
}

async function deal() {
    try {
        previousState = null;
        
        // Set the bet first
        const betAmount = parseInt(document.getElementById('bet-input').value);
        await fetch('/set_bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ amount: betAmount })
        });
        
        // Then deal
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

async function dealerStep() {
    try {
        const response = await fetch('/dealer_step', { method: 'POST' });
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        const state = await response.json();
        updateDisplay(state); // This will re-trigger the loop if status is still 'dealer_turn'
    } catch (error) {
        console.error('Error during dealer step:', error);
        document.getElementById('status-message').textContent = 'Error during dealer turn.';
    }
}

async function resetBankAndShuffle() {
    try {
        // Reset bank
        await fetch('/reset_bank', { method: 'POST' });
        // Shuffle deck
        const response = await fetch('/shuffle', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error resetting bank and shuffling:', error);
    }
}

// Card values for display
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

async function resetBankAndShuffle() {
    try {
        // Reset bank
        await fetch('/reset_bank', { method: 'POST' });
        // Shuffle deck
        const response = await fetch('/shuffle', { method: 'POST' });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error resetting bank and shuffling:', error);
    }
}

async function updateMqttConfig() {
    try {
        const broker = document.getElementById('mqtt-broker').value;
        const port = parseInt(document.getElementById('mqtt-port').value);
        const topic = document.getElementById('mqtt-topic').value;
        
        const response = await fetch('/update_mqtt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ broker, port, topic })
        });
        
        const result = await response.json();
        if (result.error) {
            alert(result.error);
        } else {
            alert('MQTT configuration updated successfully!');
        }
    } catch (error) {
        console.error('Error updating MQTT config:', error);
        alert('Error updating MQTT configuration');
    }
}