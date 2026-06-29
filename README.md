# CAN Bus Signal Decoder — J1939 & EV Edition
 https://baba-26-can-decoder-dashboard-oj17s0.streamlit.app/ 
A Python tool for decoding J1939 CAN bus data using DBC files, with an interactive Streamlit web dashboard.  
Built to demonstrate hands-on understanding of automotive and EV communication protocols.

---

## What this does

Vehicles communicate internally over a **CAN bus** — a shared wire that all ECUs broadcast on.
Each message contains raw bytes that only make sense once you know the **DBC file** (the decoding dictionary)
and the **SPN** (Suspect Parameter Number) that describes each signal inside.

This tool:
- Loads any `.dbc` file and lists all signals (SPNs) with their units, ranges, and descriptions
- Searches for a signal by name across the entire DBC
- Decodes a raw CAN frame (hex bytes) into human-readable values using scale + offset
- Parses a CAN log file (`.csv`) and decodes every frame automatically
- Generates a diagnostic summary report with min/avg/max per signal
- Highlights EV-specific signals: SoC, cell voltages, HV pack voltage, isolation resistance
- **Interactive web dashboard** with real-time Plotly charts and gauges

---

## Technologies & concepts

| Concept | What it means |
|---|---|
| **CAN bus** | Two-wire vehicle network (CAN H / CAN L) that all ECUs share |
| **J1939** | The protocol standard used in trucks, buses, and EVs (rides on CAN) |
| **PGN** | Parameter Group Number — identifies which *type* of message is being sent |
| **SPN** | Suspect Parameter Number — one specific signal inside a PGN (e.g. SPN 190 = Engine Speed) |
| **DBC file** | Text database mapping raw CAN bytes → named, scaled, unit-bearing signals |
| **DTC** | Diagnostic Trouble Code — faults referenced by SPN + FMI (Failure Mode Identifier) |

---

## Signals included in sample DBC

| Signal | SPN | Message | Unit |
|---|---|---|---|
| Engine Speed | 190 | EEC1 | rpm |
| Accelerator Pedal Position | 91 | EEC2 | % |
| Engine Coolant Temp | 110 | ET1 | °C |
| Engine Oil Pressure | 100 | EFL_P1 | kPa |
| Battery Voltage (12V) | 168 | VEP1 | V |
| Wheel Speed | 84 | CCVS1 | km/h |
| HV Battery Voltage | 5827 | BMS1 | V |
| Battery State of Charge | 1637 | BMS1 | % |
| Battery State of Health | 5829 | BMS1 | % |
| Cell Voltage Max | 5831 | BMS2 | V |
| Cell Voltage Min | 5832 | BMS2 | V |
| Isolation Resistance | 5834 | BMS3 | kΩ |

---

## Project structure

```
can-decoder/
├── can_decoder.py          ← CLI tool (all core logic)
├── dashboard.py            ← Streamlit interactive web dashboard
├── data/
│   ├── j1939_sample.dbc    ← DBC file with real J1939 + EV signals
│   └── sample_log.csv      ← sample CAN log frames
├── reports/
│   ├── diagnostic_report.txt   ← auto-generated after decoding a log
│   └── decoded_signals.csv     ← all decoded values, exportable
├── requirements.txt
└── README.md
```

---

## Installation

```bash
git clone https://github.com/BaBa-26/can_decoder
cd can_decoder
pip install -r requirements.txt
```

---

## Usage

### Interactive web dashboard (recommended)

```bash
streamlit run dashboard.py
```

Opens a browser UI with five pages:

| Page | Description |
|---|---|
| **Overview** | DBC KPIs, message table, signal reading distribution chart, J1939 protocol reference |
| **Signal Browser** | Searchable table of all 31 SPNs; select any signal to see specs + time-series chart |
| **Frame Decoder** | Paste a CAN ID + data bytes (or pick a preset) → decoded table + animated gauges |
| **Time-Series** | Multi-signal line chart with normalize toggle, time-range slider, and sparklines |
| **EV Battery** | BMS snapshot metrics, animated gauges, cell-voltage spread, dual-axis SoC vs HV voltage |

You can also upload your own DBC or CSV log via the sidebar.

---

### CLI menu

```bash
python can_decoder.py
```

```
  [1] List all signals in the DBC (full SPN reference)
  [2] Search for a signal by name
  [3] Decode a raw CAN frame manually
  [4] Decode a CAN log file + generate report
  [5] Show EV battery signals only
```

#### Example: decode a raw frame

```
Enter CAN ID (hex): 0CEEFEFE
Enter data bytes (hex): 78320000640050FF

Decoded frame: 0CEEFEFEh  →  BMS1
Raw bytes: 78 32 00 00 64 00 50 FF
──────────────────────────────────────────
Signal                    Value    Unit
HV_Battery_Voltage        646.0    V
HV_Battery_Current       -1600.0   A
Battery_State_of_Charge    40.0    %
Battery_State_of_Health     0.0    %
Battery_Pack_Temp          40.0    degC
```

---

## Sample diagnostic report output

```
======================================================================
  CAN BUS DIAGNOSTIC REPORT
  Total frames decoded: 94  |  Unique signals: 14
======================================================================
  HV_Battery_Voltage        avg=646.00 V
  Battery_State_of_Charge   avg=40.51 %
  Battery_Pack_Temp         avg=41.43 degC
  Cell_Voltage_Max          avg=2.02 V
  Cell_Voltage_Min          avg=0.80 V
  Isolation_Resistance      avg=65535.00 kΩ
======================================================================
```

---

## What I learned building this

- How a DBC file maps raw CAN bytes to named, scaled signals
- J1939 message structure: 29-bit arbitration ID encodes PGN + source address
- Signal decoding formula: `physical_value = raw × scale + offset`
- EV-specific SPNs: SoC (1637), HV voltage (5827), isolation resistance (5834)
- How DTCs reference SPNs: `SPN + FMI = one fault code`
- Building interactive automotive dashboards with Streamlit + Plotly

---

## Requirements

```
cantools>=39.0.0
pandas>=2.0.0
tabulate>=0.9.0
streamlit>=1.35.0
plotly>=5.22.0
```

---

## Next steps

- [ ] Add DTC fault code lookup by SPN + FMI
- [ ] Connect to live CAN bus via `python-can` + USB adapter
- [ ] Add replay mode to animate signal values over time

---

*Built as part of self-directed study in automotive/EV communications (J1939, DBC, CAN bus)*
