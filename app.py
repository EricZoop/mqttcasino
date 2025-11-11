import paho.mqtt.client as mqtt
from flask import Flask, render_template, request, jsonify
import time

# --- MQTT Configuration ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
# This topic MUST match the topic in your Arduino code
MQTT_TOPIC = "arduino/blackjack_table1"

# --- Flask App ---
app = Flask(__name__)

# --- MQTT Client Setup ---
# *** FIX: Create a single client instance outside the functions ***
mqtt_client = mqtt.Client("flask_publisher_" + str(time.time()))

def setup_mqtt_client():
    """Connects the global client and starts its network loop."""
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        # Starts a background thread to handle MQTT network communication
        mqtt_client.loop_start() 
        print("MQTT Client Connected and loop started.")
    except Exception as e:
        print(f"Failed to connect MQTT client: {e}")

@app.route('/')
def index():
    """Render the main HTML page."""
    # Pass the topic to the template (optional, but good practice)
    return render_template('index.html', MQTT_TOPIC=MQTT_TOPIC)

@app.route('/send_message', methods=['POST'])
def send_message():
    """
    API endpoint to receive a message from the webpage and publish it to MQTT.
    """
    message = request.form.get('message')
    
    if not message:
        return jsonify({"status": "error", "message": "Message is empty"}), 400

    try:
        # *** FIX: Use the existing global client to publish ***
        result = mqtt_client.publish(MQTT_TOPIC, message, retain=False)
        
        # Check if the message was successfully queued
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"Published '{message}' to topic '{MQTT_TOPIC}'")
            return jsonify({"status": "success", "message": message})
        else:
            print(f"Failed to publish. Error code: {result.rc}")
            return jsonify({"status": "error", "message": f"MQTT Error: {result.rc}"}), 500
            
    except Exception as e:
        print(f"An error occurred: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # *** FIX: Setup the client before running the app ***
    setup_mqtt_client()
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=True)