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
CARD_SUITS = ['H', 'D', 'C', 'S'] # Added suits
CARD_VALUES = {
    'A': 11, 'K': 10, 'Q': 10, 'J': 10, 'T': 10,
    '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2
}
NUMBER_OF_DECKS = 6
BASE_BET = 10 # Base bet for calculations

# --- Game State ---
game_state = {}
current_shoe = []
shoe_lock = threading.Lock()

def reset_game_state():
    """Helper to initialize or reset the game state"""
    global game_state
    game_state = {
        'player_hands': [], # List of hand objects: {'hand': [], 'value': 0, 'status': 'playing', 'bet': 10}
        'active_hand_index': -1, # -1 means no active hand (game not started)
        'dealer_hand': [],
        'dealer_value': 0,
        'dealer_hidden': True,
        'game_status': 'waiting',  # waiting, playing, dealer_turn, complete
        'message': 'Press "Deal" to start a new game',
        'can_split': False,
        'can_double': False,
        'base_bet': BASE_BET
    }

def calculate_hand_value(hand):
    """Calculate the value of a hand, adjusting for aces"""
    value = 0
    aces = 0
    
    for card in hand: # card is now 'AH', 'KS', etc.
        rank = card[:-1] # Get 'A' from 'AH'
        value += CARD_VALUES[rank]
        if rank == 'A':
            aces += 1
    
    # Adjust for aces
    while value > 21 and aces > 0:
        value -= 10
        aces -= 1
    
    return value

def build_shoe():
    """Creates a new, shuffled shoe"""
    global current_shoe
    
    # --- MODIFIED: Build full decks with suits ---
    one_deck = []
    for suit in CARD_SUITS:
        for rank in CARD_RANKS:
            one_deck.append(f"{rank}{suit}") # e.g., "AH", "KH", "2S"
    # --- END MODIFICATION ---
    
    with shoe_lock:
        current_shoe = one_deck * NUMBER_OF_DECKS
        random.shuffle(current_shoe)
        print(f"Shoe created with {len(current_shoe)} cards")

def deal_card():
    """Deal a single card from the shoe"""
    global current_shoe
    
    with shoe_lock:
        # Re-shuffle at 25% penetration
        if len(current_shoe) < (52 * NUMBER_OF_DECKS * 0.25):
            print("Shoe penetration low, rebuilding...")
            build_shoe()
        
        card = current_shoe.pop()
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
    
    # Can only split/double on the first two cards
    if len(active_hand['hand']) == 2:
        game_state['can_double'] = True
        
        # --- MODIFIED: Check ranks from card string ---
        rank1 = active_hand['hand'][0][:-1]
        rank2 = active_hand['hand'][1][:-1]
        game_state['can_split'] = CARD_VALUES[rank1] == CARD_VALUES[rank2]
        # --- END MODIFICATION ---
    else:
        game_state['can_double'] = False
        game_state['can_split'] = False

def move_to_next_hand():
    """Moves focus to the next hand, or triggers dealer's turn if all hands are played."""
    global game_state
    
    game_state['active_hand_index'] += 1
    
    if game_state['active_hand_index'] < len(game_state['player_hands']):
        # There is another hand to play
        active_hand = game_state['player_hands'][game_state['active_hand_index']]
        
        # Check for blackjack on this new hand (can happen after split)
        if active_hand['value'] == 21 and len(active_hand['hand']) == 2:
            active_hand['status'] = 'blackjack'
            game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} has Blackjack!"
            move_to_next_hand() # Recursively move to the next
        else:
            active_hand['status'] = 'playing'
            game_state['message'] = f"Your turn for Hand {game_state['active_hand_index'] + 1}"
            update_hand_options()
            
    else:
        # All player hands are finished
        # Check if ALL hands busted - if so, skip dealer's turn
        all_busted = all(hand['status'] == 'bust' for hand in game_state['player_hands'])
        
        if all_busted:
            # No need for dealer to play
            game_state['game_status'] = 'complete'
            game_state['can_split'] = False
            game_state['can_double'] = False
            game_state['dealer_hidden'] = False  # Reveal dealer's hole card anyway
            
            # Set all hands to 'lose' status
            final_messages = []
            for i, p_hand in enumerate(game_state['player_hands']):
                p_hand['status'] = 'lose'
                final_messages.append(f"Hand {i + 1} busts")
            
            game_state['message'] = ". ".join(final_messages) + ". Press 'Bet' to play again."
        else:
            # At least one hand is still in play, dealer must play
            game_state['game_status'] = 'dealer_turn'
            game_state['can_split'] = False
            game_state['can_double'] = False
            game_state['message'] = "Dealer's turn..."
            dealer_plays()

def dealer_plays():
    """Logic for the dealer's turn."""
    global game_state
    
    game_state['dealer_hidden'] = False
    game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand']) # Recalculate with hole card
    
    send_to_arduino(game_state['dealer_hand'][0]) # Reveal hidden card
    
    # Dealer hits until 17 or higher
    while game_state['dealer_value'] < 17:
        time.sleep(1.0) # Small delay for drama
        new_card = deal_card()
        game_state['dealer_hand'].append(new_card)
        game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand'])
        send_to_arduino(new_card)
    
    determine_winners()

def determine_winners():
    """Compares all player hands to the dealer's hand."""
    global game_state
    
    dealer_val = game_state['dealer_value']
    dealer_bust = dealer_val > 21
    final_messages = []
    
    # Check for dealer blackjack
    dealer_has_blackjack = dealer_val == 21 and len(game_state['dealer_hand']) == 2
    
    for i, p_hand in enumerate(game_state['player_hands']):
        hand_num = i + 1
        
        if p_hand['status'] == 'bust':
            p_hand['status'] = 'lose'
            final_messages.append(f"Hand {hand_num} busts")
        
        elif p_hand['status'] == 'blackjack':
            if dealer_has_blackjack:
                p_hand['status'] = 'tie'
                final_messages.append(f"Hand {hand_num} pushes (Blackjack)")
            else:
                p_hand['status'] = 'win'
                final_messages.append(f"Hand {hand_num} WINS (Blackjack!)")
        
        elif p_hand['status'] == 'stood':
            hand_val = p_hand['value']
            if dealer_bust:
                p_hand['status'] = 'win'
                final_messages.append(f"Hand {hand_num} wins (Dealer busts)")
            elif hand_val > dealer_val:
                p_hand['status'] = 'win'
                final_messages.append(f"Hand {hand_num} wins")
            elif hand_val < dealer_val:
                p_hand['status'] = 'lose'
                final_messages.append(f"Hand {hand_num} loses")
            else:
                p_hand['status'] = 'tie'
                final_messages.append(f"Hand {hand_num} pushes")
    
    game_state['game_status'] = 'complete'
    game_state['message'] = ". ".join(final_messages) + ". Press 'Bet' to play again."


@app.route('/')
def index():
    """Render the main game page"""
    return render_template('blackjack.html') 

@app.route('/deal', methods=['POST'])
def deal():
    """Start a new game by dealing initial cards"""
    global game_state
    
    reset_game_state() # Clear old state
    
    # Create first player hand
    game_state['player_hands'] = [{
        'hand': [], 
        'value': 0, 
        'status': 'playing', 
        'bet': game_state['base_bet']
    }]
    game_state['active_hand_index'] = 0
    game_state['game_status'] = 'playing'

    # Deal initial cards
    card1 = deal_card() # Player 1
    card2 = deal_card() # Dealer Hidden
    card3 = deal_card() # Player 2
    card4 = deal_card() # Dealer Up
    
    active_hand = game_state['player_hands'][0]
    
    active_hand['hand'].append(card1)
    send_to_arduino(card1)
    
    game_state['dealer_hand'].append(card2)
    # NOT sent
    
    active_hand['hand'].append(card3)
    send_to_arduino(card3)
    
    game_state['dealer_hand'].append(card4)
    send_to_arduino(card4)
    
    # Calculate values
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    # Don't calculate dealer's full value, only show the up card's value
    game_state['dealer_value'] = CARD_VALUES[card4[:-1]]
    
    # Check for player blackjack
    if active_hand['value'] == 21:
        active_hand['status'] = 'blackjack'
        game_state['message'] = "Blackjack! Let's see what the dealer has..."
        game_state['active_hand_index'] = -1 # Mark as no hand active
        dealer_plays()
    else:
        game_state['message'] = "Your turn for Hand 1"
        update_hand_options()
    
    return jsonify(game_state)

@app.route('/hit', methods=['POST'])
def hit():
    """Player hits - deal another card"""
    global game_state
    
    if game_state['game_status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]

    # Deal card to player (REVEALED)
    new_card = deal_card()
    active_hand['hand'].append(new_card)
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    
    send_to_arduino(new_card)
    
    # After hitting, you can't double or split
    game_state['can_double'] = False
    game_state['can_split'] = False
    
    # Check for bust
    if active_hand['value'] > 21:
        active_hand['status'] = 'bust'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} busts!"
        move_to_next_hand()
    elif active_hand['value'] == 21:
        # Auto-stand on 21
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
    move_to_next_hand() # Move to next hand or dealer
    
    return jsonify(game_state)

@app.route('/double', methods=['POST'])
def double_down():
    """Player doubles down."""
    global game_state
    
    if game_state['game_status'] != 'playing' or not game_state['can_double']:
        return jsonify({'error': 'Cannot double down now'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    
    # Double the bet
    active_hand['bet'] *= 2
    
    # Deal one card
    new_card = deal_card()
    active_hand['hand'].append(new_card)
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    send_to_arduino(new_card)
    
    # Turn is over for this hand, must stand
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
        
    # Get current hand and card to move
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    card_to_move = active_hand['hand'].pop() # e.g., '8H'
    
    # Update value of original hand (now with 1 card)
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    
    # Create a new hand
    new_hand = {
        'hand': [card_to_move],
        'value': calculate_hand_value([card_to_move]),
        'status': 'pending', # Not active yet
        'bet': game_state['base_bet']
    }
    
    # Insert new hand *after* the current one
    game_state['player_hands'].insert(game_state['active_hand_index'] + 1, new_hand)
    
    # Deal one new card to each hand
    new_card_1 = deal_card()
    active_hand['hand'].append(new_card_1)
    active_hand['value'] = calculate_hand_value(active_hand['hand'])
    send_to_arduino(new_card_1)
    
    time.sleep(0.5) # small delay
    
    new_card_2 = deal_card()
    new_hand['hand'].append(new_card_2)
    new_hand['value'] = calculate_hand_value(new_hand['hand'])
    send_to_arduino(new_card_2)
    
    # --- MODIFIED: Check rank from card string ---
    rank1 = active_hand['hand'][0][:-1]
    is_ace_split = (CARD_VALUES[rank1] == 11)
    # --- END MODIFICATION ---
    
    if is_ace_split:
        # Special rule: If splitting Aces, you only get one card each and must stand
        active_hand['status'] = 'stood'
        new_hand['status'] = 'stood'
        game_state['message'] = "Split Aces! Each hand gets one card and stands."
        # We will move to the next hand, which is also 'stood'
        move_to_next_hand()
    else:
        # Update options for the *current* active hand
        update_hand_options()
        
        # Check for blackjack on the *first* hand
        if active_hand['value'] == 21:
            active_hand['status'] = 'stood' # Auto-stand on 21
            move_to_next_hand()
        else:
            game_state['message'] = f"Split! Your turn for Hand {game_state['active_hand_index'] + 1}"

    return jsonify(game_state)


@app.route('/state', methods=['GET'])
def get_state():
    """Get current game state"""
    return jsonify(game_state)

if __name__ == '__main__':
    reset_game_state() # Initialize state on start
    build_shoe()
    setup_mqtt_client()
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)