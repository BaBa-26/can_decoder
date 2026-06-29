"""
CAN Bus Signal Decoder — Interactive Dashboard
===============================================
Streamlit + Plotly web UI for the CAN decoder.

Author: Aarrav Bala
"""

import os
import io
import cantools
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="CAN Bus Decoder",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 10px;
    }
    .metric-label {
        font-size: 0.78rem;
        color: #a6adc8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #cdd6f4;
    }
    .metric-unit {
        font-size: 0.9rem;
        color: #89b4fa;
        margin-left: 4px;
    }
    .status-ok   { color: #a6e3a1; }
    .status-warn { color: #f9e2af; }
    .status-err  { color: #f38ba8; }
    .section-header {
        font-size: 0.75rem;
        letter-spacing: 0.12em;
        color: #6c7086;
        text-transform: uppercase;
        margin-bottom: 8px;
        margin-top: 24px;
    }
    div[data-testid="stMetric"] {
        background: #1e1e2e;
        border: 1px solid #313244;
        border-radius: 10px;
        padding: 12px 16px;
    }
    .raw-byte {
        display: inline-block;
        background: #313244;
        color: #89dceb;
        font-family: monospace;
        padding: 2px 6px;
        border-radius: 4px;
        margin: 2px;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_resource
def load_dbc(path: str) -> cantools.database.Database:
    return cantools.database.load_file(path)


@st.cache_data
def decode_log(_db, log_path: str) -> pd.DataFrame:
    raw = pd.read_csv(log_path)
    records = []
    for _, row in raw.iterrows():
        frame_id = int(row["can_id_hex"], 16)
        data_bytes = bytes.fromhex(row["data_hex"])
        try:
            msg = _db.get_message_by_frame_id(frame_id)
            decoded = msg.decode(data_bytes, decode_choices=False)
            for sig_name, value in decoded.items():
                sig = msg.get_signal_by_name(sig_name)
                records.append({
                    "timestamp_s": float(row["timestamp_s"]),
                    "message": msg.name,
                    "signal": sig_name,
                    "value": round(float(value), 4),
                    "unit": sig.unit or "",
                    "can_id": row["can_id_hex"],
                })
        except KeyError:
            pass
    return pd.DataFrame(records)


def gauge_fig(value: float, min_v: float, max_v: float, label: str, unit: str,
              warn_pct: float = 0.8, color: str = "#89b4fa") -> go.Figure:
    pct = (value - min_v) / (max_v - min_v) if max_v != min_v else 0
    bar_color = "#a6e3a1" if pct < warn_pct else "#f9e2af" if pct < 0.95 else "#f38ba8"
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"suffix": f" {unit}", "font": {"size": 22, "color": "#cdd6f4"}},
        title={"text": label, "font": {"size": 13, "color": "#a6adc8"}},
        gauge={
            "axis": {"range": [min_v, max_v], "tickcolor": "#6c7086",
                     "tickfont": {"color": "#6c7086", "size": 10}},
            "bar": {"color": bar_color},
            "bgcolor": "#1e1e2e",
            "bordercolor": "#313244",
            "steps": [
                {"range": [min_v, min_v + (max_v - min_v) * 0.5], "color": "#181825"},
                {"range": [min_v + (max_v - min_v) * 0.5, max_v], "color": "#1e1e2e"},
            ],
        },
    ))
    fig.update_layout(
        height=220,
        margin=dict(t=50, b=20, l=30, r=30),
        paper_bgcolor="#181825",
        font_color="#cdd6f4",
    )
    return fig


def sparkline(df_sig: pd.DataFrame, color: str = "#89b4fa") -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=df_sig["timestamp_s"], y=df_sig["value"],
        mode="lines", line=dict(color=color, width=2),
        fill="tozeroy", fillcolor=color.replace(")", ",0.12)").replace("rgb", "rgba")
        if color.startswith("rgb") else color + "20",
    ))
    fig.update_layout(
        height=80, margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🚗 CAN Bus Decoder")
    st.caption("J1939 / EV Edition")
    st.divider()

    DBC_PATH = "data/j1939_sample.dbc"
    LOG_PATH = "data/sample_log.csv"

    uploaded_dbc = st.file_uploader("Upload DBC file", type=["dbc"])
    uploaded_log = st.file_uploader("Upload CAN log (CSV)", type=["csv"])

    if uploaded_dbc:
        tmp_dbc = "/tmp/uploaded.dbc"
        with open(tmp_dbc, "wb") as f:
            f.write(uploaded_dbc.read())
        DBC_PATH = tmp_dbc

    if uploaded_log:
        tmp_log = "/tmp/uploaded_log.csv"
        with open(tmp_log, "wb") as f:
            f.write(uploaded_log.read())
        LOG_PATH = tmp_log

    st.divider()
    page = st.radio(
        "Navigate",
        ["🏠  Overview", "📋  Signal Browser", "🔍  Frame Decoder", "📈  Time-Series", "⚡  EV Battery"],
    )
    st.divider()
    st.caption("Signals decoded in real time using cantools + plotly")


# ── Load data ─────────────────────────────────────────────────────────────────

try:
    db = load_dbc(DBC_PATH)
except Exception as e:
    st.error(f"Could not load DBC: {e}")
    st.stop()

all_signals_count = sum(len(m.signals) for m in db.messages)

try:
    df = decode_log(db, LOG_PATH)
except Exception:
    df = pd.DataFrame()


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Overview
# ═════════════════════════════════════════════════════════════════════════════

if page == "🏠  Overview":
    st.title("CAN Bus Signal Decoder")
    st.markdown("**J1939 / EV Edition** — Interactive diagnostic dashboard")
    st.divider()

    # Top KPIs
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Messages in DBC", len(db.messages))
    c2.metric("Signals (SPNs)", all_signals_count)
    if not df.empty:
        c3.metric("Decoded Readings", len(df))
        c4.metric("Time Span", f"{df['timestamp_s'].max():.2f} s")
    else:
        c3.metric("Decoded Readings", "—")
        c4.metric("Time Span", "—")

    st.divider()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Messages in DBC")
        msg_data = [
            {"Message": m.name, "Frame ID": hex(m.frame_id),
             "Signals": len(m.signals), "Length (B)": m.length}
            for m in sorted(db.messages, key=lambda x: x.name)
        ]
        st.dataframe(pd.DataFrame(msg_data), use_container_width=True, hide_index=True)

    with col_right:
        if not df.empty:
            st.subheader("Signal reading distribution")
            counts = df.groupby("signal")["value"].count().reset_index()
            counts.columns = ["Signal", "Readings"]
            fig = px.bar(counts.sort_values("Readings"), x="Readings", y="Signal",
                         orientation="h",
                         color="Readings", color_continuous_scale="Blues",
                         template="plotly_dark")
            fig.update_layout(
                paper_bgcolor="#181825", plot_bgcolor="#181825",
                margin=dict(t=10, b=10, l=0, r=0),
                showlegend=False, coloraxis_showscale=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No log loaded — upload a CSV or use the default.")

    # Protocol reference
    st.divider()
    st.subheader("J1939 Protocol Quick Reference")
    ref = {
        "CAN bus": "Two-wire differential network (CAN H / CAN L) shared by all ECUs",
        "J1939": "Protocol standard used in trucks, buses, and EVs — rides on CAN",
        "PGN": "Parameter Group Number — identifies the *type* of message",
        "SPN": "Suspect Parameter Number — one specific signal inside a PGN",
        "DBC file": "Text database: raw CAN bytes → named, scaled, unit-bearing signals",
        "Decoding formula": "physical = raw × scale + offset",
        "DTC": "Diagnostic Trouble Code — SPN + FMI identifies one fault",
    }
    for k, v in ref.items():
        st.markdown(f"**{k}** — {v}")


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Signal Browser
# ═════════════════════════════════════════════════════════════════════════════

elif page == "📋  Signal Browser":
    st.title("Signal Browser")
    st.caption("Every SPN in the loaded DBC file")
    st.divider()

    search = st.text_input("Search signals", placeholder="e.g. voltage, speed, temp…")

    rows = []
    for msg in sorted(db.messages, key=lambda m: m.name):
        for sig in msg.signals:
            rows.append({
                "Message (PGN)": msg.name,
                "Frame ID": hex(msg.frame_id),
                "Signal (SPN)": sig.name,
                "Unit": sig.unit or "—",
                "Min": sig.minimum,
                "Max": sig.maximum,
                "Scale": sig.scale,
                "Offset": sig.offset,
                "Start Bit": sig.start,
                "Length (bits)": sig.length,
                "Description": sig.comment or "—",
            })

    sig_df = pd.DataFrame(rows)

    if search:
        mask = (
            sig_df["Signal (SPN)"].str.contains(search, case=False, na=False) |
            sig_df["Message (PGN)"].str.contains(search, case=False, na=False) |
            sig_df["Description"].str.contains(search, case=False, na=False)
        )
        sig_df = sig_df[mask]
        st.caption(f"{len(sig_df)} result(s) for '{search}'")

    st.dataframe(sig_df, use_container_width=True, hide_index=True,
                 column_config={
                     "Description": st.column_config.TextColumn(width="large"),
                 })

    # Detail panel for selected signal
    st.divider()
    st.subheader("Signal detail")
    all_sig_names = [r["Signal (SPN)"] for r in rows]
    chosen = st.selectbox("Select a signal to inspect", all_sig_names)

    if chosen:
        row = next(r for r in rows if r["Signal (SPN)"] == chosen)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Unit", row["Unit"])
        c2.metric("Range", f"{row['Min']} – {row['Max']}")
        c3.metric("Bit position", f"start {row['Start Bit']}, {row['Length (bits)']} bits")
        c4.metric("Scale / Offset", f"×{row['Scale']} +{row['Offset']}")
        st.info(f"**Description:** {row['Description']}")
        st.caption(f"Message: **{row['Message (PGN)']}**  |  CAN ID: `{row['Frame ID']}`")

        if not df.empty and chosen in df["signal"].values:
            sig_ts = df[df["signal"] == chosen]
            fig = px.line(sig_ts, x="timestamp_s", y="value",
                          labels={"timestamp_s": "Time (s)", "value": f"{chosen} ({row['Unit']})"},
                          template="plotly_dark", title=f"{chosen} over time")
            fig.update_layout(paper_bgcolor="#181825", plot_bgcolor="#181825")
            st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Frame Decoder
# ═════════════════════════════════════════════════════════════════════════════

elif page == "🔍  Frame Decoder":
    st.title("Raw Frame Decoder")
    st.caption("Paste a CAN ID + data bytes and decode them instantly")
    st.divider()

    # Preset examples
    EXAMPLES = {
        "BMS1 — HV Battery": ("0CEEFEFE", "78320000640050FF"),
        "BMS2 — Cell Voltages": ("0CEEFFFE", "E0070007F0070050"),
        "BMS3 — Isolation": ("0CEF00FE", "00500050FFFFFFFF"),
        "EEC1 — Engine Speed": ("8CF00400", "F000C801000000FF"),
        "EEC2 — Accel Pedal": ("8CF00300", "00640000FFFFFFFF"),
        "ET1 — Coolant Temp": ("8FE6CEE", "FF78FFFFFFFFFFFF"),
    }

    col_preset, _ = st.columns([2, 3])
    with col_preset:
        preset = st.selectbox("Load a preset example", ["(manual entry)"] + list(EXAMPLES.keys()))

    default_id, default_data = ("", "")
    if preset != "(manual entry)":
        default_id, default_data = EXAMPLES[preset]

    col_a, col_b = st.columns(2)
    with col_a:
        can_id = st.text_input("CAN ID (hex)", value=default_id, placeholder="e.g. 0CEEFEFE")
    with col_b:
        data_hex = st.text_input("Data bytes (hex, 16 chars)", value=default_data,
                                 placeholder="e.g. 78320000640050FF")

    decode_btn = st.button("Decode frame", type="primary")

    if decode_btn and can_id and data_hex:
        try:
            frame_id = int(can_id.strip(), 16)
            data_bytes = bytes.fromhex(data_hex.strip())
        except ValueError as e:
            st.error(f"Bad input: {e}")
            st.stop()

        try:
            msg = db.get_message_by_frame_id(frame_id)
        except KeyError:
            st.error(f"CAN ID `{can_id}` not found in DBC — unknown message.")
            st.stop()

        decoded = msg.decode(data_bytes, decode_choices=False)

        st.divider()
        st.markdown(f"### {msg.name}")
        st.caption(f"CAN ID: `{can_id.upper()}h`  |  Length: {msg.length} bytes")

        byte_html = " ".join(f'<span class="raw-byte">{b:02X}</span>' for b in data_bytes)
        st.markdown(f"**Raw bytes:** {byte_html}", unsafe_allow_html=True)
        st.write("")

        result_rows = []
        for sig_name, value in decoded.items():
            sig = msg.get_signal_by_name(sig_name)
            unit = sig.unit or ""
            status = "OK"
            if sig.maximum and isinstance(value, (int, float)):
                if value >= sig.maximum * 0.98:
                    status = "N/A?"
            result_rows.append({
                "Signal (SPN)": sig_name,
                "Decoded Value": round(float(value), 4),
                "Unit": unit,
                "Status": status,
                "Bit position": f"start {sig.start}, {sig.length} bits",
                "Formula": f"raw × {sig.scale} + {sig.offset}",
            })

        res_df = pd.DataFrame(result_rows)
        st.dataframe(
            res_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Decoded Value": st.column_config.NumberColumn(format="%.4f"),
                "Status": st.column_config.TextColumn(),
            },
        )

        # Mini gauge row
        gauges = [r for r in result_rows if r["Status"] == "OK"]
        if gauges:
            st.write("")
            st.subheader("Signal gauges")
            gauge_cols = st.columns(min(len(gauges), 4))
            for i, r in enumerate(gauges[:4]):
                sig_obj = msg.get_signal_by_name(r["Signal (SPN)"])
                min_v = float(sig_obj.minimum) if sig_obj.minimum is not None else 0
                max_v = float(sig_obj.maximum) if sig_obj.maximum is not None else 100
                with gauge_cols[i]:
                    fig = gauge_fig(r["Decoded Value"], min_v, max_v,
                                    r["Signal (SPN)"], r["Unit"])
                    st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: Time-Series
# ═════════════════════════════════════════════════════════════════════════════

elif page == "📈  Time-Series":
    st.title("Time-Series Viewer")
    st.caption("Visualise decoded signal values over time from the CAN log")
    st.divider()

    if df.empty:
        st.warning("No log data loaded. Upload a CSV in the sidebar or use the default path.")
        st.stop()

    all_sigs = sorted(df["signal"].unique())

    col_sel, col_opts = st.columns([3, 1])
    with col_sel:
        selected = st.multiselect(
            "Select signals to plot",
            all_sigs,
            default=all_sigs[:3] if len(all_sigs) >= 3 else all_sigs,
        )
    with col_opts:
        normalize = st.checkbox("Normalize (0–1)", value=False)
        show_points = st.checkbox("Show data points", value=False)

    if not selected:
        st.info("Select at least one signal above.")
        st.stop()

    t_min = float(df["timestamp_s"].min())
    t_max = float(df["timestamp_s"].max())
    t_range = st.slider("Time range (s)", t_min, t_max, (t_min, t_max), step=0.001)

    plot_df = df[df["signal"].isin(selected) &
                 df["timestamp_s"].between(t_range[0], t_range[1])].copy()

    if normalize:
        def norm(g):
            mn, mx = g["value"].min(), g["value"].max()
            g = g.copy()
            g["value"] = (g["value"] - mn) / (mx - mn) if mx != mn else g["value"] * 0
            return g
        plot_df = plot_df.groupby("signal", group_keys=False).apply(norm)

    mode = "lines+markers" if show_points else "lines"

    fig = px.line(plot_df, x="timestamp_s", y="value", color="signal",
                  labels={"timestamp_s": "Time (s)", "value": "Value"},
                  template="plotly_dark",
                  line_shape="linear")
    fig.update_traces(mode=mode, line=dict(width=2))
    fig.update_layout(
        paper_bgcolor="#181825", plot_bgcolor="#181825",
        legend=dict(bgcolor="#1e1e2e", bordercolor="#313244"),
        xaxis=dict(gridcolor="#313244"),
        yaxis=dict(gridcolor="#313244"),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Stats table
    st.subheader("Statistics")
    stats = (
        plot_df.groupby(["signal", "unit"])["value"]
        .agg(Min="min", Mean="mean", Max="max", Std="std", Samples="count")
        .reset_index()
        .round(4)
    )
    st.dataframe(stats, use_container_width=True, hide_index=True)

    # Per-signal sparklines
    st.subheader("Individual sparklines")
    spark_cols = st.columns(min(len(selected), 3))
    colors = ["#89b4fa", "#a6e3a1", "#fab387", "#f38ba8", "#cba6f7", "#89dceb"]
    for i, sig in enumerate(selected):
        sdf = plot_df[plot_df["signal"] == sig]
        unit = sdf["unit"].iloc[0] if not sdf.empty else ""
        avg = sdf["value"].mean() if not sdf.empty else 0
        with spark_cols[i % 3]:
            st.markdown(f"**{sig}** `{avg:.2f} {unit}` avg")
            if not sdf.empty:
                st.plotly_chart(sparkline(sdf, colors[i % len(colors)]),
                                use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# PAGE: EV Battery
# ═════════════════════════════════════════════════════════════════════════════

elif page == "⚡  EV Battery":
    st.title("EV Battery Dashboard")
    st.caption("Real-time BMS signal overview from the CAN log")
    st.divider()

    EV_SIGNALS = {
        "HV_Battery_Voltage":        ("V",    0,   800,  "HV Pack Voltage"),
        "HV_Battery_Current":        ("A",  -600,  600,  "Pack Current"),
        "Battery_State_of_Charge":   ("%",    0,   100,  "State of Charge"),
        "Battery_State_of_Health":   ("%",    0,   100,  "State of Health"),
        "Battery_Pack_Temp":         ("°C", -40,   80,   "Pack Temperature"),
        "Cell_Voltage_Max":          ("V",    0,   4.2,  "Cell Vmax"),
        "Cell_Voltage_Min":          ("V",    0,   4.2,  "Cell Vmin"),
        "Cell_Voltage_Avg":          ("V",    0,   4.2,  "Cell Vavg"),
        "Charge_Power_Limit":        ("kW",   0,   250,  "Charge Power Limit"),
        "Isolation_Resistance":      ("kΩ",   0, 65535,  "Isolation Resistance"),
    }

    if df.empty:
        st.warning("No log data available. Upload a CSV or use the default path.")
        st.stop()

    ev_df = df[df["signal"].isin(EV_SIGNALS.keys())]
    available = ev_df["signal"].unique()

    if len(available) == 0:
        st.info("No EV/BMS signals found in the loaded log.")
        st.stop()

    # ── Top snapshot metrics ──────────────────────────────────────────────────
    st.subheader("Snapshot — last recorded value")
    last = ev_df.groupby("signal")["value"].last().to_dict()

    snap_signals = ["Battery_State_of_Charge", "HV_Battery_Voltage",
                    "Battery_Pack_Temp", "Cell_Voltage_Max", "Cell_Voltage_Min",
                    "Isolation_Resistance"]
    snap_avail = [s for s in snap_signals if s in last]
    snap_cols = st.columns(len(snap_avail))

    for i, sig in enumerate(snap_avail):
        unit, lo, hi, label = EV_SIGNALS[sig]
        val = last[sig]
        delta_label = ""
        snap_cols[i].metric(label, f"{val:.2f} {unit}", delta_label)

    st.divider()

    # ── Gauges ────────────────────────────────────────────────────────────────
    st.subheader("Live gauges")
    gauge_signals = [s for s in ["Battery_State_of_Charge", "HV_Battery_Voltage",
                                  "Battery_Pack_Temp", "Isolation_Resistance"]
                     if s in last]
    g_cols = st.columns(len(gauge_signals))
    for i, sig in enumerate(gauge_signals):
        unit, lo, hi, label = EV_SIGNALS[sig]
        fig = gauge_fig(last[sig], lo, hi, label, unit,
                        warn_pct=0.9 if sig == "Battery_Pack_Temp" else 0.8)
        with g_cols[i]:
            st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Cell voltage spread ───────────────────────────────────────────────────
    cell_sigs = [s for s in ["Cell_Voltage_Max", "Cell_Voltage_Min", "Cell_Voltage_Avg"]
                 if s in available]
    if cell_sigs:
        st.subheader("Cell voltage spread over time")
        cell_df = ev_df[ev_df["signal"].isin(cell_sigs)]
        fig_cell = px.line(cell_df, x="timestamp_s", y="value", color="signal",
                           labels={"timestamp_s": "Time (s)", "value": "Voltage (V)"},
                           template="plotly_dark")
        fig_cell.update_layout(
            paper_bgcolor="#181825", plot_bgcolor="#181825",
            legend=dict(bgcolor="#1e1e2e", bordercolor="#313244"),
            xaxis=dict(gridcolor="#313244"), yaxis=dict(gridcolor="#313244"),
            height=300,
        )
        st.plotly_chart(fig_cell, use_container_width=True)

    # ── SoC + Voltage over time ───────────────────────────────────────────────
    soc_volt = [s for s in ["Battery_State_of_Charge", "HV_Battery_Voltage"] if s in available]
    if len(soc_volt) >= 2:
        st.subheader("State of Charge vs HV Voltage")
        soc_df  = ev_df[ev_df["signal"] == "Battery_State_of_Charge"]
        volt_df = ev_df[ev_df["signal"] == "HV_Battery_Voltage"]

        fig2 = make_subplots(specs=[[{"secondary_y": True}]])
        fig2.add_trace(
            go.Scatter(x=soc_df["timestamp_s"], y=soc_df["value"],
                       name="SoC (%)", line=dict(color="#a6e3a1", width=2)),
            secondary_y=False,
        )
        fig2.add_trace(
            go.Scatter(x=volt_df["timestamp_s"], y=volt_df["value"],
                       name="HV Voltage (V)", line=dict(color="#89b4fa", width=2)),
            secondary_y=True,
        )
        fig2.update_layout(
            template="plotly_dark",
            paper_bgcolor="#181825", plot_bgcolor="#181825",
            legend=dict(bgcolor="#1e1e2e", bordercolor="#313244"),
            xaxis=dict(gridcolor="#313244", title="Time (s)"),
            height=320,
        )
        fig2.update_yaxes(title_text="SoC (%)", secondary_y=False, gridcolor="#313244")
        fig2.update_yaxes(title_text="HV Voltage (V)", secondary_y=True, gridcolor="#313244")
        st.plotly_chart(fig2, use_container_width=True)

    # ── Raw BMS table ─────────────────────────────────────────────────────────
    st.divider()
    with st.expander("Raw EV signal readings"):
        st.dataframe(ev_df.sort_values("timestamp_s"), use_container_width=True, hide_index=True)
