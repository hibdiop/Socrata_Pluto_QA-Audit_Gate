# NYC BBL Automated QA Gate & GRC Audit-Evidence Engine

An automated pre-commit ingestion gate, deterministic data verification pipeline, and audit logging framework. The engine validates agency-submitted building and energy telemetry against authoritative public municipal ground truth (NYC PLUTO via Socrata SODA API) before allowing downstream persistence, generating immutable audit artifacts for compliance triage and governance reporting.

---

## Summary &  Impact

Downstream operational registries (such as CRM/ERP instances or central registry databases) fail when unvalidated, self-reported data propagates silently into production schemas.

This engine implements strict **pre-commit gatekeeping and verification controls**:

* **Zero-Tolerance Semantic & Syntax Guardrails:** Enforces strict 10-digit borough-block-lot (BBL) identifiers on unparsed raw strings to prevent silent type coercion (e.g., dropping leading zeroes during float/int conversion).
* **Authoritative Baseline Cross-Reconciliation:** Pulls authoritative building footprints directly from NYC Open Data (PLUTO API) and executes vectorized variance checks ($\pm 10\%$ tolerance) against reported gross floor area (GFA).
* **Telemetry Integrity Controls:** Screens energy metrics to flag non-physical values ($EUI \le 0$) and decommissioned/inactive meters.
* **Deterministic Governance & Evidence Artifacts:** Divides ingest streams into clean production staging versus immutable, UTC-stamped audit logs broken down by agency and failure taxonomy.

---

## System Architecture

```mermaid
flowchart TB
    subgraph SOURCES["Authoritative & Agency Ingest"]
        S1["NYC PLUTO Ground Truth<br/>(Socrata SODA API 64uk-42ks)"]
        S2["Agency Ingestion Payload<br/>(sample_records.csv)"]
    end

    S1 -->|"fetch_pluto.py<br/>$select borocode,block,lot,bldgarea"| P1["data/pluto_gfa.csv<br/>Normalized 10-digit BBL Key"]
    S2 --> G1

    P1 --> G1

    subgraph GATE["Deterministic QA Gate — qa_gate.py"]
        G1["Precondition Validation<br/>(Schema validation, payload existence)"]
        G2["Type Preservation & Normalization<br/>(bbl_raw string retention, boolean coercion)"]
        G3["Relational Join on BBL Key<br/>(Left outer join with pluto_gfa)"]
        
        G1 --> G2 --> G3

        subgraph RULES["Rule Evaluation Engine"]
            R1["Rule 1: BBL Syntax & Check<br/>10 numeric digits on raw string"]
            R2["Rule 2: GFA Variance & Ground Truth<br/>Missing BBL OR |reported − PLUTO| / PLUTO > 0.10"]
            R3["Rule 3: Telemetry Sanity<br/>meter_active == False OR EUI ≤ 0"]
        end

        G3 --> R1
        G3 --> R2
        G3 --> R3

        R1 --> ROUTE{"Evaluation Router<br/>(Any Flags Triggered?)"}
        R2 --> ROUTE
        R3 --> ROUTE
    end

    ROUTE -->|"Clean (Zero Exceptions)"| C1["output/clean_staging.csv<br/>Downstream Ready Payload"]
    ROUTE -->|"Flagged (≥ 1 Violation)"| A1["output/audit_log.csv<br/>Immutable UTC-Stamped Evidence Log"]
    A1 --> A2["output/backlog_summary.csv<br/>Pivot Matrix: Agency × Error Code"]

    classDef source fill:#e8f0fe,stroke:#1a73e8,color:#0b1f3a
    classDef gate   fill:#fff4e5,stroke:#e37400,color:#3d1f00
    classDef pass   fill:#e6f4ea,stroke:#188038,color:#0b2b14
    classDef fail   fill:#fce8e6,stroke:#c5221f,color:#3b0906

    class S1,S2 source
    class G1,G2,G3,R1,R2,R3,ROUTE gate
    class C1 pass
    class A1,A2 fail

```

---

## Technical Mechanics: What the Code Executes

### 1. Ingestion & Ground-Truth Acquisition (`fetch_pluto.py`)

* Authenticates and queries NYC OpenData via Socrata SODA API (`64uk-42ks`).
* Extracts authoritative parcel attributes: `borocode`, `block`, `lot`, and `bldgarea`.
* Standardizes BBLs into an ISO/IEC 10-character composite key structure:

$$\text{BBL} = \text{Boro (1 digit)} + \text{Block (padded to 5 digits)} + \text{Lot (padded to 4 digits)}$$


* Caches normalized attributes to disk (`data/pluto_gfa.csv`) as an offline ground-truth lookup table.

### 2. Guardrail Enforcement & Execution (`qa_gate.py`)

The pipeline runs sequential vector checks across ingested records, evaluating each record against deterministic risk criteria:

| Rule Code | Validation Criteria | Mathematical / Logical Condition | Governance Risk Mitigated | Downstream Action |
|---|---|---|---|---|
| `ERR_BBL_SYNTAX` | Structural & Lexical Validity | `regex match: ^[0-9]{10}$` on unparsed string | Broken entity resolution, dropped leading zeroes, corrupt foreign keys. | Record rejected; isolated to audit trail. |
| `ERR_PLUTO_MISSING` | Ground Truth Existence | `gfa_pluto is NULL` | Phantom assets, unregistered parcels, fraudulent reporting. | Record rejected; isolated to audit trail. |
| `ERR_GFA_MISMATCH` | Physical Footprint Reconciliation | $\frac{\| \text{GFA}_{\text{reported}} - \text{GFA}_{\text{PLUTO}} \|}{\text{GFA}_{\text{PLUTO}}} > 0.10$ | Miscalculated emissions baselines, out-of-date building alterations. | Record rejected; isolated to audit trail. |
| `ERR_METER_INACTIVE` | Telemetry Validity & Active Status | `meter_active == False` OR $\text{EUI} \le 0$ | Skewed portfolio aggregates, zero-value division, inaccurate decarbonization benchmarks. | Record rejected; isolated to audit trail. |

### 3. Split-Stream Output & Audit Evidence Generation

The engine guarantees partition isolation between clean and non-compliant records:

* **Production-Safe Ingestion Target (`output/clean_staging.csv`):** Fully sanitized dataset guaranteed to meet relational schema constraints and reference tolerances. Safe for automated ingestion into downstream CRMs, ERPs, or data warehouses.
* **Non-Repudiation Audit Log (`output/audit_log.csv`):** Detailed exception records capturing input payload state, triggering error code, evaluated variance metrics, and UTC execution timestamps (`evaluated_at_utc`).
* **Governance Backlog Matrix (`output/backlog_summary.csv`):** An aggregated crosstab pivot (`reporting_agency` $\times$ `error_code`) providing immediate visibility into systemic agency-level data anomalies and root causes.

---

## Repository Structure

```
├── data/
│   ├── pluto_gfa.csv          # Authoritative reference dataset generated from PLUTO SODA API
│   └── sample_records.csv     # Raw ingested agency records (edge cases, anomalies, valid rows)
├── output/
│   ├── clean_staging.csv      # Verified, zero-defect records ready for downstream load
│   ├── audit_log.csv          # Granular evidence log of every flagged constraint
│   └── backlog_summary.csv    # Cross-tabulated triage matrix (Agency vs. Error Taxonomy)
├── scripts/
│   ├── fetch_pluto.py         # Socrata API extractor, BBL normalizer, and caching routine
│   └── qa_gate.py             # Rule engine, validation pipeline, and output router
├── requirements.txt
└── README.md

```

---

## Quickstart & Local Verification

### 1. Environment Initialization

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

```

### 2. Fetch Authoritative Ground Truth

```bash
# Pulls current PLUTO parcel and building area data from NYC Open Data SODA API
python3 scripts/fetch_pluto.py

```

### 3. Run the Verification Pipeline

```bash
# Processes records, applies rules, and partitions clean vs audit records
python3 scripts/qa_gate.py

```

### 4. Inspect Audit Outputs

```bash
# Review isolated non-compliant records
cat output/audit_log.csv

# Review agency-level failure triage summary
cat output/backlog_summary.csv

```
