import json
import time
import logging
from datetime import datetime
from collections import deque
import asyncio
import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)

class OneMeterSensorAsync:
    def __init__(self, hass, entry):
        self.hass = hass
        self.mqtt_config = entry.data
        self.total_impulses = 0
        self.impulse_window = deque()
        self.last_timestamp = None
        self.device_id = "om9613"
        self.client = None
        self.heartbeat_interval = self.mqtt_config.get("heartbeat_interval", 30)

    async def start(self):
        """Uruchamia klienta MQTT i loop asyncio"""
        loop = asyncio.get_running_loop()
        self.client = mqtt.Client()
        self.client.username_pw_set(
            self.mqtt_config["mqtt_user"],
            self.mqtt_config["mqtt_pass"]
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        _LOGGER.info(f"Łączenie z brokerem MQTT {self.mqtt_config['mqtt_broker']}...")
        await loop.run_in_executor(None, self.client.connect,
                                   self.mqtt_config["mqtt_broker"],
                                   self.mqtt_config["mqtt_port"],
                                   60)
        self.client.loop_start()

        # Pętla heartbeat
        asyncio.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        """Publikacja heartbeat co X sekund"""
        while True:
            self.client.publish(f"onemeter/energy/{self.device_id}/status", "online", qos=1, retain=True)
            await asyncio.sleep(self.heartbeat_interval)

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            _LOGGER.info(f"Połączono z brokerem MQTT {self.mqtt_config['mqtt_broker']}")
        else:
            _LOGGER.error(f"Błąd połączenia z MQTT, kod {rc}")
            return

        client.subscribe("onemeter/s10/v1")
        self.publish_discovery()
        self.publish_state(initial=True)

    def publish_discovery(self):
        """Publikuje konfigurację MQTT discovery dla Home Assistant"""
        device_info = {
            "identifiers": [f"onemeter_{self.device_id}"],
            "name": "OneMeter",
            "manufacturer": "OneMeter",
            "model": "OneMeter Energy Monitor"
        }

        availability_topic = f"onemeter/energy/{self.device_id}/status"

        sensors = [
            {
                "name": "OneMeter Energy",
                "unique_id": f"{self.device_id}_energy_kwh",
                "state_topic": f"onemeter/energy/{self.device_id}/state",
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "value_template": "{{ value_json.kwh }}",
                "state_class": "total_increasing",
                "device": device_info,
                "availability_topic": availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline"
            },
            {
                "name": "OneMeter Power",
                "unique_id": f"{self.device_id}_power_kw",
                "state_topic": f"onemeter/energy/{self.device_id}/state",
                "unit_of_measurement": "kW",
                "device_class": "power",
                "value_template": "{{ value_json.power_kw }}",
                "state_class": "measurement",
                "device": device_info,
                "availability_topic": availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline"
            },
            {
                "name": "OneMeter Timestamp",
                "unique_id": f"{self.device_id}_timestamp",
                "state_topic": f"onemeter/energy/{self.device_id}/state",
                "value_template": "{{ value_json.timestamp }}",
                "icon": "mdi:clock-outline",
                "device": device_info,
                "availability_topic": availability_topic,
                "payload_available": "online",
                "payload_not_available": "offline"
            }
        ]

        for sensor in sensors:
            topic = f"homeassistant/sensor/OneMeter/{sensor['unique_id']}/config"
            self.client.publish(topic, json.dumps(sensor), qos=1, retain=True)
            _LOGGER.info(f"Opublikowano MQTT discovery dla {sensor['name']}")

    def publish_state(self, initial=False):
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

        if initial:
            kwh = 0.0
            power_kw = 0.0
        else:
            window_seconds = self.mqtt_config.get("window_seconds", 60)
            impulses_in_window = len(self.impulse_window)
            power_kw = (impulses_in_window / 1000) * (3600 / window_seconds)
            max_power = self.mqtt_config.get("max_power_kw", 20.0)
            if max_power and power_kw > max_power:
                power_kw = max_power
            kwh = self.total_impulses / 1000

        mqtt_payload = {
            "timestamp": timestamp_str,
            "impulses": self.total_impulses,
            "kwh": round(kwh, 3),
            "power_kw": round(power_kw, 2)
        }

        self.client.publish(f"onemeter/energy/{self.device_id}/state", json.dumps(mqtt_payload), qos=1, retain=True)
        _LOGGER.info(f"Opublikowano stan energy: {mqtt_payload}")

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

            self.total_impulses += 1
            now = time.time()
            self.impulse_window.append(now)
            window_seconds = self.mqtt_config.get("window_seconds", 60)
            while self.impulse_window and (now - self.impulse_window[0]) > window_seconds:
                self.impulse_window.popleft()

            self.publish_state()
        except Exception as e:
            _LOGGER.error(f"Błąd przetwarzania wiadomości: {e}")
