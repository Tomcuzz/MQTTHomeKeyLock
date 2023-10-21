// Run me with `node lock.js` or `npm start`

// TODO: This is nice in that it's both a NFC and Access code lock but for some reason the access code
//  storage service doesn't seem to work and you hit a bug on adding an access code when setting up the device
//  for the first time and then adding future access codes. But it doesn't hamper the NFC functionality.
const hap = require("hap-nodejs");

const Accessory = hap.Accessory;
const Characteristic = hap.Characteristic;
const CharacteristicEventTypes = hap.CharacteristicEventTypes;
const Service = hap.Service;

const tlvDecode = hap.decodeWithLists;
const tlvEncode = hap.encode;

// optionally set a different storage location with code below
// hap.HAPStorage.setCustomStoragePath("...");

const accessoryUuid = hap.uuid.generate("hap.examples.lock-nfc");
const accessory = new Accessory("NFC Lock", accessoryUuid);

let accessCodeStorage = {};
let configStateNum = 0;

accessory
  .getService(Service.AccessoryInformation)
  // Key colour: https://github.com/kormax/apple-home-key#key-color prepend 0104 to hex value, append 00 and base64
  // Black: "AQQAAAAA"
  // Gold: "AQSq1uwA"
  // Silver: "AQTj4+MA"
  // Tan: "AQTO1doA"
  .setCharacteristic(Characteristic.HardwareFinish, "AQQAAAAA")
  .setCharacteristic(Characteristic.Manufacturer, "Tinkerer")
  .setCharacteristic(Characteristic.Model, "NFC Lock Alpha")
  .setCharacteristic(Characteristic.SerialNumber, "NFC-LOCK-0001")
  .setCharacteristic(Characteristic.FirmwareRevision, "1.0.0");

const lockManagementService = new Service.LockManagement("Lock Management");
const lockMechanismService = new Service.LockMechanism("NFC Lock");
const nfcAccessService = new Service.NFCAccess("NFC Access");
const accessCodeService = new Service.AccessCode("Access Code");

// TODO: Don't really know what the characteristic should be yet for accessCode
accessCodeService.setCharacteristic(Characteristic.AccessCodeSupportedConfiguration, "AQQAAAAA");
nfcAccessService.setCharacteristic(Characteristic.NFCAccessSupportedConfiguration, "AQEQAgEQ");

const configState = nfcAccessService.getCharacteristic(Characteristic.ConfigurationState);
const controlPoint = nfcAccessService.getCharacteristic(Characteristic.NFCAccessControlPoint);

configState.on(CharacteristicEventTypes.GET, callback => {
  console.log("Queried config state");
  callback(undefined, configStateNum);
});

controlPoint.on(CharacteristicEventTypes.SET, (value, callback) => {
  let decodedData = tlvDecode(Buffer.from(value, "base64"));

  if (decodedData[1][0] == 1) {
    console.log("Control Point Write - List");

    var response = Buffer.alloc(0);

    for (const [key, value] of Object.entries(accessCodeStorage)) {
      console.log(key, value);
      response = Buffer.concat([response, tlvEncode(0x01, parseInt(key), 0x04, 0x00)]);
    }

    callback(undefined, tlvEncode(0x01, 0x01, 0x03, response).toString("base64"));
  } else if (decodedData[1][0] == 2) {
    console.log("Control Point Write - Read " + value);

    // Spew out private keys and client public keys in b64 to be used by pn532 module
    // TODO: Could these update?
    if (decodedData[6][2] !== undefined) {
      console.log("Reader private key base64: " + tlvDecode(decodedData[6])[2].toString("base64"));
      for (let key in accessory._accessoryInfo.pairedClients) {
        let client = accessory._accessoryInfo.pairedClients[key];
        console.log(
          "Client with username: " + client.username + "publickey b64: " + client.publicKey.toString("base64"),
        );
      }
    }

    var response = Buffer.alloc(0);

    if (decodedData[2] !== undefined) {
      let req = tlvDecode(decodedData[2]);
      let acID = req[1][0];
      let code = accessCodeStorage[acID.toString()];
      response = Buffer.concat([response, tlvEncode(0x01, acID, 0x02, code, 0x03, 0x00, 0x04, 0x00)]);
    }

    callback(undefined, tlvEncode(0x01, 0x02, 0x03, response).toString("base64"));
  } else if (decodedData[1][0] == 3) {
    console.log("Control Point Write - Add");
    let request = tlvDecode(decodedData[2]);

    var response = Buffer.alloc(0);

    if (request[2] !== undefined) {
      let acID = Math.floor(Math.random() * 128);
      let code = request[2].toString("utf8");
      accessCodeStorage[acID.toString()] = code;
      console.log("Control Point Write - Add " + acID + " with code: " + code);
      response = Buffer.concat([response, tlvEncode(0x01, acID, 0x02, code, 0x03, 0x00, 0x04, 0x00)]);
    }

    callback(undefined, tlvEncode(0x01, 0x03, 0x03, response).toString("base64"));

    configStateNum += 1;
    configState.sendEventNotification(configStateNum);
  } else if (decodedData[1][0] == 4) {
    console.log("Control Point Write - Update");
    let request = tlvDecode(decodedData[2]);

    var response = Buffer.alloc(0);

    if (request[2] !== undefined) {
      let acID = request[1][0];
      console.log("Control Point Write - Update " + acID);

      if (accessCodeStorage[acID.toString()] !== undefined) {
        let code = request[2].toString("utf8");
        accessCodeStorage[acID.toString()] = code;
        response = Buffer.concat([response, tlvEncode(0x01, acID, 0x02, code, 0x03, 0x00, 0x04, 0x00)]);
      } else {
        response = Buffer.concat([response, tlvEncode(0x01, acID, 0x04, 0x09)]);
      }
    }

    callback(undefined, tlvEncode(0x01, 0x04, 0x03, response).toString("base64"));

    configStateNum += 1;
    configState.sendEventNotification(configStateNum);
  } else if (decodedData[1][0] == 5) {
    console.log("Control Point Write - Remove");
    let request = tlvDecode(decodedData[2]);

    var response = Buffer.alloc(0);

    if (request[2] !== undefined) {
      let acID = request[1][0];
      console.log("Control Point Write - delete " + acID);

      if (accessCodeStorage[acID.toString()] !== undefined) {
        let code = accessCodeStorage[acID.toString()];
        delete accessCodeStorage[acID.toString()];
        response = Buffer.concat([response, tlvEncode(0x01, acID, 0x02, code, 0x03, 0x00, 0x04, 0x00)]);
      } else {
        response = Buffer.concat([response, tlvEncode(0x01, acID, 0x04, 0x09)]);
      }
    }

    callback(undefined, tlvEncode(0x01, 0x05, 0x03, response).toString("base64"));

    configStateNum += 1;
    configState.sendEventNotification(configStateNum);
  } else {
    console.log("Unknown Control Point Write: " + value);
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
accessory.addService(accessCodeService);

// once everything is set up, we publish the accessory. Publish should always be the last step!
accessory.publish({
  username: "17:51:07:F4:BC:4B",
  pincode: "111-11-111",
  port: 47169,
  category: hap.Categories.DOOR_LOCK, // value here defines the symbol shown in the pairing screen
});

console.log("Accessory setup finished!");
