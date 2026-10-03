#include <SPI.h>
#include <MFRC522.h>
#include <WiFi.h>
#include <HTTPClient.h>

#define SS_PIN 5
#define RST_PIN 22
MFRC522 rfid(SS_PIN, RST_PIN);

// Enter the Wi-Fi name/password and your computer's IPv4 address below.
const char* WIFI_NAME = "Airtel_Rajendra";
const char* WIFI_PASSWORD = "Raje@1234";
const char* SERVER_URL = "http://192.168.1.12:5000/api/scan";

String uidToString() {
  String uid = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    if (rfid.uid.uidByte[i] < 0x10) uid += "0";
    uid += String(rfid.uid.uidByte[i], HEX);
    if (i < rfid.uid.size - 1) uid += ":";
  }
  uid.toUpperCase();
  return uid;
}

void setup() {
  Serial.begin(115200);
  SPI.begin();
  rfid.PCD_Init();
  WiFi.begin(WIFI_NAME, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi connected. Scan a registered card.");
  Serial.print("ESP32 IP address: ");
  Serial.println(WiFi.localIP());
  Serial.print("Sending attendance to: ");
  Serial.println(SERVER_URL);
}

void loop() {
  if (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial()) return;

  String uid = uidToString();
  Serial.print("Scanned UID: ");
  Serial.println(uid);

  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient http;
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    String body = "{\"uid\":\"" + uid + "\"}";
    int status = http.POST(body);
    Serial.print("Server response code: ");
    Serial.println(status);
    if (status > 0) {
      Serial.println("Server reply:");
      Serial.println(http.getString());
      if (status == 404) Serial.println("Check that the scanned UID matches a registered UID in app.py.");
    } else {
      Serial.print("Could not contact the attendance server. HTTP error: ");
      Serial.println(http.errorToString(status));
      Serial.println("Check the computer IP, port 5000, Wi-Fi, and Windows firewall.");
    }
    http.end();
  } else {
    Serial.println("Wi-Fi disconnected; attendance was not sent.");
  }

  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
  delay(1500);
}
