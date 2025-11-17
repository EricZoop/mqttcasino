let gameState = null;
let previousState = null;
let sessionId = null;

// Generate a unique session ID for this tab (doesn't persist)
function getSessionId() {
    if (!sessionId) {
        // Generate a new unique session ID for this tab
        sessionId = generateSessionId();
    }
    return sessionId;
}

function generateSessionId() {
    // Generate a random hex string (similar to what the server does)
    const array = new Uint8Array(16);
    crypto.getRandomValues(array);
    return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

function setSessionId(newSessionId) {
    sessionId = newSessionId;
}

async function initSession() {
    try {
        const response = await fetch('/init_session', { method: 'POST' });
        const result = await response.json();
        
        setSessionId(result.session_id);
        
        // Update MQTT config fields
        document.getElementById('mqtt-broker').value = result.broker;
        document.getElementById('mqtt-port').value = result.port;
        document.getElementById('mqtt-topic').value = result.topic;
        
        return result.session_id;
    } catch (error) {
        console.error('Error initializing session:', error);
        return null;
    }
}

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
    
    let betColorClass = '';
    let betPrefix = '';
    if (handData.status === 'lose' || handData.status === 'bust') {
        betColorClass = 'bet-loss';
        betPrefix = '-';
    } else if (handData.status === 'win' || handData.status === 'blackjack') {
        betColorClass = 'bet-win';
    }
    
    handContainer.innerHTML = `
    <span class="hand-value">${handData.value}</span>
        <div class="cards-container" id="player-cards-${index}">
        </div>
        
        <div style="margin-top: .5rem;">
            
            <span class="hand-bet ${betColorClass}">${betPrefix}$${handData.bet}</span>
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

function animateValue(element, start, end, duration) {
    if (start === end) {
        element.textContent = `$${end}`;
        return;
    }

    let startTime = null;

    const step = (timestamp) => {
        if (!startTime) startTime = timestamp;
        const progress = Math.min((timestamp - startTime) / duration, 1);
        
        const currentValue = Math.floor(progress * (end - start) + start);

        element.textContent = `$${currentValue}`;

        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            element.textContent = `$${end}`; 
        }
    };

    window.requestAnimationFrame(step);
}

function updateDisplay(state) {
    if (!state || Object.keys(state).length === 0) {
        console.warn("Received empty or invalid state");
        return;
    }
    
    const previousDealerHand = previousState ? previousState.dealer_hand : [];
    const previousPlayerHands = previousState ? previousState.player_hands : [];
    
    gameState = state;
    
    const bankElement = document.getElementById('bank-amount');
    const newBankValue = state.bank;
    
    const currentText = bankElement.textContent.replace('$', '');
    const startBankValue = parseInt(currentText) || newBankValue; 
    
    animateValue(bankElement, startBankValue, newBankValue, 350);
    
    document.getElementById('cards-remaining').textContent = state.cards_remaining;
    
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
        dealerValueElement.style.display = '';
    } else {
        dealerValueElement.textContent = '0';
        dealerValueElement.style.display = 'none';
    }
    
    const playerHands = document.getElementById('player-hands-display');
    playerHands.innerHTML = '';
    if (state.player_hands && state.player_hands.length > 0) {
        state.player_hands.forEach((hand, index) => {
            const isActive = (index === state.active_hand_index);
            const previousHand = previousPlayerHands[index] || null;
            
            playerHands.appendChild(createPlayerHand(hand, index, isActive, previousHand));
        });
    }
    
    document.getElementById('status-message').textContent = state.message;
    
    const playing = state.game_status === 'playing';
    document.getElementById('hit-btn').disabled = !playing;
    document.getElementById('stand-btn').disabled = !playing;
    document.getElementById('deal-btn').disabled = playing;
    document.getElementById('bet-input').disabled = playing;
    document.querySelectorAll('.bet-quick').forEach(btn => btn.disabled = playing);
    document.getElementById('reset-bank-btn').disabled = playing;
    //document.getElementById('host-table-btn').disabled = playing;
    document.querySelector('.bet-control').classList.toggle('disabled', playing);
    
    document.getElementById('double-btn').disabled = !state.can_double;
    document.getElementById('split-btn').disabled = !state.can_split;
    
    previousState = JSON.parse(JSON.stringify(state));

    if (state.game_status === 'dealer_turn') {
        document.getElementById('hit-btn').disabled = true;
        document.getElementById('stand-btn').disabled = true;
        document.getElementById('double-btn').disabled = true;
        document.getElementById('split-btn').disabled = true;

        setTimeout(dealerStep, 300); 
    }
}

function setBet(amount) {
    const betInput = document.getElementById('bet-input');
    
    let currentBet = parseInt(betInput.value) || 0;
    
    let newBet = currentBet + amount;
    
    betInput.value = Math.min(newBet, gameState.bank);
}

async function deal() {
    try {
        const sid = getSessionId();
        if (!sid) {
            console.error('No session ID');
            return;
        }
        
        previousState = null;
        
        const betAmount = parseInt(document.getElementById('bet-input').value);
        await fetch('/set_bet', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid, amount: betAmount })
        });
        
        const response = await fetch('/deal', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error dealing:', error);
        document.getElementById('status-message').textContent = 'Error starting game. Please try again.';
    }
}

async function hit() {
    try {
        const sid = getSessionId();
        if (!sid) return;
        
        const response = await fetch('/hit', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error hitting:', error);
    }
}

async function stand() {
    try {
        const sid = getSessionId();
        if (!sid) return;
        
        const response = await fetch('/stand', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error standing:', error);
    }
}

async function doubleDown() {
    try {
        const sid = getSessionId();
        if (!sid) return;
        
        const response = await fetch('/double', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error doubling:', error);
    }
}

async function split() {
    try {
        const sid = getSessionId();
        if (!sid) return;
        
        const response = await fetch('/split', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error splitting:', error);
    }
}

async function dealerStep() {
    try {
        const sid = getSessionId();
        if (!sid) return;
        
        const response = await fetch('/dealer_step', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error during dealer step:', error);
        document.getElementById('status-message').textContent = 'Error during dealer turn.';
    }
}

async function resetBankAndShuffle() {
    try {
        const sid = getSessionId();
        if (!sid) return;
        
        await fetch('/reset_bank', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const response = await fetch('/shuffle', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid })
        });
        const state = await response.json();
        updateDisplay(state);
    } catch (error) {
        console.error('Error resetting bank and shuffling:', error);
    }
}

async function hostTable() {
    try {
        const response = await fetch('/host_table', { method: 'POST' });
        const result = await response.json();
        
        if (result.error) {
            document.getElementById('status-message').textContent = `Error: ${result.error}`;
            return;
        }
        
        // Set the new session ID for THIS tab
        setSessionId(result.session_id);
        
        // Update MQTT config fields with new table info
        document.getElementById('mqtt-broker').value = result.broker;
        document.getElementById('mqtt-port').value = result.port;
        document.getElementById('mqtt-topic').value = result.topic;
        
        // Reload the game state for this new session
        const stateResponse = await fetch(`/state?session_id=${result.session_id}`);
        const state = await stateResponse.json();
        
        previousState = null;
        updateDisplay(state);
        
        document.getElementById('status-message').textContent = 
            `New table hosted! Session: ${result.session_id.substring(0, 8)} | Topic: ${result.topic}`;
    } catch (error) {
        console.error('Error hosting table:', error);
        document.getElementById('status-message').textContent = 'Error creating new table';
    }
}

const CARD_VALUES = {
    'A': 11, 'K': 10, 'Q': 10, 'J': 10, 'T': 10,
    '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2
};

window.onload = async function() {
    try {
        // Always create a new session for this tab
        const sid = await initSession();
        
        const response = await fetch(`/state?session_id=${sid}`);
        const state = await response.json();
        
        // Update MQTT config fields if provided
        if (state.mqtt_config) {
            document.getElementById('mqtt-broker').value = state.mqtt_config.broker;
            document.getElementById('mqtt-port').value = state.mqtt_config.port;
            document.getElementById('mqtt-topic').value = state.mqtt_config.topic;
        }
        
        updateDisplay(state);
    } catch (error) {
        console.error('Error loading state:', error);
    }
};

async function updateMqttConfig() {
    const statusEl = document.getElementById('status-message');

    try {
        const sid = getSessionId();
        if (!sid) return;
        
        const broker = document.getElementById('mqtt-broker').value;
        const port = parseInt(document.getElementById('mqtt-port').value);
        const topic = document.getElementById('mqtt-topic').value;
        
        const response = await fetch('/update_mqtt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sid, broker, port, topic })
        });
        
        const result = await response.json();
        if (result.error) {
            statusEl.textContent = `MQTT Error: ${result.error}`;
        } else {
            statusEl.textContent = 'MQTT configuration updated successfully!';
        }
    } catch (error) {
        console.error('Error updating MQTT config:', error);
        statusEl.textContent = 'Error updating MQTT configuration';
    }
}