import os
import time
import string
import random

import tlv8
import base64
import hashlib

from nfc.clf import RemoteTarget
from broadcast_frame_contactless_frontend import BroadcastFrameContactlessFrontend
from nfc.clf import ContactlessFrontend, ProtocolError, CommunicationError, RemoteTarget, UnsupportedTargetError, TransmissionError
from nfc.tag import tt4

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

import logging
run = True

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

apple_primary_key_applet_id = bytearray.fromhex("A0000008580101")
apple_key_configuration_applet_id = bytearray.fromhex("A0000008580102")

ecp_prefix = bytes.fromhex('6a02cb0206021100')
hap_nfc_ident_prefix = bytes.fromhex("6B65792D6964656E746966696572")

reader_private_key = base64.b64decode(os.environ.get("READER_PRIVATE_KEY"))
aid = ""
device_cred_public_key = ""

def reader_group_gen():
    return hashlib.sha256("key-identifier".encode() + base64.b64decode(reader_private_key)).digest()[:8]


def generate_broadcast():
    return ecp_prefix + reader_group_gen()

reader_id = reader_group_gen()
broadcast = generate_broadcast()


print(reader_id)

def main(driver, interface, path):
    print(broadcast)
    clf = BroadcastFrameContactlessFrontend(f"{interface}:{path}:{driver}")
    log.info(f"Initialized device")
    try:
        while True:
            target = clf.sense(
                RemoteTarget("106A"), 
                RemoteTarget("106B"), 
                broadcast=broadcast if len(broadcast) else None
            )
            if not target:
                continue

            print(f"Got target {target}") 

            if target:
                tag = tt4.activate(clf, target)
                res = tag.send_apdu(0, 0xA4, 0x04, 0x00, apple_primary_key_applet_id, 0)
                print("Applet Selected")
                supported_versions = []
                if "0200" in res.hex()[4:]:
                    supported_versions.append(0x0200)
                if "0100" in res.hex()[4:]:
                    supported_versions.append(0x0100)
               
                if len(supported_versions) < 1:
                    continue

                private_key = ec.generate_private_key(ec.SECP256R1())
                public_key = private_key.public_key()
                raw_pub_key = public_key.public_bytes(
                    encoding=serialization.Encoding.X962,
                    format=serialization.PublicFormat.UncompressedPoint
                )

                letters = string.ascii_lowercase
                nonce = ''.join(random.choice(letters) for i in range(16))

                structure = [
                    tlv8.Entry(92, supported_versions[0], tlv8.DataType.INTEGER),
                    tlv8.Entry(135, raw_pub_key, tlv8.DataType.BYTES),
                    tlv8.Entry(76, nonce, tlv8.DataType.STRING),
                    tlv8.Entry(77, reader_id+base64.b64decode(aid), tlv8.DataType.BYTES)
                ]
                bytes_data = tlv8.encode(structure)
                data = bytearray.fromhex(bytes_data.hex())
                lenVal = len(data) #.to_bytes(1, 'big').hex()
                print(bytes_data.hex())
                res = tag.send_apdu(0x80, 0x80, 0x01, 0x00, bytes_data)
                print("FAST sent")
                print(res.hex())

    except tt4.Type4TagCommandError as error:
        raise error
        print("Error Recieved: ", error)
    except TransmissionError as Err:
        print("Got Error: ", Err)
    except TimeoutError as Err:
        print("Timout Error: ", Err)
    except OSError as Err:
        print("Timout Error: ", Err)
    except KeyboardInterrupt:
        run = False
    finally:
        clf.close()


if __name__ == "__main__":
    # Broadcast frames are only implemented for PN532. Feel free to add support for other devices.
    driver = "pn532"
    path = "USB0"
    interface = "tty"
    while run:
        main(driver, interface, path)