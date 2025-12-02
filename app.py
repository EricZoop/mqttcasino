from flask import Flask, render_template, jsonify, request # type: ignore
import time
import helpers
import secrets
import threading
from mqtt_service import MqttService

app = Flask(__name__)
mqtt_service = MqttService()

# --- Session Management ---
SESSION_TIMEOUT_SECONDS = 10 * 60  # 10 minutes
SESSION_CLEANUP_INTERVAL = 60
session_last_activity = {}

def update_session_activity(session_id):
    session_last_activity[session_id] = time.time()

def cleanup_inactive_sessions():
    """Background thread to cleanup inactive sessions"""
    while True:
        time.sleep(SESSION_CLEANUP_INTERVAL)
        current_time = time.time()
        sessions_to_delete = []
        
        for session_id, last_activity in list(session_last_activity.items()):
            if current_time - last_activity > SESSION_TIMEOUT_SECONDS:
                sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            try:
                # Delegate MQTT cleanup to the service
                mqtt_service.disconnect_session(session_id)
                
                if session_id in helpers.session_states:
                    del helpers.session_states[session_id]
                
                if session_id in session_last_activity:
                    del session_last_activity[session_id]
                
                print(f"[CLEANUP] Session {session_id[:8]} deleted due to inactivity")
            except Exception as e:
                print(f"[CLEANUP] Error cleaning up session {session_id[:8]}: {e}")

cleanup_thread = threading.Thread(target=cleanup_inactive_sessions, daemon=True)
cleanup_thread.start()

def get_session_id():
    """Helper to extract session ID from JSON body or Args"""
    if request.is_json:
        data = request.get_json()
        if data and 'session_id' in data:
            return data['session_id']
    return request.args.get('session_id')

# --- Routes ---

@app.route('/')
def index():
    return render_template('blackjack.html')

@app.route('/init_session', methods=['POST'])
def init_session():
    new_session_id = secrets.token_hex(16)
    
    # Initialize game state
    helpers.init_session_state(new_session_id)
    helpers.build_shoe(new_session_id)
    update_session_activity(new_session_id)
    
    # Initialize MQTT via Service
    mqtt_service.create_client(new_session_id)
    mqtt_service.connect_client(new_session_id)
    
    config = mqtt_service.get_config(new_session_id)
    
    return jsonify({
        'session_id': new_session_id,
        'broker': config['broker'],
        'port': config['port'],
        'topic': config['topic'],
        'message': f'Session created: {new_session_id[:5]}'
    })

@app.route('/host_table', methods=['POST'])
def host_table():
    return init_session()

@app.route('/set_bet', methods=['POST'])
def set_bet():
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    
    update_session_activity(session_id)
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
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    
    update_session_activity(session_id)
    game_state = helpers.get_session_state(session_id)
    
    if game_state['bank'] < helpers.MIN_BET:
        return jsonify({'error': 'Insufficient funds. Please reset your bank.'}), 400
    
    if game_state['current_bet'] > game_state['bank']:
        game_state['current_bet'] = min(game_state['bank'], game_state['current_bet'])
    
    # Deduct bet and reset state
    game_state['bank'] -= game_state['current_bet']
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
    
    # Player Card 1
    active_hand['hand'].append(card1)
    mqtt_service.publish_card(session_id, card1)
    
    # Dealer Card 1 (Hidden)
    game_state['dealer_hand'].append(card2)
    
    # Player Card 2
    active_hand['hand'].append(card3)
    mqtt_service.publish_card(session_id, card3)
    
    # Dealer Card 2 (Visible)
    game_state['dealer_hand'].append(card4)
    mqtt_service.publish_card(session_id, card4)
    
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    game_state['dealer_value'] = helpers.CARD_VALUES[card4[:-1]]
    
    if active_hand['value'] == 21:
        active_hand['status'] = 'blackjack'
        game_state['message'] = "Blackjack! Let's see what the dealer has..."
        game_state['active_hand_index'] = -1
        # Use lambda to route dealer actions through our service
        helpers.dealer_plays(session_id, lambda msg: mqtt_service.publish_card(session_id, msg))
    else:
        game_state['message'] = f"Your turn for Hand 1 (Bet: ${game_state['current_bet']})"
        helpers.update_hand_options(session_id)
    
    return jsonify(game_state)

@app.route('/hit', methods=['POST'])
def hit():
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    update_session_activity(session_id)
    
    game_state = helpers.get_session_state(session_id)
    if game_state['game_status'] != 'playing': return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]

    new_card = helpers.deal_card(session_id)
    active_hand['hand'].append(new_card)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    
    mqtt_service.publish_card(session_id, new_card)
    
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
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    update_session_activity(session_id)
    
    game_state = helpers.get_session_state(session_id)
    if game_state['game_status'] != 'playing': return jsonify({'error': 'Game not in progress'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    active_hand['status'] = 'stood'
    
    game_state['message'] = f"Hand {game_state['active_hand_index'] + 1} stands."
    helpers.move_to_next_hand(session_id)
    
    return jsonify(game_state)

@app.route('/double', methods=['POST'])
def double_down():
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    update_session_activity(session_id)
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'playing' or not game_state['can_double']:
        return jsonify({'error': 'Cannot double down now'}), 400
    
    active_hand = game_state['player_hands'][game_state['active_hand_index']]
    
    # Deduct additional bet
    game_state['bank'] -= active_hand['bet']
    active_hand['bet'] *= 2
    
    new_card = helpers.deal_card(session_id)
    active_hand['hand'].append(new_card)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    
    mqtt_service.publish_card(session_id, new_card)
    
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
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    update_session_activity(session_id)
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'playing' or not game_state['can_split']:
        return jsonify({'error': 'Cannot split now'}), 400
    
    # Deduct additional bet
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
    
    # Deal to first hand
    new_card_1 = helpers.deal_card(session_id)
    active_hand['hand'].append(new_card_1)
    active_hand['value'] = helpers.calculate_hand_value(active_hand['hand'])
    mqtt_service.publish_card(session_id, new_card_1)
    
    time.sleep(0.5)
    
    # Deal to second (new) hand
    new_card_2 = helpers.deal_card(session_id)
    new_hand['hand'].append(new_card_2)
    new_hand['value'] = helpers.calculate_hand_value(new_hand['hand'])
    mqtt_service.publish_card(session_id, new_card_2)
    
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
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] != 'dealer_turn':
        return jsonify({'error': 'Not dealer\'s turn'}), 400

    # Step 1: Reveal hidden card
    if game_state['dealer_hidden']:
        game_state['dealer_hidden'] = False
        game_state['dealer_value'] = helpers.calculate_hand_value(game_state['dealer_hand'])
        
        mqtt_service.publish_card(session_id, game_state['dealer_hand'][0])
        game_state['message'] = f"Dealer reveals. Value is {game_state['dealer_value']}"
        
        if game_state['dealer_value'] >= 17:
            helpers.determine_winners(session_id)
        
        return jsonify(game_state)

    # Step 2: Draw card if < 17
    if game_state['dealer_value'] < 17:
        new_card = helpers.deal_card(session_id)
        game_state['dealer_hand'].append(new_card)
        game_state['dealer_value'] = helpers.calculate_hand_value(game_state['dealer_hand'])
        
        mqtt_service.publish_card(session_id, new_card)
        
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
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot shuffle during a game'}), 400
    
    helpers.build_shoe(session_id)
    # Send shuffle signal (0)
    mqtt_service.publish_card(session_id, "0")
    
    game_state['cards_remaining'] = helpers.get_shoe_count(session_id)
    game_state['message'] = f"Deck shuffled! {game_state['cards_remaining']} cards remaining."
    
    return jsonify(game_state)

@app.route('/reset_bank', methods=['POST'])
def reset_bank():
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    
    game_state = helpers.get_session_state(session_id)
    
    if game_state['game_status'] == 'playing':
        return jsonify({'error': 'Cannot reset bank during a game'}), 400
    
    game_state['bank'] = helpers.STARTING_BANK
    game_state['message'] = f"Bank reset to ${helpers.STARTING_BANK}!"
    
    return jsonify(game_state)

@app.route('/state', methods=['GET'])
def get_state():
    session_id = request.args.get('session_id')
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    
    # Initialize if doesn't exist
    if session_id not in helpers.session_states:
        helpers.init_session_state(session_id)
        helpers.build_shoe(session_id)
        mqtt_service.create_client(session_id)
        update_session_activity(session_id)
    
    game_state = helpers.get_session_state(session_id)
    config = mqtt_service.get_config(session_id)
    
    response = dict(game_state)
    response['mqtt_config'] = config
    
    return jsonify(response)

@app.route('/update_mqtt', methods=['POST'])
def update_mqtt():
    session_id = get_session_id()
    if not session_id: return jsonify({'error': 'No session ID provided'}), 400
    
    data = request.get_json()
    new_broker = data.get('broker')
    new_port = data.get('port')
    new_topic = data.get('topic')
    
    if not new_broker or not new_topic:
        return jsonify({'error': 'Broker and topic cannot be empty'}), 400
    
    try:
        new_port = int(new_port)
    except ValueError:
        return jsonify({'error': 'Invalid port number'}), 400
    
    # Use service to recreate
    try:
        mqtt_service.create_client(session_id, broker=new_broker, port=new_port, topic=new_topic)
        success = mqtt_service.connect_client(session_id)
        
        if success:
            return jsonify({
                'broker': new_broker, 
                'port': new_port, 
                'topic': new_topic, 
                'message': 'MQTT configuration updated and connected'
            })
        else:
            return jsonify({
                'broker': new_broker, 
                'port': new_port, 
                'topic': new_topic, 
                'message': 'MQTT updated, connecting in background...'
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)