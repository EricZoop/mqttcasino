import random
import threading
import time

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

# --- Session-based Storage ---
# Dictionary to store game state per session
session_states = {}
session_shoes = {}
shoe_locks = {}

def init_session_state(session_id):
    """Initialize game state for a new session"""
    if session_id not in session_states:
        session_states[session_id] = {
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
            'cards_remaining': 0
        }
        session_shoes[session_id] = []
        shoe_locks[session_id] = threading.Lock()

def get_session_state(session_id):
    """Get the game state for a session"""
    if session_id not in session_states:
        init_session_state(session_id)
    return session_states[session_id]

def reset_game_state(session_id):
    """Reset the game state for a session"""
    if session_id not in session_states:
        init_session_state(session_id)
    else:
        state = session_states[session_id]
        state['player_hands'] = []
        state['active_hand_index'] = -1
        state['dealer_hand'] = []
        state['dealer_value'] = 0
        state['dealer_hidden'] = True
        state['game_status'] = 'waiting'
        state['message'] = 'Place your bet to start'
        state['can_split'] = False
        state['can_double'] = False
        state['cards_remaining'] = len(session_shoes.get(session_id, []))

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

def _build_shoe_internal():
    """Internal helper to build shoe without locking"""
    one_deck = []
    for suit in CARD_SUITS:
        for rank in CARD_RANKS:
            one_deck.append(f"{rank}{suit}")
    
    return one_deck * NUMBER_OF_DECKS

def build_shoe(session_id):
    """Creates a new, shuffled shoe for a session"""
    if session_id not in session_shoes:
        session_shoes[session_id] = []
    if session_id not in shoe_locks:
        shoe_locks[session_id] = threading.Lock()
    
    new_shoe = _build_shoe_internal()
    
    with shoe_locks[session_id]:
        session_shoes[session_id] = new_shoe
        random.shuffle(session_shoes[session_id])
        print(f"[{session_id[:8]}] Shoe created with {len(session_shoes[session_id])} cards")

def get_shoe_count(session_id):
    """Get the number of cards remaining in the shoe"""
    return len(session_shoes.get(session_id, []))

def deal_card(session_id):
    """Deal a single card from the shoe for a session"""
    if session_id not in session_shoes:
        build_shoe(session_id)
    
    state = get_session_state(session_id)
    
    with shoe_locks[session_id]:
        if len(session_shoes[session_id]) < (52 * NUMBER_OF_DECKS * 0.25):
            print(f"[{session_id[:8]}] Shoe penetration low, rebuilding...")
            new_shoe = _build_shoe_internal()
            session_shoes[session_id] = new_shoe
            random.shuffle(session_shoes[session_id])
            print(f"[{session_id[:8]}] Shoe rebuilt with {len(session_shoes[session_id])} cards")
        
        card = session_shoes[session_id].pop()
        state['cards_remaining'] = len(session_shoes[session_id])
        return card

def update_hand_options(session_id):
    """Updates can_split and can_double for the active hand."""
    state = get_session_state(session_id)
    
    if state['game_status'] != 'playing' or state['active_hand_index'] == -1:
        state['can_split'] = False
        state['can_double'] = False
        return

    active_hand = state['player_hands'][state['active_hand_index']]
    
    if len(active_hand['hand']) == 2:
        state['can_double'] = state['bank'] >= active_hand['bet']
        
        rank1 = active_hand['hand'][0][:-1]
        rank2 = active_hand['hand'][1][:-1]
        state['can_split'] = (rank1 == rank2 and 
                            state['bank'] >= state['current_bet'])
    else:
        state['can_double'] = False
        state['can_split'] = False

def move_to_next_hand(session_id, send_func=None):
    """Moves focus to the next hand, or triggers dealer's turn if all hands are played."""
    state = get_session_state(session_id)
    
    state['active_hand_index'] += 1
    
    if state['active_hand_index'] < len(state['player_hands']):
        active_hand = state['player_hands'][state['active_hand_index']]
        
        if active_hand['value'] == 21 and len(active_hand['hand']) == 2:
            active_hand['status'] = 'blackjack'
            state['message'] = f"Hand {state['active_hand_index'] + 1} has Blackjack!"
            # Recursively call with the send_func
            move_to_next_hand(session_id, send_func)
        else:
            active_hand['status'] = 'playing'
            state['message'] = f"Your turn for Hand {state['active_hand_index'] + 1}"
            update_hand_options(session_id)
            
    else:
        all_busted = all(hand['status'] == 'bust' for hand in state['player_hands'])
        
        if all_busted:
            state['game_status'] = 'complete'
            state['can_split'] = False
            state['can_double'] = False
            state['dealer_hidden'] = False
            
            # --- FIX STARTS HERE ---
            # If provided, send the MQTT message to reveal the hole card
            if send_func and len(state['dealer_hand']) > 0:
                send_func(state['dealer_hand'][0])
            # --- FIX ENDS HERE ---
            
            final_messages = []
            for i, p_hand in enumerate(state['player_hands']):
                p_hand['status'] = 'lose'
                final_messages.append(f"Hand {i + 1} busts (-${p_hand['bet']})")
            
            state['message'] = ". ".join(final_messages) + f". Bank: ${state['bank']}"
        else:
            state['game_status'] = 'dealer_turn'
            state['can_split'] = False
            state['can_double'] = False
            state['message'] = "Dealer's turn..."

def dealer_plays(session_id, send_func):
    """
    Logic for the dealer's turn.
    Accepts a function `send_func` to send MQTT messages.
    """
    state = get_session_state(session_id)
    
    state['dealer_hidden'] = False
    state['dealer_value'] = calculate_hand_value(state['dealer_hand'])
    
    send_func(state['dealer_hand'][0])
    
    while state['dealer_value'] < 17:
        time.sleep(1.2)
        new_card = deal_card(session_id)
        state['dealer_hand'].append(new_card)
        time.sleep(1.2)
        state['dealer_value'] = calculate_hand_value(state['dealer_hand'])
        send_func(new_card)
    
    determine_winners(session_id)

def determine_winners(session_id):
    """Compares all player hands to the dealer's hand and updates bank."""
    state = get_session_state(session_id)
    
    dealer_val = state['dealer_value']
    dealer_bust = dealer_val > 21
    final_messages = []
    dealer_has_blackjack = dealer_val == 21 and len(state['dealer_hand']) == 2
    
    for i, p_hand in enumerate(state['player_hands']):
        hand_num = i + 1
        bet = p_hand['bet']
        
        if p_hand['status'] == 'bust':
            p_hand['status'] = 'lose'
            final_messages.append(f"Hand {hand_num} busts (-${bet})")
        
        elif p_hand['status'] == 'blackjack':
            if dealer_has_blackjack:
                p_hand['status'] = 'tie'
                state['bank'] += bet
                final_messages.append(f"Hand {hand_num} pushes (${bet})")
            else:
                p_hand['status'] = 'win'
                winnings = int(bet * 2.5)
                state['bank'] += winnings
                final_messages.append(f"Hand {hand_num} BLACKJACK! (+${winnings - bet})")
        
        elif p_hand['status'] == 'stood':
            hand_val = p_hand['value']
            if dealer_bust:
                p_hand['status'] = 'win'
                state['bank'] += bet * 2
                final_messages.append(f"Hand {hand_num} wins (+${bet})")
            elif hand_val > dealer_val:
                p_hand['status'] = 'win'
                state['bank'] += bet * 2
                final_messages.append(f"Hand {hand_num} wins (+${bet})")
            elif hand_val < dealer_val:
                p_hand['status'] = 'lose'
                final_messages.append(f"Hand {hand_num} loses (-${bet})")
            else:
                p_hand['status'] = 'tie'
                state['bank'] += bet
                final_messages.append(f"Hand {hand_num} pushes (${bet})")
    
    state['game_status'] = 'complete'
    state['message'] = ". ".join(final_messages) + f". Bank: ${state['bank']}"