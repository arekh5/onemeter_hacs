import json
import time
import logging
from datetime import datetime
from collections import deque
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

class OneMeterSensor:
    def __init__(self, hass, entry):
        self.hass = hass
        self.mqtt_config = entry.data
        self.total_impulses = 0
        self.impulse_window = deque()
        self.last_timestamp = None
        self.device_id = "om9613"

    async def async_start(self):
        """Uruchom połączenie z MQTT"""
        logging.basicConfig(level=logging.INFO)
        self.client = mqtt.Client()
        self.client.username_pw_set(
            self.mqtt_config["mqtt_user"], 
            self.mqtt_config["mqtt_pass"]
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.connect(
            self.mqtt_config["mqtt_broker"], 
            self.mqtt_config["mqtt_port"], 
            60
        )
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        """Po połączeniu z MQTT brokerem"""
        _LOGGER.info(f"Połączono z MQTT brokerem {self.mqtt_config['mqtt_broker']}")
        client.subscribe("onemeter/s10/v1")
        client.publish(f"onemeter/energy/{self.device_id}/status", "online", qos=1, retain=True)

        # Publikacja discovery do Home Assistant
        self.publish_discovery()

    def publish_discovery(self):
        """Publikuje konfigurację MQTT discovery dla Home Assistant"""
        base_topic = "onemeter/sensor"
        device_info = {
            "identifiers": [f"onemeter_{self.device_id}"],
            "name": "OneMeter",
            "manufacturer": "OneMeter",
            "model": "OneMeter Energy Monitor"
        }

        sensors = [
            {
                "name": "OneMeter Energy",
                "unique_id": "onemeter_energy_kwh",
                "state_topic": f"onemeter/energy/{self.device_id}/state",
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "value_template": "{{ value_json.kwh }}",
                "state_class": "total_increasing",
                "device": device_info,
            },
            {
                "name": "OneMeter Power",
                "unique_id": "onemeter_power_kw",
                "state_topic": f"onemeter/energy/{self.device_id}/state",
                "unit_of_measurement": "kW",
                "device_class": "power",
                "value_template": "{{ value_json.power_kw }}",
                "state_class": "measurement",
                "device": device_info,
            },
            {
                "name": "OneMeter Timestamp",
                "unique_id": "onemeter_timestamp",
                "state_topic": f"onemeter/energy/{self.device_id}/state",
                "value_template": "{{ value_json.timestamp }}",
                "icon": "mdi:clock-outline",
                "device": device_info,
            }
        ]

        for sensor in sensors:
            topic = f"{base_topic}/{sensor['unique_id']}/config"
            self.client.publish(topic, json.dumps(sensor), qos=1, retain=True)
            _LOGGER.info(f"Published MQTT discovery for {sensor['name']}")

    def on_message(self, client, userdata, msg):
        """Obsługuje wiadomości MQTT"""
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

            # Licz impuls
            delta = 1
            self.total_impulses += delta

            # Okno czasowe do obliczania mocy
            now = time.time()
            self.impulse_window.append(now)
            while self.impulse_window and (now - self.impulse_window[0]) > self.mqtt_config.get("window_seconds", 60):
                self.impulse_window.popleft()

            # Moc chwilowa (kW)
            window_seconds = self.mqtt_config.get("window_seconds", 60)
            impulses_in_window = len(self.impulse_window)
            power_kw = (impulses_in_window / 1000) * (3600 / window_seconds)

            max_power = self.mqtt_config.get("max_power_kw", 20.0)
            if max_power and power_kw > max_power:
                power_kw = max_power

            # Energia całkowita (kWh)
            kwh = self.total_impulses / 1000

            # Timestamp
            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            mqtt_payload = {
                "timestamp": timestamp_str,
                "impulses": self.total_impulses,
                "kwh": round(kwh, 3),
                "power_kw": round(power_kw, 2)
            }

            client.publish(f"onemeter/energy/{self.device_id}/state", json.dumps(mqtt_payload), qos=1, retain=True)
            _LOGGER.info(f"Published energy update: {mqtt_payload}")

        except Exception as e:
            _LOGGER.error(f"Błąd przetwarzania wiadomości: {e}")
