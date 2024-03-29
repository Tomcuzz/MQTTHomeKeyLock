"""Module to handle mqtt."""
import json
import random
import string
import time
import logging
from dataclasses import dataclass

import paho.mqtt.client as mqtt_client

log = logging.getLogger()

@dataclass
class MqttConfig:
    """Class to hold mqtt configs."""
    mqtt_server: str
    mqtt_port: int
    mqtt_client_id: str
    mqtt_auth: bool
    mqtt_user: str
    mqtt_pass: str
    mqtt_ha_enable: bool
    lock_id: str
    mqtt_topic_prefix: str
    mqtt_ha_status_topic: str
    mqtt_oneline_topic: str
    mqtt_state_topic: str
    mqtt_command_topic: str
    mqtt_key_id_authed_topic: str

    @classmethod
    def from_dict(cls, config: dict):
        """Create configs from dict."""
        return MqttConfig(
            mqtt_server = config.get("server", ""),
            mqtt_port = config.get("port", 1883),
            mqtt_client_id = config.get("client_id", "mqtt-homekey-lock"),
            mqtt_auth = config.get("auth", False),
            mqtt_user = config.get("user", ""),
            mqtt_pass = config.get("pass", ""),
            mqtt_ha_enable = config.get("hass_enabled", True),
            lock_id = config.get("lock_id", "0"),
            mqtt_topic_prefix = config.get("prefix_topic", ""),
            mqtt_ha_status_topic = config.get(
                "hass_status_topic", "homeassistant/status"),
            mqtt_oneline_topic = config.get(
                "prefix_topic", "") + "/" + config.get("lock_id", "0") + "/online",
            mqtt_state_topic = config.get(
                "prefix_topic", "") + "/" + config.get("lock_id", "0") + "/mqtt_state_topic",
            mqtt_command_topic = config.get(
                "prefix_topic", "") + "/" + config.get("lock_id", "0") + "/command_topic",
            mqtt_key_id_authed_topic = config.get(
                "prefix_topic", "") + "/" + config.get("lock_id", "0") + "/key_id_authed"
        )

class Mqtt:
    """Class to handle mqtt."""
    def __init__(
        self,
        config_dict:dict
        ) -> None:
        self.config = MqttConfig.from_dict(config_dict)
        self.update_callback = self.default_update_callback
        self.connect_mqtt()

    def connect_mqtt(self):
        """Connect to mqtt."""
        log.info("Connecting to MQTT")
        def on_connect(client, _1, _2, rc):
            if rc == 0:
                log.info("Connected to MQTT Broker!")
                self.setup_subscriptions()
                self.publish_hass_config()
                client.publish(self.config.mqtt_oneline_topic, "online", 0, True)
            else:
                log.error("Failed to connect, return code %d\n", rc)
        def on_disconnect(_1, _2, _3):
            self.connect_mqtt()
            log.warning("Mqtt Disconnected")
        # Set Connecting Client ID
        rand_string = ''.join(random.choice(string.ascii_letters) for i in range(8))
        self.client = mqtt_client.Client(self.config.mqtt_client_id + "_" + rand_string)
        if self.config.mqtt_auth:
            self.client.username_pw_set(self.config.mqtt_user, self.config.mqtt_pass)
        self.client.on_connect = on_connect
        self.client.on_disconnect = on_disconnect
        self.client.will_set(self.config.mqtt_oneline_topic, "offline", 0, True)
        self.client.connect(self.config.mqtt_server, self.config.mqtt_port)
        self.client.loop_start()
        log.info("MQTT Connection setup")

    def setup_subscriptions(self):
        """Setup mqtt subscriptions."""
        def on_message(_1, _2, msg):
            log.debug("Message recieved on topic: " +
                      msg.topic + " With Message: " +
                      msg.payload.decode())
            if msg.topic == self.config.mqtt_command_topic:
                self.update_callback(True if msg.payload.decode() == "lock" else False)
            elif msg.topic == self.config.mqtt_ha_status_topic:
                self.publish_hass_config()

        self.client.subscribe(self.config.mqtt_command_topic)
        self.client.subscribe(self.config.mqtt_ha_status_topic)
        self.client.on_message = on_message
        log.info("Subscription setup")

    def publish_hass_config(self):
        """Publish hass config to mqtt."""
        time.sleep(10)
        hass_device_name = "mqtt-homekey-lock-" + self.config.lock_id
        hass_lock_name = "mqtt-homekey-lock-" + self.config.lock_id + "-lock"
        config = {
            "name": "lock",
            "unique_id": hass_lock_name,
            "device":{
                "identifiers": [
                    hass_device_name,
                ],
                "manufacturer": "tcousin",
                "model":"MQTT Homekey Lock V1",
                "name": hass_device_name
            },
            "payload_lock":"lock",
            "payload_unlock":"unlock",
            "state_locked":"locked",
            "state_unlocked":"unlocked",
            "state_locking":"unlocking",
            "state_unlocking":"unlocking",
            "state_topic": self.config.mqtt_state_topic,
            "command_topic": self.config.mqtt_command_topic,
            "availability": {
                "topic": self.config.mqtt_oneline_topic,
                "payload_available":"online",
                "payload_not_available":"offline"
            }
        }
        self.client.publish(
            "homeassistant/lock/" + hass_lock_name + "/config",
            json.dumps(config))


    # This should be overriden by the accessory file
    def default_update_callback(self, set_locked:bool):
        """Create a default callback to call when mqtt sets state."""

    def update_state(self, target_locked:bool, current_locked:bool):
        """Send status update to mqtt."""
        pub_state = "unkown"
        if not target_locked and not current_locked:
            pub_state = "unlocked"
        elif target_locked and current_locked:
            pub_state = "locked"
        elif not target_locked and current_locked:
            pub_state = "unlocking"
        elif target_locked and not current_locked:
            pub_state = "locking"
        self.client.publish(self.config.mqtt_state_topic, pub_state, 0, True)

    def device_passed_auth(self, key_id:str):
        """Send device authentication method to mqtt."""
        self.client.publish(self.config.mqtt_key_id_authed_topic, key_id)
    