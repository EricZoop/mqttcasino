import paho.mqtt.client as mqtt
from flask import Flask, render_template, jsonify, request
import time
import random
import threading

# --- MQTT Configuration ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "ece508/blackjack_table1"

# --- App Configuration ---
app = Flask(__name__)
mqtt_client = mqtt.Client("flask_blackjack_" + str(time.time()))

# --- Card Configuration ---
CARD_RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
CARD_SUITS = ['H', 'D', 'C', 'S']
CARD_VALUES = {
    'A': 11, 'K': 10, 'Q': 10, 'J': 10, 'T': 10,
    '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2
}
NUMBER_OF_DECKS = 6
MIN_BET = 10
STARTING_BANK = 1000

# --- Game State ---
game_state = {}
current_shoe = []
shoe_lock = threading.Lock()

def reset_game_state():
    """Helper to initialize or reset the game state"""
    global game_state
    game_state = {
        'player_hands': [],
        'active_hand_index': -1,
        'dealer_hand': [],
        'dealer_value': 0,
        'dealer_hidden': True,
        'game_status': 'waiting',
        'message': 'Place your bet to start',
        'can_split': False,
        'can_double': False,
        'current_bet': MIN_BET,
        'bank': STARTING_BANK,
        'cards_remaining': len(current_shoe)
    }

def calculate_hand_value(hand):
    """Calculate the value of a hand, adjusting for aces"""
    value = 0
    aces = 0
    
    for card in hand:
        rank = card[:-1]
        value += CARD_VALUES[rank]
        if rank == 'A':
            aces += 1
    
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    
    return value

def build_shoe():
    """Creates a new, shuffled shoe"""
    global current_shoe
    
    one_deck = []
    for suit in CARD_SUITS:
        for rank in CARD_RANKS:
            one_deck.append(f"{rank}{suit}")
    
    with shoe_lock:
        current_shoe = one_deck * NUMBER_OF_DECKS
        random.shuffle(current_shoe)
        print(f"Shoe created with {len(current_shoe)} cards")

def deal_card():
    """Deal a single card from the shoe"""
    global current_shoe
    
    with shoe_lock:
        if len(current_shoe) < (52 * NUMBER_OF_DECKS * 0.25):
            print("Shoe penetration low, rebuilding...")
            build_shoe()
        
        card = current_shoe.pop()
        game_state['cards_remaining'] = len(current_shoe)
        return card

def send_to_arduino(message):
    """Send a message to Arduino via MQTT and print the revealed card"""
    try:
        mqtt_client.publish(MQTT_TOPIC, message)
        print(f"Card revealed on table: {message}")
    except Exception as e:
        print(f"MQTT publish error: {e}")

def setup_mqtt_client():
    """Connects the MQTT client"""
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        print("MQTT Client Connected.")
    except Exception as e:
        print(f"MQTT connection failed: {e}")

def update_hand_options():
    """Updates can_split and can_double for the active hand."""
    if game_state['game_status'] != 'playing' or game_state['active_hand_index'] == -1:
        game_state['can_split'] = False
        game_state['can_double'] = False
        return

    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    
    if len(active_hand['hand']) == 2:
        # Can only double if player has enough money
        game_state['can_double'] = game_state['bank'] >= active_hand['bet']
        
        rank1 = active_hand['hand'][0][:-1]
        rank2 = active_hand['hand'][1][:-1]
        # Can only split if player has enough money
        game_state['can_split'] = (CARD_VALUES[rank1] == CARD_VALUES[rank2] and 
                                   game_state['bank'] >= game_state['current_bet'])
    else:
        game_state['can_double'] = False
        game_state['can_split'] = False

def move_to_next_hand():
    """Moves focus to the next hand, or triggers dealer's turn if all hands are played."""
    global game_state
    
    game_state['active_hand_index'] += 1
    
    if game_state['active_hand_index'] < len(game_state['player_hands']):
        active_hand = game_state['player_hands'][game_state['active_hand_index']]
        
        if active_hand['value'] == 21 and len(active_hand['hand']) == 2:
            active_hand['status'] = 'blackjack'
            game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} has Blackjack!"
            move_to_next_hand()
        else:
            active_hand['status'] = 'playing'
            game_state['message'] = f"Your turn for Hand {game_state['active_hand_index'] + 1}"
            update_hand_options()
            
    else:
        all_busted = all(hand['status'] == 'bust' for hand in game_state['player_hands'])
        
        if all_busted:
            game_state['game_status'] = 'complete'
            game_state['can_split'] = False
            game_state['can_double'] = False
            game_state['dealer_hidden'] = False
            
            final_messages = []
            for i, p_hand in enumerate(game_state['player_hands']):
                p_hand['status'] = 'lose'
                final_messages.append(f"Hand {i + 1} busts (-${p_hand['bet']})")
            
            game_state['message'] = ". ".join(final_messages) + f". Bank: ${game_state['bank']}"
        else:
            game_state['game_status'] = 'dealer_turn'
            game_state['can_split'] = False
            game_state['can_double'] = False
            game_state['message'] = "Dealer's turn..."

def dealer_plays():
    """Logic for the dealer's turn."""
    global game_state
    
    game_state['dealer_hidden'] = False
    game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand'])
    
    send_to_arduino(game_state['dealer_hand'][0])
    
    while game_state['dealer_value'] < 17:
        time.sleep(1.0)
        new_card = deal_card()
        game_state['dealer_hand'].append(new_card)
        time.sleep(1.0)
        game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand'])
        send_to_arduino(new_card)
    
    determine_winners()

def determine_winners():
    """Compares all player hands to the dealer's hand and updates bank."""
    global game_state
    
    dealer_val = game_state['dealer_value']
    dealer_bust = dealer_val > 21
    final_messages = []
    dealer_has_blackjack = dealer_val == 21 and len(game_state['dealer_hand']) == 2
    
    for i, p_hand in enumerate(game_state['player_hands']):
        hand_num = i + 1
        bet = p_hand['bet']
        
        if p_hand['status'] == 'bust':
            p_hand['status'] = 'lose'
            final_messages.append(f"Hand {hand_num} busts (-${bet})")
        
        elif p_hand['status'] == 'blackjack':
            if dealer_has_blackjack:
                p_hand['status'] = 'tie'
                game_state['bank'] += bet
                final_messages.append(f"Hand {hand_num} pushes (${bet})")
            else:
                p_hand['status'] = 'win'
                winnings = int(bet * 2.5)  # 3:2 payout for blackjack
                game_state['bank'] += winnings
                final_messages.append(f"Hand {hand_num} BLACKJACK! (+${winnings - bet})")
        
        elif p_hand['status'] == 'stood':
            hand_val = p_hand['value']
            if dealer_bust:
                p_hand['status'] = 'win'
                game_state['bank'] += bet * 2
                final_messages.append(f"Hand {hand_num} wins (+${bet})")
            elif hand_val > dealer_val:
                p_hand['status'] = 'win'
                game_state['bank'] += bet * 2
                final_messages.append(f"Hand {hand_num} wins (+${bet})")
            elif hand_val < dealer_val:
                p_hand['status'] = 'lose'
                final_messages.append(f"Hand {hand_num} loses (-${bet})")
            else:
                p_hand['status'] = 'tie'
                game_state['bank'] += bet
                final_messages.append(f"Hand {hand_num} pushes (${bet})")
    
    game_state['game_status'] = 'complete'
    game_state['message'] = ". ".join(final_messages) + f". Bank: ${game_state['bank']}"


@app.route('/')
def index():
    """Render the main game page"""
    return render_template('blackjack.html') 

@app.route('/set_bet', methods=['POST'])
def set_bet():
    """Set the bet amount before dealing"""
    global game_state
    
    data = request.get_json()
    bet_amount = data.get('amount', MIN_BET)
    
    if bet_amount < MIN_BET:
        return jsonify({'error': f'Minimum bet is ${MIN_BET}'}), 400
    
    if bet_amount > game_state['bank']:
        return jsonify({'error': 'Insufficient funds'}), 400
    
    game_state['current_bet'] = bet_amount
    return jsonify({'current_bet': game_state['current_bet'], 'bank': game_state['bank']})

@app.route('/deal', methods=['POST'])
def deal():
    """Start a new game by dealing initial cards"""
    global game_state
    
    if game_state['bank'] < MIN_BET:
        return jsonify({'error': 'Insufficient funds. Please reset your bank.'}), 400
    
    if game_state['current_bet'] > game_state['bank']:
        game_state['current_bet'] = min(game_state['bank'], game_state['current_bet'])
    
    # Deduct bet from bank
    game_state['bank'] -= game_state['current_bet']
    
    # Reset game state but keep bank
    bank_backup = game_state['bank']
    current_bet_backup = game_state['current_bet']
    reset_game_state()
    game_state['bank'] = bank_backup
    game_state['current_bet'] = current_bet_backup
    
    game_state['player_hands'] = [{
        'hand': [], 
        'value': 0, 
        'status': 'playing', 
        'bet': game_state['current_bet']
    }]
    game_state['active_hand_index'] = 0
    game_state['game_status'] = 'playing'

    card1 = deal_card()
    card2 = deal_card()
    card3 = deal_card()
    card4 = deal_card()
    
    active_hand = game_state['player_hands'][0]
    
    active_hand['hand'].append(card1)
    send_to_arduino(card1)
    
    game_state['dealer_hand'].append(card2)
    
    active_hand['hand'].append(card3)
    send_to_arduino(card3)
    
    game_state['dealer_hand'].append(card4)
    send_to_arduino(card4)
    
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    game_state['dealer_value'] = CARD_VALUES[card4[:-1]]
    
    if active_hand['value'] == 21:
        active_hand['status'] = 'blackjack'
        game_state['message'] = "Blackjack! Let's see what the dealer has..."
        game_state['active_hand_index'] = -1
        dealer_plays()
    else:
        game_state['message'] = f"Your turn for Hand 1 (Bet: ${game_state['current_bet']})"
        update_hand_options()
    
    return jsonify(game_state)

@app.route('/hit', methods=['POST'])
def hit():
    """Player hits - deal another card"""
    global game_state
    
    if game_state['game_status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]

    new_card = deal_card()
    active_hand['hand'].append(new_card)
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    
    send_to_arduino(new_card)
    
    game_state['can_double'] = False
    game_state['can_split'] = False
    
    if active_hand['value'] > 21:
        active_hand['status'] = 'bust'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} busts!"
        move_to_next_hand()
    elif active_hand['value'] == 21:
        active_hand['status'] = 'stood'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} has 21!"
        move_to_next_hand()
    
    return jsonify(game_state)

@app.route('/stand', methods=['POST'])
def stand():
    """Player stands - dealer's turn"""
    global game_state
    
    if game_state['game_status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    active_hand['status'] = 'stood'
    
    game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} stands."
    move_to_next_hand()
    
    return jsonify(game_state)

@app.route('/double', methods=['POST'])
def double_down():
    """Player doubles down."""
    global game_state
    
    if game_state['game_status'] != 'playing' or not game_state['can_double']:
        return jsonify({'error': 'Cannot double down now'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    
    # Deduct additional bet from bank
    game_state['bank'] -= active_hand['bet']
    active_hand['bet'] *= 2
    
    new_card = deal_card()
    active_hand['hand'].append(new_card)
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    send_to_arduino(new_card)
    
    game_state['can_double'] = False
    game_state['can_split'] = False
    
    if active_hand['value'] > 21:
        active_hand['status'] = 'bust'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} busts on double!"
    else:
        active_hand['status'] = 'stood'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} doubles and stands."
    
    move_to_next_hand()
    return jsonify(game_state)

@app.route('/split', methods=['POST'])
def split():
    """Player splits a pair."""
    global game_state
    
    if game_state['game_status'] != 'playing' or not game_state['can_split']:
        return jsonify({'error': 'Cannot split now'}), 400
    
    # Deduct additional bet from bank
    game_state['bank'] -= game_state['current_bet']
        
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    card_to_move = active_hand['hand'].pop()
    
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    
    new_hand = {
        'hand': [card_to_move],
        'value': calculate_hand_value([card_to_move]),
        'status': 'pending',
        'bet': game_state['current_bet']
    }
    
    game_state['player_hands'].insert(game_state['active_hand_index'] + 1, new_hand)
    
    new_card_1 = deal_card()
    active_hand['hand'].append(new_card_1)
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    send_to_arduino(new_card_1)
    
    time.sleep(0.5)
    
    new_card_2 = deal_card()
    new_hand['hand'].append(new_card_2)
    new_hand['value'] = calculate_hand_value(new_hand['hand'])
    send_to_arduino(new_card_2)
    
    rank1 = active_hand['hand'][0][:-1]
    is_ace_split = (CARD_VALUES[rank1] == 11)
    
    if is_ace_split:
        active_hand['status'] = 'stood'
        new_hand['status'] = 'stood'
        game_state['message'] = "Split Aces! Each hand gets one card and stands."
        move_to_next_hand()
    else:
        update_hand_options()
        
        if active_hand['value'] == 21:
            active_hand['status'] = 'stood'
            move_to_next_hand()
        else:
            game_state['message'] = f"Split! Your turn for Hand {game_state['active_hand_index'] + 1}"

    return jsonify(game_state)


@app.route('/dealer_step', methods=['POST'])
def dealer_step():
    """Performs one step of the dealer's turn."""
    global game_state
    
    if game_state['game_status'] != 'dealer_turn':
        return jsonify({'error': 'Not dealer\'s turn'}), 400

    # Step 1: Reveal hidden card if it's the first step
    if game_state['dealer_hidden']:
        game_state['dealer_hidden'] = False
        game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand'])
        send_to_arduino(game_state['dealer_hand'][0]) # Reveal hole card
        game_state['message'] = f"Dealer reveals. Value is {game_state['dealer_value']}"
        
        # After revealing, check if we're done (e.g., dealer has 17-21)
        if game_state['dealer_value'] >= 17:
            determine_winners()
        
        return jsonify(game_state)

    # Step 2: Draw a card if under 17
    if game_state['dealer_value'] < 17:
        new_card = deal_card()
        game_state['dealer_hand'].append(new_card)
        game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand'])
        send_to_arduino(new_card)
        
        if game_state['dealer_value'] > 21:
            game_state['message'] = "Dealer busts!"
        else:
            game_state['message'] = f"Dealer hits. Value is {game_state['dealer_value']}"
        
        # After drawing, check if we're done
        if game_state['dealer_value'] >= 17:
            determine_winners() # This will set status to 'complete'
    
    # This should only happen if dealer hits and is still < 17
    # Or if they were already >= 17, in which case we determine winners
    elif game_state['game_status'] != 'complete':
        determine_winners()

    return jsonify(game_state)

@app.route('/shuffle', methods=['POST'])
def shuffle():
    """Shuffle the deck and notify Arduino"""
    global game_state
    
    if game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot shuffle during a game'}), 400
    
    build_shoe()
    send_to_arduino("0")  # Send shuffle signal to Arduino
    game_state['cards_remaining'] = len(current_shoe)
    game_state['message'] = f"Deck shuffled! {game_state['cards_remaining']} cards remaining."
    
    return jsonify(game_state)

@app.route('/reset_bank', methods=['POST'])
def reset_bank():
    """Reset the player's bank to starting amount"""
    global game_state
    
    if game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot reset bank during a game'}), 400
    
    game_state['bank'] = STARTING_BANK
    game_state['message'] = f"Bank reset to ${STARTING_BANK}!"
    
    return jsonify(game_state)

@app.route('/state', methods=['GET'])
def get_state():
    """Get current game state"""
    return jsonify(game_state)

if __name__ == '__main__':
    reset_game_state()
    build_shoe()
    setup_mqtt_client()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)