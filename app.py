import paho.mqtt.client as mqtt
from flask import Flask, render_template, jsonify, request
import time
import helpers  # Import our new helpers file

# --- MQTT Configuration ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "ece508/blackjack_table1"

# --- App Configuration ---
app = Flask(__name__)
mqtt_client = mqtt.Client("flask_blackjack_" + str(time.time()))

# --- MQTT Functions ---

def send_to_arduino(message):
    """Send a message to Arduino via MQTT and print the revealed card"""
    try:
        testmessage = mqtt_client.publish(MQTT_TOPIC, message)
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

# --- Flask Routes ---

@app.route('/')
def index():
    """Render the main game page"""
    return render_template('blackjack.html') 

@app.route('/set_bet', methods=['POST'])
def set_bet():
    """Set the bet amount before dealing"""
    data = request.get_json()
    bet_amount = data.get('amount', helpers.MIN_BET)
    
    if bet_amount < helpers.MIN_BET:
        return jsonify({'error': f'Minimum bet is ${helpers.MIN_BET}'}), 400
    
    if bet_amount > helpers.game_state['bank']:
        return jsonify({'error': 'Insufficient funds'}), 400
    
    helpers.game_state['current_bet'] = bet_amount
    return jsonify({
        'current_bet': helpers.game_state['current_bet'], 
        'bank': helpers.game_state['bank']
    })

@app.route('/deal', methods=['POST'])
def deal():
    """Start a new game by dealing initial cards"""
    if helpers.game_state['bank'] < helpers.MIN_BET:
        return jsonify({'error': 'Insufficient funds. Please reset your bank.'}), 400
    
    if helpers.game_state['current_bet'] > helpers.game_state['bank']:
        helpers.game_state['current_bet'] = min(
            helpers.game_state['bank'], helpers.game_state['current_bet']
        )
    
    # Deduct bet from bank
    helpers.game_state['bank'] -= helpers.game_state['current_bet']
    
    # Reset game state but keep bank
    bank_backup = helpers.game_state['bank']
    current_bet_backup = helpers.game_state['current_bet']
    helpers.reset_game_state()
    helpers.game_state['bank'] = bank_backup
    helpers.game_state['current_bet'] = current_bet_backup
    
    helpers.game_state['player_hands'] = [{
        'hand': [], 
        'value': 0, 
        'status': 'playing', 
        'bet': helpers.game_state['current_bet']
    }]
    helpers.game_state['active_hand_index'] = 0
    helpers.game_state['game_status'] = 'playing'

    card1 = helpers.deal_card()
    card2 = helpers.deal_card()
    card3 = helpers.deal_card()
    card4 = helpers.deal_card()
    
    active_hand = helpers.game_state['player_hands'][0]
    
    active_hand['hand'].append(card1)
    send_to_arduino(card1)
    
    helpers.game_state['dealer_hand'].append(card2)
    
    active_hand['hand'].append(card3)
    send_to_arduino(card3)
    
    helpers.game_state['dealer_hand'].append(card4)
    send_to_arduino(card4)
    
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    helpers.game_state['dealer_value'] = helpers.CARD_VALUES[card4[:-1]]
    
    if active_hand['value'] == 21:
        active_hand['status'] = 'blackjack'
        helpers.game_state['message'] = "Blackjack! Let's see what the dealer has..."
        helpers.game_state['active_hand_index'] = -1
        # Pass the send_to_arduino function to dealer_plays
        helpers.dealer_plays(send_to_arduino)
    else:
        helpers.game_state['message'] = f"Your turn for Hand 1 (Bet: ${helpers.game_state['current_bet']})"
        helpers.update_hand_options()
    
    return jsonify(helpers.game_state)

@app.route('/hit', methods=['POST'])
def hit():
    """Player hits - deal another card"""
    if helpers.game_state['game_status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = helpers.game_state['player_hands'][helpers.game_state['active_hand_index']]

    new_card = helpers.deal_card()
    active_hand['hand'].append(new_card)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    
    send_to_arduino(new_card)
    
    helpers.game_state['can_double'] = False
    helpers.game_state['can_split'] = False
    
    if active_hand['value'] > 21:
        active_hand['status'] = 'bust'
        helpers.game_state['message'] = f"Hand {helpers.game_state['active_hand_index'] + 1} busts!"
        helpers.move_to_next_hand()
    elif active_hand['value'] == 21:
        active_hand['status'] = 'stood'
        helpers.game_state['message'] = f"Hand {helpers.game_state['active_hand_index'] + 1} has 21!"
        helpers.move_to_next_hand()
    
    return jsonify(helpers.game_state)

@app.route('/stand', methods=['POST'])
def stand():
    """Player stands - dealer's turn"""
    if helpers.game_state['game_status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = helpers.game_state['player_hands'][helpers.game_state['active_hand_index']]
    active_hand['status'] = 'stood'
    
    helpers.game_state['message'] = f"Hand {helpers.game_state['active_hand_index'] + 1} stands."
    helpers.move_to_next_hand()
    
    return jsonify(helpers.game_state)

@app.route('/double', methods=['POST'])
def double_down():
    """Player doubles down."""
    if helpers.game_state['game_status'] != 'playing' or not helpers.game_state['can_double']:
        return jsonify({'error': 'Cannot double down now'}), 400
    
    active_hand = helpers.game_state['player_hands'][helpers.game_state['active_hand_index']]
    
    # Deduct additional bet from bank
    helpers.game_state['bank'] -= active_hand['bet']
    active_hand['bet'] *= 2
    
    new_card = helpers.deal_card()
    active_hand['hand'].append(new_card)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    send_to_arduino(new_card)
    
    helpers.game_state['can_double'] = False
    helpers.game_state['can_split'] = False
    
    if active_hand['value'] > 21:
        active_hand['status'] = 'bust'
        helpers.game_state['message'] = f"Hand {helpers.game_state['active_hand_index'] + 1} busts on double!"
    else:
        active_hand['status'] = 'stood'
        helpers.game_state['message'] = f"Hand {helpers.game_state['active_hand_index'] + 1} doubles and stands."
    
    helpers.move_to_next_hand()
    return jsonify(helpers.game_state)

@app.route('/split', methods=['POST'])
def split():
    """Player splits a pair."""
    if helpers.game_state['game_status'] != 'playing' or not helpers.game_state['can_split']:
        return jsonify({'error': 'Cannot split now'}), 400
    
    # Deduct additional bet from bank
    helpers.game_state['bank'] -= helpers.game_state['current_bet']
        
    active_hand = helpers.game_state['player_hands'][helpers.game_state['active_hand_index']]
    card_to_move = active_hand['hand'].pop()
    
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    
    new_hand = {
        'hand': [card_to_move],
        'value': helpers.calculate_hand_value([card_to_move]),
        'status': 'pending',
        'bet': helpers.game_state['current_bet']
    }
    
    helpers.game_state['player_hands'].insert(helpers.game_state['active_hand_index'] + 1, new_hand)
    
    new_card_1 = helpers.deal_card()
    active_hand['hand'].append(new_card_1)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    send_to_arduino(new_card_1)
    
    time.sleep(0.5)
    
    new_card_2 = helpers.deal_card()
    new_hand['hand'].append(new_card_2)
    new_hand['value'] = helpers.calculate_hand_value(new_hand['hand'])
    send_to_arduino(new_card_2)
    
    rank1 = active_hand['hand'][0][:-1]
    is_ace_split = (helpers.CARD_VALUES[rank1] == 11)
    
    if is_ace_split:
        active_hand['status'] = 'stood'
        new_hand['status'] = 'stood'
        helpers.game_state['message'] = "Split Aces! Each hand gets one card and stands."
        helpers.move_to_next_hand()
    else:
        helpers.update_hand_options()
        
        if active_hand['value'] == 21:
            active_hand['status'] = 'stood'
            helpers.move_to_next_hand()
        else:
            helpers.game_state['message'] = f"Split! Your turn for Hand {helpers.game_state['active_hand_index'] + 1}"

    return jsonify(helpers.game_state)


@app.route('/dealer_step', methods=['POST'])
def dealer_step():
    """Performs one step of the dealer's turn."""
    if helpers.game_state['game_status'] != 'dealer_turn':
        return jsonify({'error': 'Not dealer\'s turn'}), 400

    # Step 1: Reveal hidden card if it's the first step
    if helpers.game_state['dealer_hidden']:
        helpers.game_state['dealer_hidden'] = False
        helpers.game_state['dealer_value'] = helpers.calculate_hand_value(helpers.game_state['dealer_hand'])
        send_to_arduino(helpers.game_state['dealer_hand'][0]) # Reveal hole card
        helpers.game_state['message'] = f"Dealer reveals. Value is {helpers.game_state['dealer_value']}"
        
        # After revealing, check if we're done (e.g., dealer has 17-21)
        if helpers.game_state['dealer_value'] >= 17:
            helpers.determine_winners()
        
        return jsonify(helpers.game_state)

    # Step 2: Draw a card if under 17
    if helpers.game_state['dealer_value'] < 17:
        new_card = helpers.deal_card()
        helpers.game_state['dealer_hand'].append(new_card)
        helpers.game_state['dealer_value'] = helpers.calculate_hand_value(helpers.game_state['dealer_hand'])
        send_to_arduino(new_card)
        
        if helpers.game_state['dealer_value'] > 21:
            helpers.game_state['message'] = "Dealer busts!"
        else:
            helpers.game_state['message'] = f"Dealer hits. Value is {helpers.game_state['dealer_value']}"
        
        # After drawing, check if we're done
        if helpers.game_state['dealer_value'] >= 17:
            helpers.determine_winners() # This will set status to 'complete'
    
    # This should only happen if dealer hits and is still < 17
    # Or if they were already >= 17, in which case we determine winners
    elif helpers.game_state['game_status'] != 'complete':
        helpers.determine_winners()

    return jsonify(helpers.game_state)

@app.route('/shuffle', methods=['POST'])
def shuffle():
    """Shuffle the deck and notify Arduino"""
    if helpers.game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot shuffle during a game'}), 400
    
    helpers.build_shoe()
    send_to_arduino("0")  # Send shuffle signal to Arduino
    helpers.game_state['cards_remaining'] = len(helpers.current_shoe)
    helpers.game_state['message'] = f"Deck shuffled! {helpers.game_state['cards_remaining']} cards remaining."
    
    return jsonify(helpers.game_state)

@app.route('/reset_bank', methods=['POST'])
def reset_bank():
    """Reset the player's bank to starting amount"""
    if helpers.game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot reset bank during a game'}), 400
    
    helpers.game_state['bank'] = helpers.STARTING_BANK
    helpers.game_state['message'] = f"Bank reset to ${helpers.STARTING_BANK}!"
    
    return jsonify(helpers.game_state)

@app.route('/state', methods=['GET'])
def get_state():
    """Get current game state"""
    return jsonify(helpers.game_state)

@app.route('/update_mqtt', methods=['POST'])
def update_mqtt():
    """Update MQTT configuration"""
    global MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, mqtt_client
    
    data = request.get_json()
    new_broker = data.get('broker', MQTT_BROKER)
    new_port = data.get('port', MQTT_PORT)
    new_topic = data.get('topic', MQTT_TOPIC)
    
    # Validate inputs
    if not new_broker or not new_topic:
        return jsonify({'error': 'Broker and topic cannot be empty'}), 400
    
    try:
        new_port = int(new_port)
        if new_port < 1 or new_port > 65535:
            return jsonify({'error': 'Port must be between 1 and 65535'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid port number'}), 400
    
    # Disconnect old client
    try:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
    except:
        pass
    
    # Update configuration
    MQTT_BROKER = new_broker
    MQTT_PORT = new_port
    MQTT_TOPIC = new_topic
    
    # Reconnect with new settings
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start()
        return jsonify({
            'broker': MQTT_BROKER,
            'port': MQTT_PORT,
            'topic': MQTT_TOPIC,
            'message': 'MQTT configuration updated successfully'
        })
    except Exception as e:
        return jsonify({'error': f'Failed to connect: {str(e)}'}), 500

# --- Application Start-up ---
# These functions MUST run when the file is imported by the
# PythonAnywhere server, so they must be outside the __name__ block.
helpers.reset_game_state()
helpers.build_shoe()
setup_mqtt_client()


if __name__ == '__main__':
    # This block will now only be used when you run it locally
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)