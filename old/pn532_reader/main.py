"""
To Set up:
- pip install poetry && poetry install
To Run:
- poetry run python main.py
"""
import base64
import hashlib
import logging
import random
import string

import tlv8
import environs
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ec
from nfc.clf import RemoteTarget, TransmissionError, TimeoutError as ClfTimeoutError
from nfc.tag import tt4

from broadcast_frame_contactless_frontend import BroadcastFrameContactlessFrontend

env = environs.Env()
run = True


log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

apple_primary_key_applet_id = bytearray.fromhex("A0000008580101")
apple_key_configuration_applet_id = bytearray.fromhex("A0000008580102")

ecp_prefix = bytes.fromhex('6a02cb0206021100')
hap_nfc_ident_prefix = bytes.fromhex("6B65792D6964656E746966696572")

# Reader private key base64 encoded - get this from HAP pairing output
reader_private_key_b64 = env.str("READER_PRIVATE_KEY")
reader_private_key_bytes = base64.b64decode(reader_private_key_b64)

# iPhone HomeKey Public Key base64 encoded - get this from HAP Pairing output
# TODO: This might not be correct, the docs mention key exchange if FAST doesn't already have keys..
device_public_key_b64 = env.str("DEVICE_PUBLIC_KEY")
device_public_key_bytes = base64.b64decode(device_public_key_b64)

reader_id = hashlib.sha256("key-identifier".encode() + reader_private_key_bytes).digest()[:8]
broadcast = ecp_prefix + reader_id

print(f"Reader ID: {reader_id}")
print(f"Broadcast: {broadcast}")


def main(driver, interface, path):
    clf = BroadcastFrameContactlessFrontend(f"{interface}:{path}:{driver}")
    log.info(f"Initialized device")
    try:
        while True:
            target = clf.sense(
                RemoteTarget("106A"),
                RemoteTarget("106B"),
                broadcast=broadcast if len(broadcast) else None,
            )
            if not target:
                continue

            print(f"Got target {target}") 

            tag = tt4.activate(clf, target)
            res = tag.send_apdu(0, 0xA4, 0x04, 0x00, apple_primary_key_applet_id, 0)
            print("Applet Selected")
            res_supported_versions = tlv8.decode(res)[0].data.hex()
            supported_versions = []
            if "0200" in res_supported_versions:
                supported_versions.append(b'\x02\x00')
            if "0100" in res_supported_versions:
                supported_versions.append(b'\x01\x00')

            if not supported_versions:
                # Device didn't respond to applet selection with a version we can continue with
                continue

            ephemeral_private_key = ec.generate_private_key(ec.SECP256R1())
            ephemeral_public_key = ephemeral_private_key.public_key()
            ephemeral_raw_pub_key = ephemeral_public_key.public_bytes(
                encoding=serialization.Encoding.X962,
                format=serialization.PublicFormat.UncompressedPoint
            )

            nonce = ''.join(random.choice(string.ascii_lowercase) for _ in range(16))

            structure = [
                # TODO: Should be able to return 0x0200\0x0100 - https://github.com/kormax/apple-home-key#data-format
                tlv8.Entry(92, supported_versions[0], tlv8.DataType.BYTES),
                tlv8.Entry(135, ephemeral_raw_pub_key, tlv8.DataType.BYTES),
                tlv8.Entry(76, nonce, tlv8.DataType.STRING),
                tlv8.Entry(77, reader_id, tlv8.DataType.BYTES)
            ]
            bytes_data = tlv8.encode(structure)

            print(bytes_data.hex())
            res = tag.send_apdu(cla=0x80, ins=0x80, p1=0x01, p2=0x00, data=bytes_data)
            print("FAST sent")
            print(res.hex())

            decoded_fast_response = tlv8.decode(res)
            auth_cryptogram = next(filter(lambda k: k.type_id == 157, decoded_fast_response)).data
            device_ephemeral_public_key = next(filter(lambda k: k.type_id == 134, decoded_fast_response)).data

            # TODO: Verify FAST Response


            need_standard = True
            if need_standard:
                public_key = ec.EllipticCurvePrivateKey.from_encoded_point(ec.SECP256R1(), reader_private_key_bytes)
                lock_signature = public_key.sign(
                    bytes_data,
                    ec.ECDSA(hashes.SHA256())
                )

                structure = [
                    tlv8.Entry(40, lock_signature, tlv8.DataType.BYTES)
                ]
                bytes_data = tlv8.encode(structure)
                print(bytes_data.hex())
                res = tag.send_apdu(cla=0x80, ins=0x80, p1=0x00, p2=0x00, data=bytes_data)
                print("STANDARD sent")
                print(res.hex())


            # public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), device_public_key_bytes)  # From HAP
            # public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), device_ephemeral_public_key)
            # public_key.verify(signature=device_public_key_bytes, data=auth_cryptogram, signature_algorithm=ec.ECDSA(hashes.SHA1()))

            # TODO: Verify the response was generated by a publickey we know of
            # breakpoint()
            # data = tlv8.decode(res)
            # device_ephemeral_public_key = data[0].data
            # device_cryptogram = data[1].data
            # # Verify device_cryptogram is signed by device_ephemeral_public_key
            # public_key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), device_ephemeral_public_key)
            # public_key.verify(ephemeral_raw_pub_key, device_cryptogram, ec.ECDSA(hashes.SHA1()))

            # Send an okay response
            res = tag.send_apdu(cla=0x80, ins=0x3c, p1=0x01, p2=0x00)
            print(res.hex())

    except tt4.Type4TagCommandError as error:
        print("Error Received: ", error, "\n\n\n")
    except TransmissionError as Err:
        print("Got Error: ", Err, "\n\n\n")
    except (TimeoutError, ClfTimeoutError) as Err:
        print("Timout Error: ", Err, "\n\n\n")
    except OSError as Err:
        print("Timout Error: ", Err, "\n\n\n")
    except KeyboardInterrupt:
        global run
        run = False
    finally:
        clf.close()


if __name__ == "__main__":
    # Broadcast frames are only implemented for PN532. Feel free to add support for other devices.
    while run:
        # For macOS use a usb interface, find the path with `system_profiler SPUSBDataType`
        main(interface="tty", path="usbserial-110", driver="pn532")
