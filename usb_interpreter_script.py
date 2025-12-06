import serial
import serial.tools.list_ports
import struct
import queue
import threading
import time
import csv
import json
import os
import signal
import sys

# ==========================================================
# CONFIG
# ==========================================================

BAUD = 115200
TIMEOUT = 0.05

# Auto-detect COM port
def detect_port():
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if "USB" in p.description or "Serial" in p.description or "ACM" in p.device:
            print(f"[✓] Detected device on {p.device}")
            return p.device
    raise RuntimeError("No USB serial device detected.")

COM = detect_port()

# Folder for output
folder_path = os.path.join(os.getcwd(), "Data")
os.makedirs(folder_path, exist_ok=True)

# Find next available CSV file
i = 1
while True:
    CSV_FILE = os.path.join(folder_path, f"usb_data{i}.csv")
    if not os.path.exists(CSV_FILE):
        break
    i += 1

# JSON file
JSON_FILE = CSV_FILE.replace(".csv", ".json")

# ==========================================================
# USB Protocol Definitions
# ==========================================================

# OPCODES (must match your C enum)
OP_OPTICAL = 0
OP_FORCESENSOR = 1
OP_BPM = 2

# Largest struct = 16 bytes
STANDARD_SIZE = 16   # Determined by your C++ USBController::Init()

# Struct formats (little endian)
fmt_optical = "<I f I f"      # timestamp, ang_vel, raw, ang_acc
fmt_force   = "<I f I"        # timestamp, force, raw
fmt_bpm     = "<I f I"        # timestamp, duty, raw

# Parsed data stored for JSON export
all_data = []

# Queue for CSV writer thread
data_queue = queue.Queue()

# Thread stop flag
running = True

# ==========================================================
# PARSER
# ==========================================================

def parse_packet(opcode, payload):
    """
    Parse the padded struct data based on opcode.
    Payload is STANDARD_SIZE bytes.
    """

    if opcode == OP_OPTICAL:
        ts, ang_vel, raw, ang_acc = struct.unpack(fmt_optical, payload[:struct.calcsize(fmt_optical)])
        return {
            "type": "optical_encoder",
            "timestamp": ts,
            "angular_velocity": ang_vel,
            "raw_value": raw,
            "angular_acceleration": ang_acc,
        }

    elif opcode == OP_FORCESENSOR:
        ts, force, raw = struct.unpack(fmt_force, payload[:struct.calcsize(fmt_force)])
        return {
            "type": "forcesensor",
            "timestamp": ts,
            "force": force,
            "raw_value": raw,
        }

    elif opcode == OP_BPM:
        ts, duty, raw = struct.unpack(fmt_bpm, payload[:struct.calcsize(fmt_bpm)])
        return {
            "type": "bpm",
            "timestamp": ts,
            "duty_cycle": duty,
            "raw_value": raw,
        }

    else:
        return None

# ==========================================================
# THREAD 1 — SERIAL READER
# ==========================================================

def serial_reader(port):
    global running

    while running:
        try:
            # 1 byte opcode + STANDARD_SIZE bytes payload
            if port.in_waiting >= (1 + STANDARD_SIZE):
                header = port.read(1)
                payload = port.read(STANDARD_SIZE)

                opcode = header[0]

                parsed = parse_packet(opcode, payload)

                if parsed:
                    print(parsed)
                    all_data.append(parsed)
                    data_queue.put(parsed)

        except Exception as e:
            print(f"[ERROR] Serial read: {e}")
            time.sleep(0.1)

# ==========================================================
# THREAD 2 — CSV WRITER
# ==========================================================

def csv_writer():
    global running

    # Determine CSV headers
    headers = [
        "type",
        "timestamp",
        "angular_velocity",
        "angular_acceleration",
        "force",
        "duty_cycle",
        "raw_value",
    ]

    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

    while running:
        while not data_queue.empty():
            item = data_queue.get()

            # Ensure all keys exist (missing fields become None)
            row = {key: item.get(key) for key in headers}

            with open(CSV_FILE, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writerow(row)

        time.sleep(0.2)

# ==========================================================
# CLEAN EXIT (Ctrl+C)
# ==========================================================

def handle_exit(sig, frame):
    global running
    print("\nStopping...")
    running = False

signal.signal(signal.SIGINT, handle_exit)

# ==========================================================
# MAIN
# ==========================================================

def main():
    print(f"[✓] Opening {COM} at {BAUD} baud...")
    port = serial.Serial(COM, BAUD, timeout=TIMEOUT)

    t1 = threading.Thread(target=serial_reader, args=(port,), daemon=True)
    t2 = threading.Thread(target=csv_writer, daemon=True)

    t1.start()
    t2.start()

    print("[✓] Running... Press Ctrl+C to exit.\n")

    while running:
        time.sleep(0.5)

    # Save JSON
    print("[✓] Saving JSON...")
    with open(JSON_FILE, "w") as f:
        json.dump(all_data, f, indent=4)

    port.close()
    print("[✓] Done. Files saved:")
    print(f"    CSV  → {CSV_FILE}")
    print(f"    JSON → {JSON_FILE}")

if __name__ == "__main__":
    main()
