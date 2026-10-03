# RFID Attendance (ESP32 + Flask + SQLite)

This local project receives a card UID from the ESP32, stores attendance by class session, and shows totals in a browser dashboard. You can record more than one class on the same date.

## Files

- `app.py`: Flask web server and SQLite database logic.
- `templates/index.html`: dashboard.
- `esp32_attendance.ino`: Arduino sketch for the ESP32 + RC522.
- `attendance.db`: created automatically when the server first runs. Keep it to preserve attendance.

## 1. Start the computer server

Install Python 3 if needed. In a terminal opened in this project folder, run:

```text
py -m pip install -r requirements.txt
py app.py
```

If `py` is unavailable, use `python` in both commands. Keep this terminal window running. On the same computer, open `http://127.0.0.1:5000` in a browser.

Click **Start another class** before scanning each class session. The date is taken from the computer's local clock. If a registered card is scanned before you start the first class of the day, the server opens Class 1 automatically. For later classes, click the button first so scans are recorded in the new class.

## 2. Find the computer's Wi-Fi address

On Windows, open Command Prompt and run `ipconfig`. Under the Wi-Fi adapter, find **IPv4 Address**, for example `192.168.1.10`. The computer and ESP32 must be connected to the same Wi-Fi network. Do not use `127.0.0.1` in the ESP32 sketch; that address means the ESP32 itself.

## 3. Set up the ESP32 sketch

Open `esp32_attendance.ino` in Arduino IDE. Install the **MFRC522** library if it is not already installed, then select your ESP32 board and port. Replace `YOUR_WIFI_NAME`, `YOUR_WIFI_PASSWORD`, and `192.168.1.10` with your Wi-Fi details and computer IPv4 address. Preserve `/api/scan` at the end of the URL. Upload the sketch and open Serial Monitor at **115200 baud**.

This sketch keeps the RC522 pins from the working version: SS/SDA is GPIO 5 and RST is GPIO 22. It sends every scanned UID to the server, which accepts only the four registered UIDs.

## 4. Attendance rules

- Each press of **Start another class** creates a new class session, numbered for that date.
- The first scan for a student in a class marks them present. Further scans in that same class do not increase totals. In a later class, the student can be marked present again.
- Students not scanned remain absent for that class; attended class sessions divided by total class sessions gives the percentage.
- `attendance.db` is created beside `app.py`. Back up this file to preserve records. Deleting it resets the database.

## Troubleshooting

- If the ESP32 cannot reach the server, confirm both devices are on the same Wi-Fi, the server is still running, and the URL has the computer's current IPv4 address.
- Allow Python through the Windows firewall for private networks if Windows asks. If the firewall blocks the connection, allow inbound connections to port 5000 on your trusted private network.
- If today's values do not appear after a scan, refresh the browser dashboard.
- The example is intended for a trusted local network. It does not use login or encrypted HTTPS; do not expose port 5000 to the public internet.
