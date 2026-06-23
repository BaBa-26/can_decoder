"""
CAN Bus Signal Decoder & DBC Viewer
=====================================
A Python tool for decoding J1939 CAN bus data using DBC files.
Demonstrates understanding of: DBC format, SPNs, PGNs, J1939 protocol,
signal scaling, and automotive data analysis.

Author: Aarrav Bala

Skills demonstrated: cantools, pandas, J1939, DBC parsing, CAN diagnostics
"""

import cantools
import pandas as pd
import struct
import os
import sys
from datetime import datetime
from tabulate import tabulate


# ─────────────────────────────────────────────
# CORE: Load a DBC file
# ─────────────────────────────────────────────

def load_dbc(dbc_path: str) -> cantools.database.Database:
    """
    Load a DBC file and return a cantools database object.
    A DBC file is the 'dictionary' that tells us what each
    CAN message ID means and how to decode the bytes inside it.
    """
    if not os.path.exists(dbc_path):
        print(f"[ERROR] DBC file not found: {dbc_path}")
        sys.exit(1)

    db = cantools.database.load_file(dbc_path)
    print(f"[OK] Loaded DBC: {dbc_path}")
    print(f"     {len(db.messages)} messages | "
          f"{sum(len(m.signals) for m in db.messages)} signals total\n")
    return db


# ─────────────────────────────────────────────
# FEATURE 1: Browse all signals (SPN reference)
# ─────────────────────────────────────────────

def list_all_signals(db: cantools.database.Database):
    """
    Print every signal in the DBC as a formatted table.
    Each signal = one SPN (Suspect Parameter Number) in J1939.
    Shows: message name, signal name, unit, value range, and description.
    """
    rows = []
    for msg in sorted(db.messages, key=lambda m: m.name):
        for sig in msg.signals:
            min_val = sig.minimum if sig.minimum is not None else "—"
            max_val = sig.maximum if sig.maximum is not None else "—"
            unit    = sig.unit if sig.unit else "—"
            comment = sig.comment[:55] + "…" if sig.comment and len(sig.comment) > 55 else (sig.comment or "—")
            rows.append([
                msg.name,
                sig.name,
                unit,
                f"{min_val} – {max_val}",
                comment
            ])

    print("=" * 90)
    print("  ALL SIGNALS IN DBC (each signal = one SPN/parameter)")
    print("=" * 90)
    print(tabulate(
        rows,
        headers=["Message (PGN)", "Signal (SPN)", "Unit", "Range", "Description"],
        tablefmt="rounded_outline"
    ))
    print(f"\n  Total: {len(rows)} signals across {len(db.messages)} messages\n")


# ─────────────────────────────────────────────
# FEATURE 2: Search for a signal by name
# ─────────────────────────────────────────────

def search_signal(db: cantools.database.Database, query: str):
    """
    Search for a signal (SPN) by name keyword.
    Useful for quickly finding what message carries a specific parameter.
    """
    query_lower = query.lower()
    found = []

    for msg in db.messages:
        for sig in msg.signals:
            if query_lower in sig.name.lower() or (sig.comment and query_lower in sig.comment.lower()):
                found.append({
                    "Message":     msg.name,
                    "Message ID":  hex(msg.frame_id),
                    "Signal":      sig.name,
                    "Start Bit":   sig.start,
                    "Length":      f"{sig.length} bits",
                    "Scale":       sig.scale,
                    "Offset":      sig.offset,
                    "Unit":        sig.unit or "—",
                    "Range":       f"{sig.minimum} – {sig.maximum}",
                    "Description": sig.comment or "—"
                })

    if not found:
        print(f"  [!] No signals found matching '{query}'\n")
        return

    print(f"\n  Found {len(found)} signal(s) matching '{query}':\n")
    for f in found:
        print(f"  ┌─ {f['Signal']} (in message: {f['Message']})")
        print(f"  │  CAN ID:      {f['Message ID']}")
        print(f"  │  Position:    start bit {f['Start Bit']}, {f['Length']}")
        print(f"  │  Decoding:    raw × {f['Scale']} + {f['Offset']} {f['Unit']}")
        print(f"  │  Valid range: {f['Range']} {f['Unit']}")
        print(f"  └─ {f['Description']}\n")


# ─────────────────────────────────────────────
# FEATURE 3: Decode a raw CAN frame manually
# ─────────────────────────────────────────────

def decode_frame(db: cantools.database.Database, can_id_hex: str, data_hex: str):
    """
    Decode a single raw CAN frame into human-readable signal values.

    This is the core of what diagnostic tools do:
    - Take a CAN ID (tells us which message/PGN it is)
    - Take raw data bytes
    - Use the DBC to find scale/offset and convert to real values
    """
    try:
        frame_id = int(can_id_hex, 16)
        data_bytes = bytes.fromhex(data_hex)
    except ValueError as e:
        print(f"  [ERROR] Bad input: {e}")
        return

    try:
        message = db.get_message_by_frame_id(frame_id)
    except KeyError:
        print(f"  [!] CAN ID {can_id_hex} not found in DBC. Unknown message.\n")
        return

    decoded = message.decode(data_bytes, decode_choices=False)

    print(f"\n  Decoded frame: {can_id_hex}h  →  {message.name}")
    print(f"  Raw bytes: {' '.join(f'{b:02X}' for b in data_bytes)}")
    print(f"  {'─'*50}")

    rows = []
    for sig_name, value in decoded.items():
        sig = message.get_signal_by_name(sig_name)
        unit = sig.unit if sig.unit else ""
        # Flag values that look like "not available" (0xFF patterns)
        status = "OK"
        if sig.maximum and isinstance(value, float) and value >= sig.maximum * 0.98:
            status = "N/A?"
        rows.append([sig_name, f"{value:.3f}", unit, status])

    print(tabulate(
        rows,
        headers=["Signal (SPN)", "Decoded Value", "Unit", "Status"],
        tablefmt="simple"
    ))
    print()


# ─────────────────────────────────────────────
# FEATURE 4: Parse and decode a CAN log file
# ─────────────────────────────────────────────

def decode_log(db: cantools.database.Database, log_path: str) -> pd.DataFrame:
    """
    Parse a CSV log of CAN frames and decode every frame using the DBC.
    Returns a DataFrame with one row per decoded signal value,
    which can then be analysed, plotted, or exported.

    This is exactly what automotive engineers do with CAN logs
    from test drives or diagnostic sessions.
    """
    if not os.path.exists(log_path):
        print(f"  [ERROR] Log file not found: {log_path}")
        return pd.DataFrame()

    raw_log = pd.read_csv(log_path)
    print(f"  Loaded log: {len(raw_log)} frames from {log_path}")

    records = []
    unknown_ids = set()

    for _, row in raw_log.iterrows():
        frame_id   = int(row["can_id_hex"], 16)
        data_bytes = bytes.fromhex(row["data_hex"])
        timestamp  = row["timestamp_s"]

        try:
            message = db.get_message_by_frame_id(frame_id)
            decoded = message.decode(data_bytes, decode_choices=False)
            for sig_name, value in decoded.items():
                sig = message.get_signal_by_name(sig_name)
                records.append({
                    "timestamp_s":   timestamp,
                    "message":       message.name,
                    "signal":        sig_name,
                    "value":         round(float(value), 4),
                    "unit":          sig.unit or "",
                    "can_id":        row["can_id_hex"],
                })
        except KeyError:
            unknown_ids.add(row["can_id_hex"])

    if unknown_ids:
        print(f"  [!] {len(unknown_ids)} unknown CAN IDs skipped: {', '.join(unknown_ids)}")

    df = pd.DataFrame(records)
    print(f"  Decoded {len(df)} signal readings across {df['signal'].nunique()} unique signals\n")
    return df


# ─────────────────────────────────────────────
# FEATURE 5: Generate a summary report
# ─────────────────────────────────────────────

def generate_report(df: pd.DataFrame, output_path: str):
    """
    Generate a diagnostic summary report from decoded CAN log data.
    Shows min/max/avg for each signal — like a basic health snapshot
    of the vehicle or EV system during the recorded session.
    """
    if df.empty:
        print("  [!] No data to report.")
        return

    summary = (
        df.groupby(["message", "signal", "unit"])["value"]
        .agg(["min", "mean", "max", "count"])
        .reset_index()
        .round(3)
    )
    summary.columns = ["Message", "Signal", "Unit", "Min", "Avg", "Max", "Samples"]

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "=" * 70,
        "  CAN BUS DIAGNOSTIC REPORT",
        f"  Generated: {now}",
        f"  Total frames decoded: {len(df)}",
        f"  Unique signals: {df['signal'].nunique()}",
        f"  Time range: {df['timestamp_s'].min():.3f}s – {df['timestamp_s'].max():.3f}s",
        "=" * 70,
        "",
        tabulate(summary, headers="keys", tablefmt="rounded_outline", showindex=False),
        "",
        "=" * 70,
        "  EV-SPECIFIC SIGNALS SUMMARY",
        "=" * 70,
    ]

    ev_signals = ["HV_Battery_Voltage", "Battery_State_of_Charge",
                  "Battery_State_of_Health", "Battery_Pack_Temp",
                  "Cell_Voltage_Max", "Cell_Voltage_Min", "Isolation_Resistance"]

    ev_df = df[df["signal"].isin(ev_signals)]
    if not ev_df.empty:
        for sig in ev_signals:
            s = ev_df[ev_df["signal"] == sig]
            if not s.empty:
                unit = s["unit"].iloc[0]
                lines.append(
                    f"  {sig:<30}  avg={s['value'].mean():.2f} {unit}  "
                    f"min={s['value'].min():.2f}  max={s['value'].max():.2f}"
                )
    else:
        lines.append("  No EV-specific signals found in this log.")

    report_text = "\n".join(lines)

    with open(output_path, "w") as f:
        f.write(report_text)

    print(report_text)
    print(f"\n  [OK] Report saved to: {output_path}\n")


# ─────────────────────────────────────────────
# MAIN — interactive menu
# ─────────────────────────────────────────────

def main():
    DBC_PATH = "data/j1939_sample.dbc"
    LOG_PATH = "data/sample_log.csv"
    REPORT_PATH = "reports/diagnostic_report.txt"

    os.makedirs("reports", exist_ok=True)

    print("\n" + "=" * 60)
    print("  CAN BUS SIGNAL DECODER  |  J1939 / EV Edition")
    print("  github.com/[yourname]/can-decoder")
    print("=" * 60 + "\n")

    db = load_dbc(DBC_PATH)

    while True:
        print("  What do you want to do?")
        print("  [1] List all signals in the DBC (full SPN reference)")
        print("  [2] Search for a signal by name")
        print("  [3] Decode a raw CAN frame manually")
        print("  [4] Decode a CAN log file + generate report")
        print("  [5] Show EV battery signals only")
        print("  [0] Exit")
        print()

        choice = input("  Enter choice: ").strip()

        if choice == "1":
            list_all_signals(db)

        elif choice == "2":
            query = input("  Enter signal name to search: ").strip()
            search_signal(db, query)

        elif choice == "3":
            print("  Example — EEC1 engine message:")
            print("    CAN ID: 8CF00400")
            print("    Data:   F000C801000000FF")
            print()
            can_id = input("  Enter CAN ID (hex): ").strip() or "8CF00400"
            data   = input("  Enter data bytes (hex, 16 chars): ").strip() or "F000C801000000FF"
            decode_frame(db, can_id, data)

        elif choice == "4":
            df = decode_log(db, LOG_PATH)
            if not df.empty:
                generate_report(df, REPORT_PATH)
                export = input("  Export decoded data to CSV? [y/n]: ").strip().lower()
                if export == "y":
                    csv_path = "reports/decoded_signals.csv"
                    df.to_csv(csv_path, index=False)
                    print(f"  [OK] Exported to {csv_path}\n")

        elif choice == "5":
            ev_signals = [
                "HV_Battery_Voltage", "HV_Battery_Current",
                "Battery_State_of_Charge", "Battery_State_of_Health",
                "Battery_Pack_Temp", "Cell_Voltage_Max",
                "Cell_Voltage_Min", "Cell_Voltage_Avg",
                "Charge_Power_Limit", "Isolation_Resistance"
            ]
            print("\n  EV / BMS SIGNAL DEFINITIONS\n")
            for sig_name in ev_signals:
                search_signal(db, sig_name)

        elif choice == "0":
            print("  Bye!\n")
            break
        else:
            print("  [!] Invalid choice. Try again.\n")


if __name__ == "__main__":
    main()
