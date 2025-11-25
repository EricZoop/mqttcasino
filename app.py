import paho.mqtt.client as mqtt # type: ignore
from flask import Flask, render_template, jsonify, request # type: ignore
import time
import helpers
import secrets
import threading

# --- App Configuration ---
app = Flask(__name__)

# Session timeout configuration
SESSION_TIMEOUT_SECONDS = 10 * 60  # 10 minutes
SESSION_CLEANUP_INTERVAL_SECONDS = 60  # Check every minute

# Store MQTT clients per session
mqtt_clients = {}

# Track last activity time for each session
session_last_activity = {}

# --- Session Management ---

def update_session_activity(session_id):
    """Update the last activity timestamp for a session"""
    session_last_activity[session_id] = time.time()

def cleanup_inactive_sessions():
    """Background thread to cleanup inactive sessions"""
    while True:
        time.sleep(SESSION_CLEANUP_INTERVAL_SECONDS)
        current_time = time.time()
        sessions_to_delete = []
        
        for session_id, last_activity in list(session_last_activity.items()):
            if current_time - last_activity > SESSION_TIMEOUT_SECONDS:
                sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            try:
                # Disconnect MQTT client
                if session_id in mqtt_clients:
                    try:
                        mqtt_clients[session_id]['client'].loop_stop()
                        mqtt_clients[session_id]['client'].disconnect()
                    except:
                        pass
                    del mqtt_clients[session_id]
                
                # Remove session state
                if session_id in helpers.session_states:
                    del helpers.session_states[session_id]
                
                # Remove activity tracking
                if session_id in session_last_activity:
                    del session_last_activity[session_id]
                
                print(f"[CLEANUP] Session {session_id[:8]} deleted due to inactivity")
            except Exception as e:
                print(f"[CLEANUP] Error cleaning up session {session_id[:8]}: {e}")

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_inactive_sessions, daemon=True)
cleanup_thread.start()

# --- MQTT Functions ---

def get_mqtt_client(session_id):
    """Get or create MQTT client for this session"""
    if session_id not in mqtt_clients:
        client = mqtt.Client(f"flask_blackjack_{session_id}_{time.time()}")
        mqtt_clients[session_id] = {
            'client': client,
            'broker': "broker.hivemq.com",
            'port': 1883,
            'topic': f"gmu/ece508/team08/blkjck_{session_id[:5]}",
            'connected': False
        }
    return mqtt_clients[session_id]

def send_to_arduino(session_id, message):
    """Send a message to Arduino via MQTT for this session"""
    try:
        client_info = get_mqtt_client(session_id)
        client_info['client'].publish(client_info['topic'], message)
        print(f"[{session_id[:5]}] Card revealed on table: {message}")
    except Exception as e:
        print(f"MQTT publish error: {e}")

def setup_mqtt_client(session_id):
    """Connects the MQTT client for this session"""
    client_info = get_mqtt_client(session_id)
    try:
        if not client_info['connected']:
            client_info['client'].connect(client_info['broker'], client_info['port'], 60)
            client_info['client'].loop_start()
            client_info['connected'] = True
            print(f"[{session_id[:5]}] MQTT Client Connected to {client_info['broker']}:{client_info['port']} on topic {client_info['topic']}")
    except Exception as e:
        print(f"MQTT connection failed: {e}")

def get_session_id_from_request():
    """Extract session_id from request body or query params"""
    # Try to get from JSON body first
    if request.is_json:
        data = request.get_json()
        if data and 'session_id' in data:
            return data['session_id']
    
    # Try to get from query params
    return request.args.get('session_id')

# --- Flask Routes ---

@app.route('/')
def index():
    """Render the main game page"""
    return render_template('blackjack.html')

@app.route('/init_session', methods=['POST'])
def init_session():
    """Initialize a new session"""
    new_session_id = secrets.token_hex(16)
    
    # Initialize game state for new session
    helpers.init_session_state(new_session_id)
    helpers.build_shoe(new_session_id)
    setup_mqtt_client(new_session_id)
    update_session_activity(new_session_id)
    
    client_info = get_mqtt_client(new_session_id)
    
    return jsonify({
        'session_id': new_session_id,
        'broker': client_info['broker'],
        'port': client_info['port'],
        'topic': client_info['topic'],
        'message': f'Session created: {new_session_id[:5]}'
    })

@app.route('/host_table', methods=['POST'])
def host_table():
    """Create a new table (new session)"""
    new_session_id = secrets.token_hex(16)
    
    # Initialize game state for new session
    helpers.init_session_state(new_session_id)
    helpers.build_shoe(new_session_id)
    setup_mqtt_client(new_session_id)
    update_session_activity(new_session_id)
    
    client_info = get_mqtt_client(new_session_id)
    
    return jsonify({
        'session_id': new_session_id,
        'broker': client_info['broker'],
        'port': client_info['port'],
        'topic': client_info['topic'],
        'message': f'New table hosted! Session: {new_session_id[:5]}'
    })

@app.route('/set_bet', methods=['POST'])
def set_bet():
    """Set the bet amount before dealing"""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    data = request.get_json()
    bet_amount = data.get('amount', helpers.MIN_BET)
    
    game_state = helpers.get_session_state(session_id)
    
    if bet_amount < helpers.MIN_BET:
        return jsonify({'error': f'Minimum bet is ${helpers.MIN_BET}'}), 400
    
    if bet_amount > game_state['bank']:
        return jsonify({'error': 'Insufficient funds'}), 400
    
    game_state['current_bet'] = bet_amount
    return jsonify({
        'current_bet': game_state['current_bet'], 
        'bank': game_state['bank']
    })

@app.route('/deal', methods=['POST'])
def deal():
    """Start a new game by dealing initial cards"""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    # Update activity timestamp when cards are dealt
    update_session_activity(session_id)
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['bank'] < helpers.MIN_BET:
        return jsonify({'error': 'Insufficient funds. Please reset your bank.'}), 400
    
    if game_state['current_bet'] > game_state['bank']:
        game_state['current_bet'] = min(game_state['bank'], game_state['current_bet'])
    
    # Deduct bet from bank
    game_state['bank'] -= game_state['current_bet']
    
    # Reset game state but keep bank
    bank_backup = game_state['bank']
    current_bet_backup = game_state['current_bet']
    helpers.reset_game_state(session_id)
    game_state = helpers.get_session_state(session_id)
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

    card1 = helpers.deal_card(session_id)
    card2 = helpers.deal_card(session_id)
    card3 = helpers.deal_card(session_id)
    card4 = helpers.deal_card(session_id)
    
    active_hand = game_state['player_hands'][0]
    
    active_hand['hand'].append(card1)
    send_to_arduino(session_id, card1)
    
    game_state['dealer_hand'].append(card2)
    
    active_hand['hand'].append(card3)
    send_to_arduino(session_id, card3)
    
    game_state['dealer_hand'].append(card4)
    send_to_arduino(session_id, card4)
    
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    game_state['dealer_value'] = helpers.CARD_VALUES[card4[:-1]]
    
    if active_hand['value'] == 21:
        active_hand['status'] = 'blackjack'
        game_state['message'] = "Blackjack! Let's see what the dealer has..."
        game_state['active_hand_index'] = -1
        helpers.dealer_plays(session_id, lambda msg: send_to_arduino(session_id, msg))
    else:
        game_state['message'] = f"Your turn for Hand 1 (Bet: ${game_state['current_bet']})"
        helpers.update_hand_options(session_id)
    
    return jsonify(game_state)

@app.route('/hit', methods=['POST'])
def hit():
    """Player hits - deal another card"""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]

    new_card = helpers.deal_card(session_id)
    active_hand['hand'].append(new_card)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    
    send_to_arduino(session_id, new_card)
    
    game_state['can_double'] = False
    game_state['can_split'] = False
    
    if active_hand['value'] > 21:
        active_hand['status'] = 'bust'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} busts!"
        helpers.move_to_next_hand(session_id)
    elif active_hand['value'] == 21:
        active_hand['status'] = 'stood'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} has 21!"
        helpers.move_to_next_hand(session_id)
    
    return jsonify(game_state)

@app.route('/stand', methods=['POST'])
def stand():
    """Player stands - dealer's turn"""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'playing':
        return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    active_hand['status'] = 'stood'
    
    game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} stands."
    helpers.move_to_next_hand(session_id)
    
    return jsonify(game_state)

@app.route('/double', methods=['POST'])
def double_down():
    """Player doubles down."""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'playing' or not game_state['can_double']:
        return jsonify({'error': 'Cannot double down now'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    
    # Deduct additional bet from bank
    game_state['bank'] -= active_hand['bet']
    active_hand['bet'] *= 2
    
    new_card = helpers.deal_card(session_id)
    active_hand['hand'].append(new_card)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    send_to_arduino(session_id, new_card)
    
    game_state['can_double'] = False
    game_state['can_split'] = False
    
    if active_hand['value'] > 21:
        active_hand['status'] = 'bust'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} busts on double!"
    else:
        active_hand['status'] = 'stood'
        game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} doubles and stands."
    
    helpers.move_to_next_hand(session_id)
    return jsonify(game_state)

@app.route('/split', methods=['POST'])
def split():
    """Player splits a pair."""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'playing' or not game_state['can_split']:
        return jsonify({'error': 'Cannot split now'}), 400
    
    # Deduct additional bet from bank
    game_state['bank'] -= game_state['current_bet']
        
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    card_to_move = active_hand['hand'].pop()
    
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    
    new_hand = {
        'hand': [card_to_move],
        'value': helpers.calculate_hand_value([card_to_move]),
        'status': 'pending',
        'bet': game_state['current_bet']
    }
    
    game_state['player_hands'].insert(game_state['active_hand_index'] + 1, new_hand)
    
    new_card_1 = helpers.deal_card(session_id)
    active_hand['hand'].append(new_card_1)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    send_to_arduino(session_id, new_card_1)
    
    time.sleep(0.5)
    
    new_card_2 = helpers.deal_card(session_id)
    new_hand['hand'].append(new_card_2)
    new_hand['value'] = helpers.calculate_hand_value(new_hand['hand'])
    send_to_arduino(session_id, new_card_2)
    
    rank1 = active_hand['hand'][0][:-1]
    is_ace_split = (helpers.CARD_VALUES[rank1] == 11)
    
    if is_ace_split:
        active_hand['status'] = 'stood'
        new_hand['status'] = 'stood'
        game_state['message'] = "Split Aces! Each hand gets one card and stands."
        helpers.move_to_next_hand(session_id)
    else:
        helpers.update_hand_options(session_id)
        
        if active_hand['value'] == 21:
            active_hand['status'] = 'stood'
            helpers.move_to_next_hand(session_id)
        else:
            game_state['message'] = f"Split! Your turn for Hand {game_state['active_hand_index'] + 1}"

    return jsonify(game_state)

@app.route('/dealer_step', methods=['POST'])
def dealer_step():
    """Performs one step of the dealer's turn."""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'dealer_turn':
        return jsonify({'error': 'Not dealer\'s turn'}), 400

    # Step 1: Reveal hidden card if it's the first step
    if game_state['dealer_hidden']:
        game_state['dealer_hidden'] = False
        game_state['dealer_value'] = helpers.calculate_hand_value(game_state['dealer_hand'])
        send_to_arduino(session_id, game_state['dealer_hand'][0])
        game_state['message'] = f"Dealer reveals. Value is {game_state['dealer_value']}"
        
        if game_state['dealer_value'] >= 17:
            helpers.determine_winners(session_id)
        
        return jsonify(game_state)

    # Step 2: Draw a card if under 17
    if game_state['dealer_value'] < 17:
        new_card = helpers.deal_card(session_id)
        game_state['dealer_hand'].append(new_card)
        game_state['dealer_value'] = helpers.calculate_hand_value(game_state['dealer_hand'])
        send_to_arduino(session_id, new_card)
        
        if game_state['dealer_value'] > 21:
            game_state['message'] = "Dealer busts!"
        else:
            game_state['message'] = f"Dealer hits. Value is {game_state['dealer_value']}"
        
        if game_state['dealer_value'] >= 17:
            helpers.determine_winners(session_id)
    
    elif game_state['game_status'] != 'complete':
        helpers.determine_winners(session_id)

    return jsonify(game_state)

@app.route('/shuffle', methods=['POST'])
def shuffle():
    """Shuffle the deck and notify Arduino"""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot shuffle during a game'}), 400
    
    helpers.build_shoe(session_id)
    send_to_arduino(session_id, "0")
    game_state['cards_remaining'] = helpers.get_shoe_count(session_id)
    game_state['message'] = f"Deck shuffled! {game_state['cards_remaining']} cards remaining."
    
    return jsonify(game_state)

@app.route('/reset_bank', methods=['POST'])
def reset_bank():
    """Reset the player's bank to starting amount"""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot reset bank during a game'}), 400
    
    game_state['bank'] = helpers.STARTING_BANK
    game_state['message'] = f"Bank reset to ${helpers.STARTING_BANK}!"
    
    return jsonify(game_state)

@app.route('/state', methods=['GET'])
def get_state():
    """Get current game state"""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    # Initialize if doesn't exist
    if session_id not in helpers.session_states:
        helpers.init_session_state(session_id)
        helpers.build_shoe(session_id)
        setup_mqtt_client(session_id)
        update_session_activity(session_id)
    
    game_state = helpers.get_session_state(session_id)
    client_info = get_mqtt_client(session_id)
    
    # Include MQTT config in response
    response = dict(game_state)
    response['mqtt_config'] = {
        'broker': client_info['broker'],
        'port': client_info['port'],
        'topic': client_info['topic']
    }
    
    return jsonify(response)

@app.route('/update_mqtt', methods=['POST'])
def update_mqtt():
    """Update MQTT configuration"""
    session_id = get_session_id_from_request()
    if not session_id:
        return jsonify({'error': 'No session ID provided'}), 400
    
    data = request.get_json()
    new_broker = data.get('broker')
    new_port = data.get('port')
    new_topic = data.get('topic')
    
    # Validate inputs
    if not new_broker or not new_topic:
        return jsonify({'error': 'Broker and topic cannot be empty'}), 400
    
    try:
        new_port = int(new_port)
        if new_port < 1 or new_port > 65535:
            return jsonify({'error': 'Port must be between 1 and 65535'}), 400
    except ValueError:
        return jsonify({'error': 'Invalid port number'}), 400
    
    client_info = get_mqtt_client(session_id)
    
    # Disconnect old client
    try:
        client_info['client'].loop_stop()
        client_info['client'].disconnect()
        client_info['connected'] = False
    except:
        pass
    
    # Update configuration
    client_info['broker'] = new_broker
    client_info['port'] = new_port
    client_info['topic'] = new_topic
    
    # Reconnect with new settings
    try:
        client_info['client'].connect(new_broker, new_port, 60)
        client_info['client'].loop_start()
        client_info['connected'] = True
        return jsonify({
            'broker': new_broker,
            'port': new_port,
            'topic': new_topic,
            'message': 'MQTT configuration updated successfully'
        })
    except Exception as e:
        return jsonify({'error': f'Failed to connect: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)