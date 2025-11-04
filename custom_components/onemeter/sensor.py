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

        # --- Podstawowe ---
        self.device_id = "om9613"
        self.total_impulses = 0
        self.last_timestamp = None
        self.last_message_time = 0
        self.last_impulse_times = deque(maxlen=2)
        
        # --- Parametry mocy chwilowej (k, timeout, max) ---
        self.impulses_per_kwh = self.mqtt_config.get("impulses_per_kwh", 1000)
        self.max_power_kw = self.mqtt_config.get("max_power_kw", 20.0)
        self.power_update_interval = self.mqtt_config.get("power_update_interval", 15)

        # --- Logika ostatniej znanej mocy / zerowania ---
        self.last_valid_power = 0.0
        self.power_timeout_seconds = self.mqtt_config.get("power_timeout_seconds", 300) 

        # --- Bufor do wygładzenia mocy chwilowej ---
        self.power_history = deque(maxlen=self.mqtt_config.get("power_average_window", 5))
        self.last_power_publish = 0
        self.client = None
        
    def start(self):
        """Uruchom MQTT w tle (blokująco w executorze HA)"""
        self.client = mqtt.Client()
        self.client.username_pw_set(
            self.mqtt_config["mqtt_user"],
            self.mqtt_config["mqtt_pass"]
        )

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.will_set(
            f"onemeter/energy/{self.device_id}/status",
            "offline",
            qos=1,
            retain=True
        )

        try:
            self.client.connect(
                self.mqtt_config["mqtt_broker"],
                self.mqtt_config["mqtt_port"],
                60
            )
            self.client.loop_start()
            _LOGGER.info("🚀 OneMeter MQTT client started")
        except Exception as e:
            _LOGGER.error(f"❌ Błąd połączenia MQTT: {e}")

    def stop(self):
        """Zatrzymaj MQTT"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            _LOGGER.info("🛑 OneMeter MQTT client stopped")

    def on_connect(self, client, userdata, flags, rc):
        """Połączenie z MQTT"""
        if rc == 0:
            _LOGGER.info(f"✅ Połączono z brokerem {self.mqtt_config['mqtt_broker']}")
            client.subscribe("onemeter/s10/v1", qos=1)
            client.publish(f"onemeter/energy/{self.device_id}/status", "online", qos=1, retain=True)
            self.publish_discovery()
        else:
            _LOGGER.error(f"❌ Błąd połączenia MQTT (kod {rc})")

    def publish_discovery(self):
        """Publikacja MQTT discovery dla Home Assistant"""
        base_topic = "homeassistant/sensor/onemeter"
        device_info = {
            "identifiers": [f"onemeter_{self.device_id}"],
            "name": "OneMeter",
            "manufacturer": "OneMeter",
            "model": "OM9613 Energy Monitor"
        }

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
            },
            {
                "name": "OneMeter Timestamp",
                "unique_id": f"{self.device_id}_timestamp",
                "state_topic": f"onemeter/energy/{self.device_id}/state",
                "icon": "mdi:clock-outline",
                "value_template": "{{ value_json.timestamp }}",
                "device": device_info,
            }
        ]

        for sensor in sensors:
            topic = f"{base_topic}/{sensor['unique_id']}/config"
            self.client.publish(topic, json.dumps(sensor), qos=1, retain=True)
            _LOGGER.info(f"📡 Zarejestrowano sensor HA: {sensor['name']}")

    def on_message(self, client, userdata, msg):
        """Obsługa wiadomości MQTT z impulsami (Finalna wersja)"""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            dev_list = payload.get("dev_list", [])
            if not dev_list:
                return

            device = dev_list[0]
            ts = device.get("ts")

            now = time.time()
            self.last_timestamp = ts
            self.last_message_time = now

            # --- Licz impuls i zapisz czas ---
            self.total_impulses += 1
            self.last_impulse_times.append(now) 

            # --- Obliczanie Mocy Chwilowej wg różnicy czasu (t) ---
            power_kw = 0.0
            
            if len(self.last_impulse_times) == 2:
                time_diff_t = self.last_impulse_times[1] - self.last_impulse_times[0]
                
                if time_diff_t > 0:
                    power_kw = 3600 / (self.impulses_per_kwh * time_diff_t)
                    self.last_valid_power = power_kw # Zapisujemy nową, ważną moc
                else: 
                    power_kw = self.max_power_kw
                    self.last_valid_power = power_kw
            
            # --- Ograniczenie Mocy ---
            if self.max_power_kw and power_kw > self.max_power_kw:
                power_kw = self.max_power_kw
                self.last_valid_power = power_kw
                
            # --- Publikacja co power_update_interval ---
            if now - self.last_power_publish >= self.power_update_interval:
                
                power_to_publish = 0.0
                
                # Jeśli ostatni impuls był dawno temu (wg timeoutu), moc jest 0.0
                if self.last_impulse_times and (now - self.last_impulse_times[-1] > self.power_timeout_seconds):
                    power_to_publish = 0.0
                    self.power_history.clear() # Opcjonalnie: czyścimy bufor, gdy moc spada do zera
                else:
                    # Jeśli impulsy są aktywne (lub właśnie się pojawiły), 
                    # do bufora dodajemy ostatnią obliczoną moc i ją uśredniamy.
                    self.power_history.append(self.last_valid_power)
                    power_to_publish = sum(self.power_history) / len(self.power_history)
                
                # --- Właściwa Publikacja MQTT ---
                self.last_power_publish = now
                kwh = self.total_impulses / self.impulses_per_kwh
                timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                mqtt_payload = {
                    "timestamp": timestamp_str,
                    "impulses": self.total_impulses,
                    "kwh": round(kwh, 3),
                    "power_kw": round(power_to_publish, 3) 
                }
                client.publish(f"onemeter/energy/{self.device_id}/state", json.dumps(mqtt_payload), qos=1, retain=True)
                _LOGGER.info(f"📈 Energy update: {mqtt_payload}")

        except Exception as e:
            _LOGGER.error(f"❌ Błąd przetwarzania wiadomości: {e}")