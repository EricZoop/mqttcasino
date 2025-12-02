import paho.mqtt.client as mqtt # type: ignore
import time
import threading

class MqttService:
    def __init__(self):
        # Default Credentials
        self.DEFAULT_USERNAME = "public"
        self.DEFAULT_PASSWORD = "public"
        self.DEFAULT_BROKER = "public.cloud.shiftr.io"
        self.DEFAULT_PORT = 1883
        
        # Store MQTT clients: {session_id: {'client': obj, 'connected': bool, ...}}
        self.clients = {}

    def _get_client_data(self, session_id):
        return self.clients.get(session_id)

    def create_client(self, session_id, broker=None, port=None, topic=None):
        """Initializes an MQTT client for a specific session."""
        
        # Use defaults if not provided
        broker = broker or self.DEFAULT_BROKER
        port = port or self.DEFAULT_PORT
        topic = topic or f"gmu/ece508/team08/blkjck_{session_id[:5]}"

        # Clean up existing if present
        self.disconnect_session(session_id)

        # Create Paho Client
        client = mqtt.Client(
            client_id=f"flask_blackjack_{session_id[:8]}_{int(time.time())}",
            clean_session=True,
            protocol=mqtt.MQTTv311
        )
        client.username_pw_set(self.DEFAULT_USERNAME, self.DEFAULT_PASSWORD)

        # Initialize state dictionary
        self.clients[session_id] = {
            'client': client,
            'broker': broker,
            'port': port,
            'topic': topic,
            'connected': False,
            'connecting': False
        }

        # Define Callbacks
        def on_connect(client, userdata, flags, rc):
            if session_id in self.clients:
                if rc == 0:
                    self.clients[session_id]['connected'] = True
                    self.clients[session_id]['connecting'] = False
                    print(f"[{session_id[:5]}] MQTT Connected Successfully")
                else:
                    self.clients[session_id]['connected'] = False
                    self.clients[session_id]['connecting'] = False
                    print(f"[{session_id[:5]}] MQTT Connection Failed: RC={rc}")

        def on_disconnect(client, userdata, rc):
            if session_id in self.clients:
                self.clients[session_id]['connected'] = False
                self.clients[session_id]['connecting'] = False
                if rc != 0:
                    print(f"[{session_id[:5]}] MQTT Unexpected Disconnect: RC={rc}")

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        return self.clients[session_id]

    def connect_client(self, session_id):
        """Trigger the actual network connection."""
        data = self._get_client_data(session_id)
        if not data:
            return False

        if not data['connected'] and not data['connecting']:
            try:
                print(f"[{session_id[:5]}] Connecting to {data['broker']}...")
                data['connecting'] = True
                data['client'].connect(data['broker'], int(data['port']), 60)
                data['client'].loop_start()
                
                # Non-blocking wait (up to 2s)
                start = time.time()
                while not data['connected'] and (time.time() - start < 2):
                    time.sleep(0.1)
                
                return data['connected']
            except Exception as e:
                data['connecting'] = False
                print(f"[{session_id[:5]}] Connection Exception: {e}")
                return False
        return True

    def publish_card(self, session_id, message):
        """Publishes a card or message to the session's topic."""
        data = self._get_client_data(session_id)
        
        # Auto-heal: If missing or disconnected, try to reconnect
        if not data or not data.get('connected'):
            if not data:
                # If client doesn't exist, create it with defaults
                self.create_client(session_id)
            self.connect_client(session_id)
            data = self._get_client_data(session_id)

        if data and data['connected']:
            try:
                info = data['client'].publish(data['topic'], message)
                print(f"[{session_id[:5]}] Card sent to Arduino: {message}")
                return info.rc == 0
            except Exception as e:
                print(f"[{session_id[:5]}] Publish Error: {e}")
                return False
        else:
            print(f"[{session_id[:5]}] Failed to send '{message}' - MQTT not connected")
            return False

    def disconnect_session(self, session_id):
        """Cleanly disconnects and removes a client."""
        if session_id in self.clients:
            try:
                self.clients[session_id]['client'].loop_stop()
                self.clients[session_id]['client'].disconnect()
            except Exception as e:
                print(f"Error disconnecting {session_id}: {e}")
            finally:
                del self.clients[session_id]

    def get_config(self, session_id):
        """Returns current broker config for frontend."""
        data = self._get_client_data(session_id)
        if data:
            return {
                'broker': data['broker'],
                'port': data['port'],
                'topic': data['topic']
            }
        return {'broker': '', 'port': 0, 'topic': ''}