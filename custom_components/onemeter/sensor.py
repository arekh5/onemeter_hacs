import json, time, logging
from datetime import datetime
from collections import deque
import paho.mqtt.client as mqtt
from homeassistant.helpers.entity import Entity

class OneMeterSensor:
    def __init__(self, hass, entry):
        self.hass = hass
        self.mqtt_config = entry.data
        self.total_impulses = 0
        self.impulse_window = deque()
        self.last_timestamp = None

    async def async_start(self):
        logging.basicConfig(level=logging.INFO)
        self.client = mqtt.Client()
        self.client.username_pw_set(self.mqtt_config["mqtt_user"], self.mqtt_config["mqtt_pass"])
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(self.mqtt_config["mqtt_broker"], self.mqtt_config["mqtt_port"], 60)
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        logging.info(f"Połączono z MQTT brokerem {self.mqtt_config['mqtt_broker']}")
        client.subscribe("onemeter/s10/v1")
        client.publish("onemeter/energy/om9613/status", "online", qos=1, retain=True)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            dev_list = payload.get("dev_list", [])
            if not dev_list:
                return

            device = dev_list[0]
            ts = device.get("ts")

            if ts == self.last_timestamp:
                return
            self.last_timestamp = ts

            # impuls
            delta = 1
            self.total_impulses += delta

            # okno czasowe
            now = time.time()
            self.impulse_window.append(now)
            while self.impulse_window and (now - self.impulse_window[0]) > self.mqtt_config.get("window_seconds",60):
                self.impulse_window.popleft()

            # moc chwilowa
            power_kw = (len(self.impulse_window)/1000) * (3600/self.mqtt_config.get("window_seconds",60))
            max_power = self.mqtt_config.get("max_power_kw", 20.0)
            if max_power and power_kw > max_power:
                power_kw = max_power

            # kWh
            kwh = self.total_impulses / 1000

            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            mqtt_payload = {"timestamp": timestamp_str,"impulses": self.total_impulses,"kwh": round(kwh,3),"power_kw": round(power_kw,2)}

            client.publish("onemeter/energy/om9613/state", json.dumps(mqtt_payload), qos=1, retain=True)
            client.publish("onemeter/energy/om9613/timestamp", timestamp_str, qos=1, retain=True)

        except Exception as e:
            logging.error(f"Błąd przetwarzania wiadomości: {e}")
