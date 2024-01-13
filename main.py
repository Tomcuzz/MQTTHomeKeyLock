import os
import json
import logging
import signal
import sys

from pyhap.accessory_driver import AccessoryDriver

from accessory import Lock
from util.bfclf import BroadcastFrameContactlessFrontend
from repository import Repository
from service import Service

def load_configuration() -> dict:
    return {
        "logging": {
            "level":  int(os.getenv("LOG_LEVEL", 20)),
        },
        "nfc": {
            "port":  str(os.getenv("NFC_PORT", "USB0")),
            "driver": str(os.getenv("NFC_DRIVER", "pn532")),
            "broadcast": (True if os.getenv("NFC_BROADCAST", "True") == "True" else False)
        },
        "hap": {
            "port": int(os.getenv("HAP_PORT", 51926)),
            "persist": str(os.getenv("HAP_PERSIST", "hap.state"))
        },
        "homekey": {
            "persist": str(os.getenv("HOMEKEY_PERSIST", "homekey.json")),
            "express": (True if os.getenv("HOMEKEY_EXPRESS", "True") == "True" else False),
            "finish": str(os.getenv("HOMEKEY_FINISH", "black")),
            "flow": str(os.getenv("HOMEKEY_FLOW", "fast")),
        }
    }


def configure_logging(config: dict):
    log = logging.getLogger()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)8s] %(module)-18s:%(lineno)-4d %(message)s"
    )
    hdlr = logging.StreamHandler(sys.stdout)
    log.setLevel(config.get("level", logging.INFO))
    hdlr.setFormatter(formatter)
    log.addHandler(hdlr)
    return log


def configure_hap_accessory(config: dict, homekey_service=None):
    driver = AccessoryDriver(port=config["port"], persist_file=config["persist"])
    accessory = Lock(driver, "NFC Lock", service=homekey_service)
    driver.add_accessory(accessory=accessory)
    return driver, accessory


def configure_nfc_device(config: dict):
    clf = BroadcastFrameContactlessFrontend(
        path=f"tty:{config['port']}:{config['driver']}",
        broadcast_enabled=config.get("broadcast", True),
    )
    return clf


def configure_homekey_service(config: dict, nfc_device, repository=None):
    service = Service(
        nfc_device,
        repository=repository or Repository(config["persist"]),
        express=config.get("express", True),
        finish=config.get("finish"),
        flow=config.get("flow"),
    )
    return service


def main():
    config = load_configuration()
    log = configure_logging(config["logging"])

    nfc_device = configure_nfc_device(config["nfc"])
    homekey_service = configure_homekey_service(config["homekey"], nfc_device)
    hap_driver, _ = configure_hap_accessory(config["hap"], homekey_service)

    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(
            s,
            lambda *_: (
                log.info(f"SIGNAL {s}"),
                homekey_service.stop(),
                hap_driver.stop(),
            ),
        )

    homekey_service.start()
    hap_driver.start()


if __name__ == "__main__":
    main()