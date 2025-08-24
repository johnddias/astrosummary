# app.py
# Streamlit app for astrophotography FITS analysis:
# - AstroBin CSV export (date, filter, number, duration [+ optional ISO/Binning/Gain])
# - Ratio Planner (per-target integration totals vs goal schemas, interactive pie charts in a grid)
# - Calibration awareness via IMAGETYP/OBSTYPE (LIGHT-only counted)
# - Cross-platform: threads on Windows, processes on POSIX
# Run: streamlit run app.py

import platform
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from typing import Dict, Tuple, Optional, Any, List

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from astropy.io import fits

# =========================
# Configuration / Defaults
# =========================

DEFAULT_FILTER_MAP_TEXT = (
    "R=3007\n"
    "Ha=4657\n"
    "OIII=4746\n"
    "SII=4838\n"
    "L=3012\n"
    "G=3011\n"
    "B=3008\n"
)

GOAL_RATIOS: Dict[str, Dict[str, int]] = {
    "SHO (2:1:1)": {"Ha": 2, "OIII": 1, "SII": 1},
    "HOO (2:1)": {"Ha": 2, "OIII": 1},
    "LRGB (2:1:1:1)": {"L": 2, "R": 1, "G": 1, "B": 1},
}
ALIASES = {
    "ha": "Ha", "hα": "Ha", "halpha": "Ha",
    "oiii": "OIII", "o3": "OIII",
    "sii": "SII", "s2": "SII",
    "luminance": "L", "lum": "L",
    "red": "R", "green": "G", "blue": "B",
}

# ================
# Helper functions
# ================


def build_target_stacked_bar(
    df_report: pd.DataFrame,
    target: str,
    goal_label: str,
    prefer_total_goal: bool = True,   # True -> use plan_total_need_s if available; else balance_need_s
    hide_zero_filters: bool = True,   # drop filters with zero captured & zero needed
) -> Optional[go.Figure]:
    """
    Build a stacked bar (hours) for one target.
    Bars are per-filter; stacks are 'Captured (h)' and 'Needed (h)'.
    Needed uses plan_total_need_s (if prefer_total_goal and present) else balance_need_s.
    """
    df_t = df_report[df_report["target"] == target].copy()
    if df_t.empty:
        return None

    # Ensure numeric
    for col in ["have_seconds", "have_hours", "balance_need_s", "plan_total_need_s", "goal_weight"]:
        if col not in df_t.columns:
            df_t[col] = 0
        df_t[col] = pd.to_numeric(df_t[col], errors="coerce").fillna(0.0)

    # Aggregate to one row per filter
    df_g = (
        df_t.groupby("filter", as_index=False)
            .agg(
                have_hours=("have_hours", "sum"),
                balance_need_s=("balance_need_s", "max"),
                plan_total_need_s=("plan_total_need_s", "max"),
                goal_weight=("goal_weight", "max"),
            )
    )

    # Needed hours selection
    if prefer_total_goal and (df_g["plan_total_need_s"].abs().sum() > 0):
        df_g["needed_hours"] = df_g["plan_total_need_s"] / 3600.0
        need_basis = "to reach total goal"
    else:
        df_g["needed_hours"] = df_g["balance_need_s"] / 3600.0
        need_basis = "to balance ratio"

    # Optionally hide filters with zero captured AND zero needed
    if hide_zero_filters:
        df_g = df_g[(df_g["have_hours"] > 0) | (df_g["needed_hours"] > 0)]

    if df_g.empty:
        return None

    # Order filters for readability: largest captured first
    df_g = df_g.sort_values("have_hours", ascending=False)

    # Build hover text
    hover_captured = [
        f"<b>{f}</b><br>Captured: {h:.2f} h" for f, h in zip(df_g["filter"], df_g["have_hours"])
    ]
    hover_needed = [
        f"<b>{f}</b><br>Needed ({need_basis}): {h:.2f} h" for f, h in zip(df_g["filter"], df_g["needed_hours"])
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_g["filter"],
            y=df_g["have_hours"],
            name="Captured (h)",
            hovertext=hover_captured,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=df_g["filter"],
            y=df_g["needed_hours"],
            name="Needed (h)",
            hovertext=hover_needed,
            hovertemplate="%{hovertext}<extra></extra>",
        )
    )

    fig.update_layout(
        title=f"{target} — {goal_label}",
        barmode="stack",
        xaxis_title="Filter",
        yaxis_title="Hours",
        margin=dict(l=10, r=10, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig

def parse_ratio_text(text: str) -> Dict[str, float]:
    """
    Parse user-entered ratio like:
      "Ha=2, OIII=1, SII=1"
      "L:2 R:1 G:1 B:1"
      "Ha 2; OIII 1; SII 1"
    Returns dict of {FilterName: weight}, only positive numbers kept.
    """
    if not text or not text.strip():
        return {}
    raw = (
        text.replace(",", " ")
            .replace(";", " ")
            .replace(":", "=")
    )
    out: Dict[str, float] = {}
    for token in raw.split():
        if "=" in token:
            k, v = token.split("=", 1)
        else:
            # allow "Ha 2" style if it slipped through
            parts = token.split()
            if len(parts) == 2:
                k, v = parts
            else:
                continue
        k = norm_filter(k.strip())
        try:
            w = float(v.strip())
            if w > 0:
                out[k] = w
        except Exception:
            continue
    return out


def parse_filter_map(text: str) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, val = line.split("=", 1)
        name, val = name.strip(), val.strip()
        try:
            mapping[name] = int(val)
        except ValueError:
            continue
    return mapping

def val_or_blank(values_set: set) -> str:
    cleaned = {v for v in values_set if v not in (None, "", "Unknown")}
    if len(cleaned) == 1:
        return str(next(iter(cleaned)))
    return ""

def read_iso(hdr) -> Optional[int]:
    for k in ("ISO", "ISOSPEED", "PHOTOMET", "ISOSET"):
        if k in hdr:
            try:
                return int(hdr.get(k))
            except Exception:
                try:
                    return int(float(hdr.get(k)))
                except Exception:
                    pass
    return None

def read_binning(hdr) -> Optional[int]:
    for k in ("XBINNING", "BINNING", "XBIN"):
        if k in hdr:
            try:
                return int(hdr.get(k))
            except Exception:
                try:
                    return int(float(hdr.get(k)))
                except Exception:
                    pass
    if "BINNING" in hdr:
        val = str(hdr.get("BINNING"))
        if "x" in val.lower():
            try:
                return int(val.lower().split("x")[0])
            except Exception:
                pass
    return None

def read_gain(hdr) -> Optional[float]:
    for k in ("GAIN", "GAINSETTING", "GAIN_SET"):
        if k in hdr:
            try:
                return float(hdr.get(k))
            except Exception:
                pass
    return None

def normalize_frame_type(raw: str) -> str:
    if not raw:
        return "UNKNOWN"
    s = str(raw).strip().upper()
    if s.startswith("LIGHT"):
        return "LIGHT"
    if s in {"DARK", "DARKS", "MASTER DARK", "MASTER_DARK"}:
        return "DARK"
    if s in {"FLAT", "FLATS", "MASTER FLAT", "MASTER_FLAT"}:
        return "FLAT"
    if s in {"BIAS", "OFFSET", "OFFSETS", "MASTER BIAS", "MASTER_BIAS"}:
        return "BIAS"
    if s in {"DARKFLAT", "FLATDARK", "FLAT DARK", "DARK FLAT", "MASTER_DARKFLAT"}:
        return "DARKFLAT"
    return s

def get_frame_type(hdr) -> str:
    t = hdr.get("IMAGETYP")
    if not t:
        t = hdr.get("OBSTYPE")
    return normalize_frame_type(t)

def norm_filter(name: str) -> str:
    if not name:
        return "Unknown"
    k = str(name).strip().lower()
    return ALIASES.get(k, name.strip())

def collect_files(root: str, recurse: bool) -> List[Path]:
    p = Path(root)
    if not p.exists():
        return []
    patterns = ("*.fits", "*.fit")
    files: List[Path] = []
    if recurse:
        for ext in patterns:
            files += list(p.rglob(ext))
    else:
        for ext in patterns:
            files += list(p.glob(ext))
    return files

def _executor_cls():
    """Use threads on Windows (Streamlit multiproc quirks), processes elsewhere."""
    return ThreadPoolExecutor if platform.system() == "Windows" else ProcessPoolExecutor

# =======================
# Extraction / Summaries
# =======================

def extract_fits_metadata(path: Path):
    """For AstroBin export summarization; returns (date_str, ftype, filt, exptime, iso, binning, gain)"""
    try:
        with fits.open(path, ignore_missing_end=True, memmap=True) as hdul:
            hdr = hdul[0].header
            ftype = get_frame_type(hdr)
            date_obs = hdr.get("DATE-OBS")
            filt = hdr.get("FILTER", "Unknown")
            exptime_raw = hdr.get("EXPTIME", 0)

            if not date_obs:
                return ("UNKNOWN", ftype, None, None, None, None, None)

            date_token = str(date_obs).split("T")[0].strip()
            date_str = datetime.fromisoformat(date_token).strftime("%Y-%m-%d")

            iso = read_iso(hdr)
            binning = read_binning(hdr)
            gain = read_gain(hdr)

            try:
                exptime = float(exptime_raw)
            except Exception:
                exptime = 0.0

            return (date_str, ftype, str(filt), exptime, iso, binning, gain)
    except Exception:
        return ("ERROR", "UNKNOWN", None, None, None, None, None)

def extract_target_filter_exptime(fpath: Path):
    """For Ratio Planner; returns (target, ftype, filt, exptime)"""
    try:
        with fits.open(fpath, ignore_missing_end=True, memmap=True) as hdul:
            hdr = hdul[0].header
            ftype = get_frame_type(hdr)
            target = (hdr.get("OBJECT") or "").strip() or "(Unknown Target)"
            filt = norm_filter(hdr.get("FILTER", "Unknown"))
            try:
                exptime = float(hdr.get("EXPTIME", 0))
            except Exception:
                exptime = 0.0
            return (target, ftype, filt, exptime)
    except Exception:
        return ("ERROR", "UNKNOWN", None, 0.0)

def summarize_for_astrobin(files, progress_cb=None):
    """
    Group by date -> filter -> exposure time (LIGHT only).
    Return (summary, counts_by_type)
    """
    summary = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {
        "count": 0, "iso_set": set(), "binning_set": set(), "gain_set": set()
    })))
    counts_by_type = defaultdict(int)

    total = len(files); done = 0
    Executor = _executor_cls()
    with Executor() as executor:
        futures = {executor.submit(extract_fits_metadata, f): f for f in files}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                date_str, ftype, filt, exptime, iso, binning, gain = res
                counts_by_type[ftype] += 1
                if ftype == "LIGHT" and date_str not in ("UNKNOWN", "ERROR") and exptime and exptime > 0:
                    bucket = summary[date_str][filt][float(exptime)]
                    bucket["count"] += 1
                    bucket["iso_set"].add(iso if iso is not None else "")
                    bucket["binning_set"].add(binning if binning is not None else "")
                    bucket["gain_set"].add(gain if gain is not None else "")
            done += 1
            if progress_cb:
                progress_cb(done, total)
    return summary, counts_by_type

def scan_totals_by_target(files, progress_cb=None):
    """
    Sum LIGHT integration per target × filter.
    Return (totals_by_target, counts_by_type)
    """
    totals = defaultdict(lambda: defaultdict(float))
    counts_by_type = defaultdict(int)

    total = len(files); done = 0
    Executor = _executor_cls()
    with Executor() as pool:
        futures = {pool.submit(extract_target_filter_exptime, f): f for f in files}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                target, ftype, filt, exptime = res
                counts_by_type[ftype] += 1
                if ftype == "LIGHT" and filt and exptime > 0:
                    totals[target][filt] += exptime
            done += 1
            if progress_cb:
                progress_cb(done, total)
    return totals, counts_by_type

def build_astrobin_df(summary, filter_map: Dict[str, int],
                      include_iso: bool, include_binning: bool, include_gain: bool) -> pd.DataFrame:
    rows = []
    for date, filt_dict in summary.items():
        for filt, exp_dict in filt_dict.items():
            for exptime, stats in exp_dict.items():
                row = {
                    "date": date,
                    "filter": filter_map.get(filt, ""),
                    "number": stats["count"],
                    "duration": round(float(exptime), 4),
                }
                if include_iso:
                    row["iso"] = val_or_blank(stats["iso_set"])
                if include_binning:
                    row["binning"] = val_or_blank(stats["binning_set"])
                if include_gain:
                    g = val_or_blank(stats["gain_set"])
                    try:
                        row["gain"] = f"{float(g):.2f}" if g != "" else ""
                    except Exception:
                        row["gain"] = ""
                rows.append(row)

    cols = ["date", "filter", "number", "duration"]
    if include_iso: cols.append("iso")
    if include_binning: cols.append("binning")
    if include_gain: cols.append("gain")

    if not rows:
        return pd.DataFrame(columns=cols)

    df = pd.DataFrame(rows)
    return df[cols].sort_values(by=["date", "filter", "duration"]).reset_index(drop=True)

def normalize_ratio(d: dict):
    total = sum(d.values()) or 1.0
    return {k: v/total for k, v in d.items()}

def balance_deficits(current_s: dict, goal_ratio: dict):
    """Keep strongest feasible scale (no reductions)."""
    if not current_s:
        return {}, {}
    goal_keys = list(goal_ratio.keys())
    current = {k: current_s.get(k, 0.0) for k in goal_keys}
    if all(v == 0 for v in current.values()):
        return {k: 0.0 for k in goal_keys}, {k: 0.0 for k in goal_keys}
    bases = []
    for k in goal_keys:
        g = goal_ratio[k]
        if g > 0:
            bases.append(current[k] / g if current[k] > 0 else 0.0)
    base = min(bases) if bases else 0.0
    desired = {k: goal_ratio[k]*base for k in goal_keys}
    deficits = {k: max(0.0, desired[k] - current[k]) for k in goal_keys}
    return desired, deficits

def plan_to_total_hours(current_s: dict, goal_ratio: dict, total_hours: float):
    total_seconds = total_hours * 3600.0
    sum_goal = sum(goal_ratio.values()) or 1.0
    desired = {k: total_seconds * (goal_ratio[k] / sum_goal) for k in goal_ratio.keys()}
    deficits = {k: max(0.0, desired[k] - current_s.get(k, 0.0)) for k in desired.keys()}
    return desired, deficits

def build_ratio_report_df(totals_by_target: dict,
                          goal_ratio: Dict[str, float],
                          desired_total_hours: Optional[float]) -> pd.DataFrame:
    """
    Build per-target, per-filter table using an explicit goal_ratio mapping.
    goal_ratio keys should be canonical filter names (Ha, OIII, SII, L, R, G, B).
    """
    rows = []
    for target, filt_secs in sorted(totals_by_target.items()):
        have = {f: filt_secs.get(f, 0.0) for f in sorted(filt_secs.keys())}
        have_ratio = normalize_ratio({k: v for k, v in have.items() if v > 0})

        # Align goal ratio to existing filters + any extra goal keys
        # so that rows contain union of both sets.
        goal_keys = set(goal_ratio.keys())
        have_keys = set(have.keys())
        all_keys = sorted(goal_keys.union(have_keys))

        # Use only the goal weights provided (missing filters => 0)
        goal = {k: float(goal_ratio.get(k, 0.0)) for k in all_keys}

        desired_bal, deficits_bal = balance_deficits(filt_secs, goal)

        desired_tot, deficits_tot = ({}, {})
        if desired_total_hours and desired_total_hours > 0:
            desired_tot, deficits_tot = plan_to_total_hours(filt_secs, goal, desired_total_hours)

        for f in all_keys:
            rows.append({
                "target": target,
                "filter": f,
                "have_seconds": round(have.get(f, 0.0), 1),
                "have_hours": round(have.get(f, 0.0)/3600.0, 2),
                "have_ratio": round(have_ratio.get(f, 0.0), 3),
                "goal_weight": goal.get(f, 0.0),
                "balance_want_s": round(desired_bal.get(f, 0.0), 1),
                "balance_need_s": round(deficits_bal.get(f, 0.0), 1),
                "plan_total_want_s": round(desired_tot.get(f, 0.0), 1) if desired_tot else "",
                "plan_total_need_s": round(deficits_tot.get(f, 0.0), 1) if deficits_tot else "",
            })
    return pd.DataFrame(rows)

# --------------------------
# Chart helper (no customdata)
# --------------------------

def build_target_pie(df_report: pd.DataFrame,
                     target: str,
                     schema_name: str,
                     value_mode: str = "seconds",   # "seconds" or "hours"
                     min_percent: float = 0.0       # hide slices below this %
                     ) -> Optional[go.Figure]:
    """
    Build a donut pie for a single target using df_report rows for that target.
    Expects df_report columns: target, filter, have_seconds, goal_weight, balance_need_s, plan_total_need_s.
    Returns a go.Figure or None if there is no LIGHT exposure for the target.
    """
    df_t = df_report[df_report["target"] == target].copy()
    if df_t.empty:
        return None

    # Ensure numeric
    for col in ["have_seconds","have_hours","have_ratio","goal_weight","balance_need_s","plan_total_need_s"]:
        if col not in df_t.columns:
            df_t[col] = 0
        df_t[col] = pd.to_numeric(df_t[col], errors="coerce").fillna(0.0)

    # Aggregate to one row per filter
    df_g = (
        df_t.groupby("filter", as_index=False)
            .agg(
                have_seconds=("have_seconds", "sum"),
                goal_weight=("goal_weight", "max"),
                balance_need_s=("balance_need_s", "max"),
                plan_total_need_s=("plan_total_need_s", "max"),
            )
    )

    total_secs = float(df_g["have_seconds"].sum())
    if total_secs <= 0:
        return None

    # Derive fields
    df_g["have_hours"] = df_g["have_seconds"] / 3600.0
    df_g["have_ratio"] = df_g["have_seconds"] / max(total_secs, 1e-9)
    df_g["percent"] = df_g["have_ratio"] * 100.0

    # Choose pie values
    if value_mode.lower() == "hours":
        values = df_g["have_hours"]
        value_label = "Hours"
        value_fmt = lambda x: f"{x:.2f}h"
    else:
        values = df_g["have_seconds"]
        value_label = "Seconds"
        value_fmt = lambda x: f"{x:,.0f}s"

    # Optional: hide tiny slices
    if min_percent > 0:
        df_g = df_g[df_g["percent"] >= float(min_percent)]
        values = values[df_g.index]

    # Prepare rounded/label fields
    df_g = df_g.assign(
        _filter=df_g["filter"].astype(str),
        _secs=df_g["have_seconds"].round(0),
        _hours=df_g["have_hours"].round(2),
        _ratio=df_g["have_ratio"].round(3),
        _pct=df_g["percent"].round(1),
        _goal=df_g["goal_weight"].fillna(0).astype(int),
        _need_bal=df_g["balance_need_s"].round(0),
        _need_tot=df_g["plan_total_need_s"].round(0),
        _total_hours=(total_secs / 3600.0),
    )
    df_g["_need_tot_str"] = df_g["_need_tot"].apply(lambda x: "—" if pd.isna(x) or x == 0 else f"{x:,.0f}s")

    # Build per-slice hover text (use dict records to preserve exact column names)
    needed_cols = ["_filter","_secs","_hours","_ratio","_pct","_goal","_need_bal","_need_tot_str","_total_hours"]
    rows = df_g[needed_cols].to_dict(orient="records")

    hovertext = []
    for row in rows:
        value_display = value_fmt(row["_hours"] if value_label == "Hours" else row["_secs"])
        hovertext.append(
            f"<b>{row['_filter']}</b><br>"
            f"{value_label}: {value_display}<br>"
            f"Seconds: {row['_secs']:,.0f}s<br>"
            f"Hours: {row['_hours']:.2f}h<br>"
            f"Current ratio: {row['_ratio']:.3f}<br>"
            f"Slice of total: {row['_pct']:.1f}%<br>"
            f"Goal weight: {row['_goal']}<br>"
            f"Need to balance: {row['_need_bal']:,.0f}s<br>"
            f"Need to reach total: {row['_need_tot_str']}<br>"
            f"<span style='opacity:0.7'>(Total hours: {row['_total_hours']:.2f}h)</span>"
        )


    fig = go.Figure(
        data=[
            go.Pie(
                labels=df_g["_filter"],
                values=values,
                hole=0.3,
                text=hovertext,
                textinfo="percent+label",
                hovertemplate="%{text}<extra></extra>",
            )
        ]
    )
    fig.update_layout(title_text=f"{target} — {schema_name}", margin=dict(l=10, r=10, t=40, b=10))
    return fig

# ===========
# Streamlit UI
# ===========

st.set_page_config(page_title="AstroSummary", layout="wide")
st.title("AstroSummary — FITS Integration & AstroBin Export")

with st.sidebar:
    st.header("Source")
    root_path = st.text_input("Image folder (e.g., Y:/M101 or /data/m101)", value="")
    recurse = st.checkbox("Recurse subfolders", value=True)
    mode = st.selectbox("Mode", ["AstroBin Export", "Ratio Planner"])

files = collect_files(root_path, recurse)
st.sidebar.write(f"Found {len(files)} FITS files.")

# -------------------------
# AstroBin Export Interface
# -------------------------

if mode == "AstroBin Export":
    st.header("AstroBin Export")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        add_iso = st.checkbox("Include ISO", value=False)
        add_binning = st.checkbox("Include Binning", value=False)
        add_gain = st.checkbox("Include Gain", value=False)
    with col2:
        output_name = st.text_input("Output CSV filename", value="astrobin_acquisitions.csv")
    with col3:
        st.write("Filter → AstroBin ID mapping:")
        filter_map_text = st.text_area("Edit lines like 'Ha=4657'", value=DEFAULT_FILTER_MAP_TEXT, height=150)

    run = st.button("Build CSV")
    progress = st.progress(0)
    status = st.empty()

    if run:
        if not files:
            status.warning("No files found.")
        else:
            def prog(done, total):
                progress.progress(int(done/total*100))
                if done == total:
                    progress.progress(100)

            summary, counts = summarize_for_astrobin(files, progress_cb=prog)
            fmap = parse_filter_map(filter_map_text)
            df_csv = build_astrobin_df(summary, fmap, add_iso, add_binning, add_gain)

            status.success(f"Built {len(df_csv)} rows.")
            st.subheader("Preview")
            st.dataframe(df_csv, use_container_width=True, height=400)

            st.subheader("Frame type summary")
            st.table(
                pd.DataFrame(
                    [{"type": k, "count": v} for k, v in sorted(counts.items())]
                ).sort_values("type")
            )

            csv_bytes = df_csv.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv_bytes, file_name=output_name, mime="text/csv")

            st.subheader("Copy to Clipboard (manual)")
            st.text_area("CSV", df_csv.to_csv(index=False), height=250)

# ----------------------
# Ratio Planner Interface
# ----------------------

elif mode == "Ratio Planner":
    st.header("Ratio Planner")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        ratio_source = st.radio("Ratio source", ["Equal (1:1:1)", "Custom", "Preset"], index=0, horizontal=False)
    with c2:
       desired_hours = st.text_input("Desired total hours (optional)", value="")
    with c3:
        n_cols = st.number_input("Charts per row", min_value=1, max_value=4, value=2, step=1)

    custom_ratio_text = ""
    schema_name = None
    if ratio_source == "Custom":
        custom_ratio_text = st.text_input("Custom ratio (e.g., Ha=2, OIII=1, SII=1)", value="")
    elif ratio_source == "Preset":
        schema_name = st.selectbox("Preset schema", list(GOAL_RATIOS.keys()), index=0)

    #value_mode_choice = st.radio("Pie values", ["Hours", "Seconds"], index=0, horizontal=True)
    run2 = st.button("Generate Report & Charts")
    progress2 = st.progress(0)
    status2 = st.empty()


    if run2:
        if not files:
            status2.warning("No files found.")
        else:
            def prog(done, total):
                progress2.progress(int(done/total*100))
                if done == total:
                    progress2.progress(100)

            totals, counts = scan_totals_by_target(files, progress_cb=prog)

            # 1. Decide on goal_ratio
            if ratio_source == "Custom":
                goal_ratio = parse_ratio_text(custom_ratio_text)
            elif ratio_source == "Preset":
                goal_ratio = GOAL_RATIOS[schema_name].copy()
            else:
                goal_ratio = {}

            # 2. If empty, build equal 1:1:1 using the filters actually present
            if not goal_ratio:
                present_filters = set()
                for _t, filt_map in totals.items():
                    present_filters.update(k for k, v in filt_map.items() if v > 0)
                if present_filters:
                    goal_ratio = {f: 1.0 for f in sorted(present_filters)}

            # 3. Parse desired hours
            try:
                dhrs = float(desired_hours) if desired_hours.strip() else None
                if dhrs is not None and dhrs <= 0:
                    dhrs = None
            except Exception:
                dhrs = None

            # 4. Build the report with the explicit goal_ratio
            df_report = build_ratio_report_df(totals_by_target=totals,
                                            goal_ratio=goal_ratio,
                                            desired_total_hours=dhrs)
            status2.success(f"Report rows: {len(df_report)}")

            # ----- Stacked bars for ALL targets in a grid (hours only) -----
            st.subheader("Captured vs Needed (hours) — all targets")
            if df_report.empty:
                st.info("No LIGHT frames found for charting.")
            else:
                targets = sorted(df_report["target"].unique().tolist())
                cols = st.columns(int(n_cols))

                col_idx = 0
                goal_label = (schema_name or "Equal/Custom") if 'schema_name' in locals() and schema_name else "Equal/Custom"

                for target in targets:
                    fig = build_target_stacked_bar(
                        df_report=df_report,
                        target=target,
                        goal_label=goal_label,
                        prefer_total_goal=True,     # if desired_total_hours given, shows plan-to-total needs
                        hide_zero_filters=True
                    )
                    if fig is None:
                        continue
                    with cols[col_idx]:
                        st.plotly_chart(fig, use_container_width=True)
                    col_idx = (col_idx + 1) % int(n_cols)

            # ----- Tabular report & downloads -----
            st.subheader("Per-target, per-filter report")
            st.dataframe(df_report, use_container_width=True, height=500)

            st.download_button(
                "Download Report (CSV)",
                df_report.to_csv(index=False).encode("utf-8"),
                file_name="ratio_report.csv",
                mime="text/csv"
            )

            # Frame-type summary
            st.subheader("Frame type summary")
            st.table(
                pd.DataFrame(
                    [{"type": k, "count": v} for k, v in sorted(counts.items())]
                ).sort_values("type")
            )
