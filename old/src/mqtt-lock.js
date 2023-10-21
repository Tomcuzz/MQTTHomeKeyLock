var hap = require("hap-nodejs");
const crypto = require('crypto');

const Accessory = hap.Accessory;
const Characteristic = hap.Characteristic;
const CharacteristicEventTypes = hap.CharacteristicEventTypes;
const Service = hap.Service;

const tlvDecode = hap.decodeWithLists;
const tlvEncode = hap.encode;

// optionally set a different storage location with code below
// hap.HAPStorage.setCustomStoragePath("...");

var ReaderPrivateKey = "";
var ReaderIdent = "";
const HapNfcIdentPrefix = "6B65792D6964656E746966696572";
var DeviceKeys = {};

const accessoryUuid = hap.uuid.generate("hap.examples.lock-nfc");
const accessory = new Accessory("NFC Lock", accessoryUuid);

accessory
  .getService(Service.AccessoryInformation)
  .setCharacteristic(Characteristic.HardwareFinish, "AQT///8A");

const lockManagementService = new Service.LockManagement("Lock Management");
const lockMechanismService = new Service.LockMechanism("NFC Lock");
const nfcAccessService = new Service.NFCAccess("NFC Access");

nfcAccessService.setCharacteristic(Characteristic.NFCAccessSupportedConfiguration, "AQEQAgEQ");

const configState = nfcAccessService.getCharacteristic(Characteristic.ConfigurationState);
const controlPoint = nfcAccessService.getCharacteristic(Characteristic.NFCAccessControlPoint);

configState.on(CharacteristicEventTypes.GET, callback => {
    console.log("Queried config state: ");
    callback(undefined, 0);
});

controlPoint.on(CharacteristicEventTypes.SET, (value, callback) => {
  
  let decodedData = tlvDecode(Buffer.from(value, 'base64'));
  console.log("------------------------------------------------------------------------------")
  console.log("Control Point Write: " + value);
  //console.log(decodedData)

  if (decodedData[1] !== undefined) {
    // Opertation Decode
    if (decodedData[1][0] == 1) {
      console.log("Got Operation: get")
      if (ReaderIdent == "") {
        callback(undefined, "");
      } else {
        callback(undefined, tlvEncode(0x07, 0x0a, 0x01, 0x08, ReaderIdent.toString('utf8')).toString('base64'));
      }
    } else if (decodedData[1][0] == 2) {
      console.log("Got Operation: add")
      if (decodedData[6] !== undefined) {
        console.log("Got Reader Key Request")
        let rkr = tlvDecode(decodedData[6])
        
        // Key Type
        if (rkr[1] == 1) {
          console.log("Key type: curve25519")
        } else if (rkr[1] == 2) {
          console.log("Key type: secp256r1")
        }
  
        // Reader Private Key
        if (rkr[2] !== undefined) {
          ReaderPrivateKey = rkr[2].toString("base64")
          hash = crypto.createHash("sha256");
          hash.update(HapNfcIdentPrefix+ReaderPrivateKey);
          ReaderIdent = hash.digest("hex").substring(0,8)
          console.log("Reader Private Key", ReaderPrivateKey)
          console.log("Reader Ident", ReaderIdent)
        }
        // Return OK to Add
        callback(undefined, tlvEncode(0x07, 0x03, 0x02, 0x01, 0x00).toString('base64'));
      }

      if (decodedData[4] !== undefined) {
        console.log("Device Credential Request")
        let dcr = tlvDecode(decodedData[4])

        // Key Type
        if (dcr[1] == 1) {
          console.log("Key type: curve25519")
        } else if (dcr[1] == 2) {
          console.log("Key type: secp256r1")
        }

        // Device Key
        if (dcr[2] !== undefined && dcr[3] !== undefined) {
          deviceKey = dcr[2].toString("base64")
          deviceIdent = dcr[3].toString("base64")
          console.log("Device Key: ", deviceKey)
          console.log("Device Ident: ", deviceIdent)

          DeviceKeys[deviceIdent] = deviceKey

          callback(undefined, tlvEncode(0x05, 0x0d, 0x02, 0x08, deviceIdent.toString('utf8'), 0x03, 0x01, 0x00).toString('base64'));
        }

        // Key State
        if (dcr[4] == 0) {
          console.log("Key state: inactive")
        } else if (dcr[4] == 1) {
          console.log("Key state: active")
        }
      }
    } else if (decodedData[1][0] == 3) {
      console.log("Got Operation: remove")
    }
  } else {
    callback(undefined, "");
  }
});

let lockState = Characteristic.LockCurrentState.UNSECURED;

const currentStateCharacteristic = lockMechanismService.getCharacteristic(Characteristic.LockCurrentState);
const targetStateCharacteristic = lockMechanismService.getCharacteristic(Characteristic.LockTargetState);

currentStateCharacteristic.on(CharacteristicEventTypes.GET, callback => {
  console.log("Queried current lock state: " + lockState);
  callback(undefined, lockState);
});

targetStateCharacteristic.on(CharacteristicEventTypes.SET, (value, callback) => {
  console.log("Setting lock state to: " + value);
  lockState = value;
  callback();
  setTimeout(() => {
      currentStateCharacteristic.updateValue(lockState);
  }, 1000);
});

accessory.addService(lockManagementService);
accessory.addService(lockMechanismService);
accessory.addService(nfcAccessService);

// once everything is set up, we publish the accessory. Publish should always be the last step!
accessory.publish({
  username: "17:51:07:F4:BC:3C",
  pincode: "678-90-876",
  port: 47170,
  category: hap.Categories.DOOR_LOCK, // value here defines the symbol shown in the pairing screen
});

console.log("Accessory setup finished!");