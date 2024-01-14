# Start from the latest python base image
FROM python:3.11

VOLUME /persist

WORKDIR /usr/app

COPY . .

# Define environment veriables
ENV TZ="Europe/London"

# Set Log Level (10->DEBUG, 20->INFO, 30->WARNING, 50->ERROR, 60->CRITICAL)
ENV LOG_LEVEL="20"

# Set Homekit default variables
ENV NFC_PORT="USB0"
ENV NFC_DRIVER="pn532"
ENV NFC_BROADCAST="True"
ENV HAP_PORT="51926"
ENV HAP_PERSIST="/persist/hap.state"
ENV HOMEKEY_PERSIST="/persist/homekey.json"
ENV HOMEKEY_EXPRESS="True"
ENV HOMEKEY_FINISH="black"
ENV HOMEKEY_FLOW="fast"

# Set MQTT default variables
ENV MQTT_SERVER="192.168.1.2"
ENV MQTT_PORT="1883"
ENV MQTT_CLIENT_ID="mqtt-homekey-lock"
ENV MQTT_AUTH="False"
ENV MQTT_USER=""
ENV MQTT_PASS=""
ENV MQTT_LOCK_ID="0"
ENV MQTT_PREFIX_TOPIC="mqtt-homekey-lock"
ENV MQTT_HASS_ENABLED="True"
ENV MQTT_STATUS_TOPIC="homeassistant/status"

#Update pip
RUN pip install --upgrade pip

#Install the Python dependancies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 51926

# Create health check to check / url
#HEALTHCHECK --interval=5m --timeout=3s --start-period=10s --retries=3 CMD curl -f http://localhost:8080/ || exit 1

CMD ["python3", "./main.py"]