# NYC BBL QA Gate & Audit-Evidence Engine

A pre-commit validation pipeline that sits between agency-reported building data and downstream systems (Salesforce / BBL registry). Every record that fails a rule leaves an immutable, UTC-stamped audit record and a categorized remediation backlog entry.
## Architecture

```mermaid
flowchart TB
    subgraph SOURCES["Data Sources"]
        S1["NYC PLUTO<br/>(Socrata 64uk-42ks)"]
        S2["Agency-reported records<br/>(data/sample_records.csv)"]
    end

    S1 -->|"fetch_pluto.py<br/>$select borocode,block,lot,bldgarea"| P1["data/pluto_gfa.csv<br/>10-digit BBL + GFA"]
    S2 --> G1

    P1 --> G1

    subgraph GATE["QA Gate — qa_gate.py"]
        G1["Precondition checks<br/>(files exist, non-empty)"]
        G1 --> G2["Load + normalize<br/>(bbl_raw preserved, meter_active → bool)"]
        G2 --> G3["Left join on BBL<br/>(attach gfa_pluto)"]
        G3 --> R1
        G3 --> R2
        G3 --> R3
        R1["R1: BBL syntax<br/>10 numeric digits (raw)"]
        R2["R2: GFA reconciliation<br/>|reported − PLUTO| / PLUTO > 10%"]
        R3["R3: Meter integrity<br/>EUI ≤ 0 or meter inactive"]
        R1 --> ROUTE
        R2 --> ROUTE
        R3 --> ROUTE
        ROUTE{"Any flags?"}
    end

    ROUTE -->|"No"| C1["output/clean_staging.csv<br/>(ready for Salesforce)"]
    ROUTE -->|"Yes"| A1["output/audit_log.csv<br/>UTC-stamped evidence"]
    A1 --> A2["output/backlog_summary.csv<br/>agency × error_code triage"]

    classDef source fill:#e8f0fe,stroke:#1a73e8,color:#0b1f3a
    classDef gate   fill:#fff4e5,stroke:#e37400,color:#3d1f00
    classDef pass   fill:#e6f4ea,stroke:#188038,color:#0b2b14
    classDef fail   fill:#fce8e6,stroke:#c5221f,color:#3b0906

    class S1,S2 source
    class G1,G2,G3,R1,R2,R3,ROUTE gate
    class C1 pass
    class A1,A2 fail
```

## Business Context
This pipeline replicates the pre-commit validation logic a Compliance & Reporting Senior Program Manager would design at NYC DCAS DEM: before agency-reported building data enters the Salesforce/BBL registry, it must pass automated gates with retained audit evidence.

## Data Sources
| Source | Provider | Method |
|---|---|---|
| Agency-reported records | Simulated in `data/sample_records.csv` | Hand-crafted for rule coverage |
| **Authoritative GFA** | **NYC PLUTO** (Socrata `64uk-42ks`) | `scripts/fetch_pluto.py` calls the SODA API and writes `data/pluto_gfa.csv` |

## Rules
| ID | Condition | Error Code | Downstream Action |
|----|-----------|------------|-------------------|
| R1 | BBL ≠ 10 numeric digits (validated on raw value) | `ERR_BBL_SYNTAX` | Block + backlog |
| R2 | \|GFA_reported − GFA_PLUTO\| / GFA_PLUTO > 10% | `ERR_GFA_MISMATCH` | Block + backlog |
| R2b | BBL not found in PLUTO extract | `ERR_PLUTO_MISSING` | Block + backlog |
| R3 | EUI ≤ 0 OR `meter_active = False` | `ERR_METER_INACTIVE` | Block + backlog |

## Outputs
- `output/clean_staging.csv` — records ready for downstream ingestion
- `output/audit_log.csv` — immutable audit evidence with UTC timestamp
- `output/backlog_summary.csv` — root-cause triage by agency × error code

## Setup (macOS)
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/fetch_pluto.py     # pulls real PLUTO data from Socrata
python3 scripts/qa_gate.py         # runs the gate, writes output/