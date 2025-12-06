#!/usr/bin/env python3
import struct
import json
import csv

# ---------- USER SETTINGS ----------
INPUT_FILE = "usb_log.bin"
CSV_OUTPUT = "usb_output.csv"
JSON_OUTPUT = "usb_output.json"

# Standard struct size (largest of all three)
STANDARD_SIZE = 16  # bytes (4+4+4+4 for optical sensor)

# Opcodes (match your USBOpcode enum)
OP_OPTICAL = 0
OP_FORCE = 1
OP_BPM = 2

# struct formats (little-endian STM32)
FMT_OPTICAL = "<IfIf"   # timestamp, angular_velocity, raw_value, angular_accel
FMT_FORCE   = "<IfI"    # timestamp, force, raw_value
FMT_BPM     = "<IfI"    # timestamp, duty_cycle, raw_value
# -----------------------------------


def parse_record(opcode, payload):
    """Parse a single record based on opcode and struct format."""

    if opcode == OP_OPTICAL:
        timestamp, ang_vel, raw_val, ang_acc = struct.unpack(FMT_OPTICAL, payload[:struct.calcsize(FMT_OPTICAL)])
        return {
            "type": "optical_encoder",
            "timestamp": timestamp,
            "angular_velocity": ang_vel,
            "raw_value": raw_val,
            "angular_acceleration": ang_acc
        }

    elif opcode == OP_FORCE:
        timestamp, force, raw_val = struct.unpack(FMT_FORCE, payload[:struct.calcsize(FMT_FORCE)])
        return {
            "type": "forcesensor",
            "timestamp": timestamp,
            "force": force,
            "raw_value": raw_val
        }

    elif opcode == OP_BPM:
        timestamp, duty, raw_val = struct.unpack(FMT_BPM, payload[:struct.calcsize(FMT_BPM)])
        return {
            "type": "bpm",
            "timestamp": timestamp,
            "duty_cycle": duty,
            "raw_value": raw_val
        }

    return None



def parse_file():
    records = []

    with open(INPUT_FILE, "rb") as f:
        data = f.read()

    i = 0
    while i < len(data):

        if i + 1 > len(data):
            break

        opcode = data[i]
        i += 1

        if i + STANDARD_SIZE > len(data):
            break

        payload = data[i : i + STANDARD_SIZE]
        i += STANDARD_SIZE

        record = parse_record(opcode, payload)
        if record:
            records.append(record)

    return records



def write_csv(records):
    if not records:
        print("No records parsed.")
        return

    # Collect all possible keys
    keys = sorted({k for r in records for k in r.keys()})

    with open(CSV_OUTPUT, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=keys)
        writer.writeheader()
        for r in records:
            writer.writerow(r)



def write_json(records):
    with open(JSON_OUTPUT, "w") as f:
        json.dump(records, f, indent=4)



if __name__ == "__main__":
    records = parse_file()
    print(f"Parsed {len(records)} records.")

    write_csv(records)
    write_json(records)

    print(f"Output written to:\n  - {CSV_OUTPUT}\n  - {JSON_OUTPUT}")
