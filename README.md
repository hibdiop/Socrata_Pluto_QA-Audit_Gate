# Automated Ingestion Control Gate & Audit-Evidence Pipeline

An automated pre-commit control gate that enforces deterministic data integrity, policy reconciliation against external ground truth, and immutable audit logging prior to downstream system ingestion.

Designed to operationalize Data Integrity Controls, Policy Enforcement Gates, and Defensible Audit Evidence Collection, this pipeline prevents unverified, corrupt, or out-of-tolerance records from reaching downstream reporting systems (e.g., Salesforce, ERPs, reporting warehouses).

Executive Summary & Capabilities
Automated Defensive Controls: Intercepts untrusted source inputs and applies deterministic syntactical, referential, and statistical tolerance checks before committing data to staging.

Deterministic Ground-Truth Cross-Validation: Validates self-reported agency metrics against authoritative external ground truth (NYC OpenData/Socrata PLUTO), computing automated deviation thresholds (10% allowable drift).

Immutable Audit Trail: Automatically writes UTC-timestamped, rule-tagged audit artifacts for every non-compliant record to ensure full forensic traceability and regulatory defensibility.

Exception Remediation & Backlog Triage: Generates structured issue-attribution matrices aggregated by reporting entity and violation code, streamlining stakeholder accountability and root-cause remediation workflows.
## Architecture

```mermaid
flowchart TB
    subgraph SOURCES["Data Ingestion Layer"]
        S1["Authoritative Ground Truth<br/>(NYC PLUTO Socrata 64uk-42ks)"]
        S2["Untrusted Source Submissions<br/>(data/sample_records.csv)"]
    end

    S1 -->|"fetch_pluto.py<br/>Schema Extraction"| P1["Authoritative Baseline<br/>data/pluto_gfa.csv"]
    S2 --> G1
    P1 --> G1

    subgraph GATE["Automated Control Gate — scripts/qa_gate.py"]
        G1["Ingestion Preconditions<br/>File existence, schema validity, non-empty check"]
        G1 --> G2["Data Sanitization & Normalization<br/>Raw identifier preservation, type coercion"]
        G2 --> G3["Relational Join & Cross-Verification<br/>Left join on primary entity identifier"]
        
        G3 --> R1["Control R1: Identifier Integrity<br/>10-digit strict regex validation"]
        G3 --> R2["Control R2: Drift & Variance Threshold<br/>Tolerance check: |reported − truth| / truth > 10%"]
        G3 --> R3["Control R3: Operational Integrity<br/>Active status & telemetry bounds (EUI > 0)"]
        
        R1 --> ROUTE
        R2 --> ROUTE
        R3 --> ROUTE
        ROUTE{"Control Gate Decision"}
    end

    ROUTE -->|"Pass (All Controls)"| C1["output/clean_staging.csv<br/>Verified Ingestion Set"]
    ROUTE -->|"Fail (Any Violation)"| A1["output/audit_log.csv<br/>Immutable Forensic Evidence (UTC)"]
    A1 --> A2["output/backlog_summary.csv<br/>Entity × Risk Code Remediation Matrix"]

    classDef source fill:#e8f0fe,stroke:#1a73e8,color:#0b1f3a
    classDef gate   fill:#fff4e5,stroke:#e37400,color:#3d1f00
    classDef pass   fill:#e6f4ea,stroke:#188038,color:#0b2b14
    classDef fail   fill:#fce8e6,stroke:#c5221f,color:#3b0906

    class S1,S2,P1 source
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
