import paho.mqtt.client as mqtt
from flask import Flask, render_template, jsonify
import time
import random
import threading

# --- MQTT Configuration ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "ece508/blackjack_table1"ano

# --- App Configuration ---
app = Flask(__name__)
mqtt_client = mqtt.Client("flask_publisher_" + str(time.time()))

# --- Card Deck Configuration ---
# All the card *ranks* in a single deck.
CARD_CHARACTERS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2']
# Set how many decks are in the shoe
NUMBER_OF_DECKS = 6

# --- Global state for the shoe and thread control ---
current_shoe = []
shoe_lock = threading.Lock() # Protects access to the current_shoe list
sending_active = False
sender_thread = None

def build_shoe():
    """
    Creates a new, shuffled shoe based on the deck configuration.
    This function is thread-safe.
    """
    global current_shoe
    # A standard deck has 4 suits, so 4 of each card character
    one_deck = CARD_CHARACTERS * 4
    
    with shoe_lock:
        current_shoe = one_deck * NUMBER_OF_DECKS
        random.shuffle(current_shoe)
        print(f"--- SHOE CREATED ---")
        print(f"Decks: {NUMBER_OF_DECKS}")
        print(f"Cards per deck: {len(one_deck)}")
        print(f"Total cards in shoe: {len(current_shoe)}")

def message_sender_loop():
    """A loop that sends one card from the shoe every 1 sec."""
    global sending_active, current_shoe
    print("Background thread started.")
    
    char_to_send = None
    shoe_was_empty = False
    cards_remaining = 0

    while sending_active:
        with shoe_lock:
            if not current_shoe: # Check if shoe is empty
                print("--- SHOE EMPTY, SENDING RESET AND RESHUFFLING ---")
                char_to_send = '0' # Send reset signal
                shoe_was_empty = True
                
                # Rebuild and shuffle the shoe
                one_deck = CARD_CHARACTERS * 4
                current_shoe = one_deck * NUMBER_OF_DECKS
                random.shuffle(current_shoe)
            else:
                # Get the next card if shoe is not empty
                char_to_send = current_shoe.pop()
                shoe_was_empty = False
            
            cards_remaining = len(current_shoe)

        # --- Actions performed outside the lock to avoid blocking ---
        
        # Publish to MQTT
        mqtt_client.publish(MQTT_TOPIC, char_to_send)
        
        if shoe_was_empty:
            print(f"Published '0' (RESET). Shoe reshuffled with {cards_remaining} cards.")
        else:
            print(f"Published: {char_to_send} (Shoe remaining: {cards_remaining})")
        
        # Wait for 1 second
        time.sleep(1)
        
    print("Background thread stopped.")

def setup_mqtt_client():
    """Connects the global client and starts its network loop."""
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        mqtt_client.loop_start() 
        print("MQTT Client Connected.")
    except Exception as e:
        print(f"MQTT connection failed: {e}")

@app.route('/')
def index():
    """Render the main HTML page."""
    # This assumes you have a 'templates/index.html' file
    return render_template('index.html')

@app.route('/start', methods=['POST'])
def start_sending():
    """API endpoint to start the message loop."""
    global sending_active, sender_thread
    
    if not sending_active:
        print("START signal received.")
        
        # --- NEW: Send initial '0' to reset clients ---
        print("Sending initial '0' RESET signal.")
        mqtt_client.publish(MQTT_TOPIC, '0')
        # --- END NEW ---
        
        build_shoe() # Create and shuffle the shoe *after* reset
        
        sending_active = True
        # We set daemon=True so the thread automatically exits when the app quits
        sender_thread = threading.Thread(target=message_sender_loop, daemon=True)
        sender_thread.start()
        
    return jsonify({"status": "started"})

@app.route('/stop', methods=['POST'])
def stop_sending():
    """API endpoint to stop the message loop."""
    global sending_active
    
    if sending_active:
        sending_active = False
        print("STOP signal received.")
        
    return jsonify({"status": "stopped"})

if __name__ == '__main__':
    setup_mqtt_client()
    # Setting debug=False is important for production and ensures
    # the app doesn't restart, which would mess with the thread.
    # Using 'allow_unsafe_werkzeug=True' is for development to run with debug.
    # For a real deployment, use a production server like Gunicorn.
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)