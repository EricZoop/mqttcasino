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

def _build_shoe_internal():
    """Internal helper to build shoe without locking"""
    one_deck = []
    for suit in CARD_SUITS:
        for rank in CARD_RANKS:
            one_deck.append(f"{rank}{suit}")
    
    return one_deck * NUMBER_OF_DECKS

def build_shoe():
    """Creates a new, shuffled shoe"""
    global current_shoe
    
    new_shoe = _build_shoe_internal()
    
    with shoe_lock:
        current_shoe = new_shoe
        random.shuffle(current_shoe)
        print(f"Shoe created with {len(current_shoe)} cards")

def deal_card():
    """Deal a single card from the shoe"""
    global current_shoe
    global game_state
    
    with shoe_lock:
        if len(current_shoe) < (52 * NUMBER_OF_DECKS * 0.25):
            print("Shoe penetration low, rebuilding...")
            # Rebuild directly without releasing/reacquiring lock
            new_shoe = _build_shoe_internal()
            current_shoe = new_shoe
            random.shuffle(current_shoe)
            print(f"Shoe rebuilt with {len(current_shoe)} cards")
        
        card = current_shoe.pop()
        if 'cards_remaining' in game_state:
            game_state['cards_remaining'] = len(current_shoe)
        return card

def update_hand_options():
    """Updates can_split and can_double for the active hand."""
    global game_state
    
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

def dealer_plays(send_func):
    """
    Logic for the dealer's turn.
    Accepts a function `send_func` to send MQTT messages.
    """
    global game_state
    
    game_state['dealer_hidden'] = False
    game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand'])
    
    send_func(game_state['dealer_hand'][0])
    
    while game_state['dealer_value'] < 17:
        time.sleep(1.0)
        new_card = deal_card()
        game_state['dealer_hand'].append(new_card)
        time.sleep(1.0)
        game_state['dealer_value'] = calculate_hand_value(game_state['dealer_hand'])
        send_func(new_card)
    
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