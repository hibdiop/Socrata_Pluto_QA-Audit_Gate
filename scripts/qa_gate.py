import pandas as pd
import datetime
import os
import sys

# ---------- Path setup (MUST come before anything that uses DATA_DIR/OUTPUT_DIR) ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
import pandas as pd
import datetime
import os
import sys

# ---------- Path setup (must be defined before anything references it) ----------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------- Precondition checks ----------
for fname in ("sample_records.csv", "pluto_gfa.csv"):
    fpath = os.path.join(DATA_DIR, fname)
    if not os.path.exists(fpath):
        sys.exit(f"FATAL: missing input: {fpath}")
    if os.path.getsize(fpath) == 0:
        sys.exit(f"FATAL: empty input file: {fpath}")

# ---------- 1. Read agency-reported records ----------
df = pd.read_csv(os.path.join(DATA_DIR, "sample_records.csv"), dtype={"bbl": str})
df["bbl_raw"] = df["bbl"]                       # preserve raw for Rule 1
df["bbl"] = df["bbl"].str.strip()               # normalize whitespace only
df["meter_active"] = (
    df["meter_active"].astype(str).str.lower()
      .map({"true": True, "false": False}).fillna(False)
)

# ---------- 2. Read real PLUTO ----------
pluto = pd.read_csv(os.path.join(DATA_DIR, "pluto_gfa.csv"), dtype={"bbl": str})
pluto["bbl"] = pluto["bbl"].str.strip()

# ---------- 3. Left join: attach real gfa_pluto ----------
df = df.drop(columns=["gfa_pluto"], errors="ignore")
df = df.merge(pluto[["bbl", "gfa_pluto"]], on="bbl", how="left")

# ---------- 4. Rule engine ----------
qa_evidence = []
clean_records = []

for _, row in df.iterrows():
    flags = []

    # Rule 1: BBL integrity — validate on raw value, not the padded/normalized one
    if not (len(str(row["bbl_raw"])) == 10 and str(row["bbl_raw"]).isdigit()):
        flags.append({"code": "ERR_BBL_SYNTAX", "root_cause": "BBL is not 10 numeric digits"})

    # Rule 2: GFA reconciliation against real PLUTO (±10%)
    if pd.notna(row.get("gfa_pluto")) and row["gfa_pluto"] > 0:
        gfa_diff = abs(row["gfa_reported"] - row["gfa_pluto"]) / row["gfa_pluto"]
        if gfa_diff > 0.10:
            flags.append({
                "code": "ERR_GFA_MISMATCH",
                "root_cause": f"GFA deviates {gfa_diff:.1%} from PLUTO (>10%)"
            })
    elif pd.isna(row.get("gfa_pluto")):
        flags.append({
            "code": "ERR_PLUTO_MISSING",
            "root_cause": "BBL not found in PLUTO reference extract"
        })

    # Rule 3: EUI / meter
    if row.get("eui", 0) <= 0 or not row.get("meter_active", False):
        flags.append({"code": "ERR_METER_INACTIVE", "root_cause": "Inactive meter or zero EUI"})

    # ---------- 5. Route ----------
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if flags:
        for f in flags:
            qa_evidence.append({
                "timestamp": timestamp,
                "record_id": row["record_id"],
                "bbl": row["bbl_raw"],           # evidence records the raw BBL submitted
                "agency": row["agency"],
                "error_code": f["code"],
                "root_cause": f["root_cause"],
                "status": "BLOCKED_AT_GATE"
            })
    else:
        clean_records.append(row.to_dict())

# ---------- 6. Export deliverables ----------
audit_df = pd.DataFrame(qa_evidence)
clean_df = pd.DataFrame(clean_records)

audit_df.to_csv(os.path.join(OUTPUT_DIR, "audit_log.csv"), index=False)
clean_df.to_csv(os.path.join(OUTPUT_DIR, "clean_staging.csv"), index=False)

if not audit_df.empty:
    backlog = audit_df.groupby(["agency", "error_code"]).size().reset_index(name="incident_count")
    backlog.to_csv(os.path.join(OUTPUT_DIR, "backlog_summary.csv"), index=False)
    print("=== BACKLOG ===")
    print(backlog)
else:
    print("No violations — all records passed.")

print("\n=== CLEAN STAGING ===")
print(clean_df[["record_id", "bbl", "agency"]] if not clean_df.empty else "No clean records.")

print("\n=== AUDIT EVIDENCE ===")
print(audit_df[["record_id", "error_code", "root_cause"]] if not audit_df.empty else "No violations.")
# ---------- Precondition checks ----------
for fname in ("sample_records.csv", "pluto_gfa.csv"):
    fpath = os.path.join(DATA_DIR, fname)
    if not os.path.exists(fpath):
        sys.exit(f"FATAL: missing input: {fpath}")
    if os.path.getsize(fpath) == 0:
        sys.exit(f"FATAL: empty input file: {fpath}")

# ---------- 1. Read agency-reported records ----------
df = pd.read_csv(os.path.join(DATA_DIR, "sample_records.csv"), dtype={"bbl": str})
df["bbl"] = df["bbl"].str.zfill(10)

# ---------- 2. Read real PLUTO building area from Socrata ----------
pluto = pd.read_csv(os.path.join(DATA_DIR, "pluto_gfa.csv"), dtype={"bbl": str})
pluto["bbl"] = pluto["bbl"].str.zfill(10)

# ---------- 3. Left join: attach real gfa_pluto to agency records ----------
df = df.drop(columns=["gfa_pluto"], errors="ignore")
df = df.merge(pluto[["bbl", "gfa_pluto"]], on="bbl", how="left")

# ---------- 4. Rule engine ----------
qa_evidence = []
clean_records = []

for _, row in df.iterrows():
    flags = []

    # Rule 1: BBL must be 10 digits
    if not (len(str(row["bbl"])) == 10 and str(row["bbl"]).isdigit()):
        flags.append({"code": "ERR_BBL_SYNTAX", "root_cause": "BBL is not 10 numeric digits"})

    # Rule 2: GFA deviation > 10% vs real PLUTO
    if pd.notna(row.get("gfa_pluto")) and row["gfa_pluto"] > 0:
        gfa_diff = abs(row["gfa_reported"] - row["gfa_pluto"]) / row["gfa_pluto"]
        if gfa_diff > 0.10:
            flags.append({
                "code": "ERR_GFA_MISMATCH",
                "root_cause": f"GFA deviates {gfa_diff:.1%} from PLUTO (>10%)"
            })
    elif pd.isna(row.get("gfa_pluto")):
        flags.append({
            "code": "ERR_PLUTO_MISSING",
            "root_cause": "BBL not found in PLUTO reference extract"
        })

    # Rule 3: EUI / meter
    if row.get("eui", 0) <= 0 or not row.get("meter_active", False):
        flags.append({"code": "ERR_METER_INACTIVE", "root_cause": "Inactive meter or zero EUI"})

    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if flags:
        for f in flags:
            qa_evidence.append({
                "timestamp": timestamp,
                "record_id": row["record_id"],
                "bbl": row["bbl"],
                "agency": row["agency"],
                "error_code": f["code"],
                "root_cause": f["root_cause"],
                "status": "BLOCKED_AT_GATE"
            })
    else:
        clean_records.append(row.to_dict())

# ---------- 5. Export deliverables ----------
audit_df = pd.DataFrame(qa_evidence)
clean_df = pd.DataFrame(clean_records)

audit_df.to_csv(os.path.join(OUTPUT_DIR, "audit_log.csv"), index=False)
clean_df.to_csv(os.path.join(OUTPUT_DIR, "clean_staging.csv"), index=False)

if not audit_df.empty:
    backlog = audit_df.groupby(["agency", "error_code"]).size().reset_index(name="incident_count")
    backlog.to_csv(os.path.join(OUTPUT_DIR, "backlog_summary.csv"), index=False)
    print(backlog)
else:
    print("No violations — all records passed.")

print("\n=== CLEAN STAGING ===")
print(clean_df[["record_id", "bbl", "agency"]] if not clean_df.empty else "No clean records.")

print("\n=== AUDIT EVIDENCE ===")
print(audit_df[["record_id", "error_code", "root_cause"]] if not audit_df.empty else "No violations.")