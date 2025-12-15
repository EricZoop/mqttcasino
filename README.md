# MQTT Casino

This fantastic repository consists of two parts: The Arduino code (everything contained in the cardcount_nano33iot folder) and the Python Flask Application (everything else).
The Arduino code was built to run on an Arduino Nano 33 IoT and connect with a session of the Flask application via MQTT.
The Flask application can be run locally, but is being hosted on OCI and can be accessed at 157.151.158.181:5000/ on a web browser.

Python 3.9.7

Clone repository
```cmd
git clone https://github.com/EricZoop/mqttcasino.git
cd mqttcasino
```

Create enviorment
```cmd
python -m venv venv
```

Activate
```cmd
venv\Scripts\activate
```

Install dependencies
```cmd
pip install -r requirements.txt
```

Run
```cmd
python app.py
```

Card images from 
https://www.flaticon.com/packs/playing-cards-15556280
