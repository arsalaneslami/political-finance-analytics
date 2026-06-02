# PFIN — Phase 1: Data Ingestion (Landing → Bronze)

**Project:** Canadian Political Contributions Analytics Platform
**Phase:** 1 — Data Ingestion
**Owner:** Arsalan Eslami
**Status:** ✅ Complete
**Date:** 2026-06-01

---

## 1. Objective

Extract Elections Canada contribution records for 2025–2026 from source CSV files in the ADLS landing zone and load them into a Bronze Delta table in Unity Catalog. All columns are stored as strings — no type casting at this layer.

---

## 2. Source Files

| File | Size | Location |
|------|------|----------|
| `od_cntrbtn_de_e_2025.csv` | 87.18 MiB | `abfss://landing@pfincanadacentralsa.dfs.core.windows.net/od_cntrbtn_de_e_2025.csv` |
| `od_cntrbtn_de_e_2026.csv` | 6.85 MiB | `abfss://landing@pfincanadacentralsa.dfs.core.windows.net/od_cntrbtn_de_e_2026.csv` |

- **Encoding:** ISO-8859-1 (Latin-1) with UTF-8 BOM on the first column header
- **Format:** CSV with header row, comma-delimited
- **Upload method:** Azure Portal Storage Browser

---

## 3. Target Table

| Property | Value |
|----------|-------|
| Full name | `pfin_dev.bronze.elections_canada_contributions_raw` |
| Format | Delta |
| Write mode | Overwrite (idempotent) |
| Row count | 284,136 |
| Column count | 29 (27 source + 2 metadata) |

---

## 4. Schema — Bronze Table

All source columns are stored as `STRING`. Column names were cleaned from the original CSV headers (spaces → underscores, special characters removed, BOM stripped, lowercased).

| # | Column Name | Source Header |
|---|-------------|---------------|
| 1 | `political_entity` | Political Entity (with BOM prefix removed) |
| 2 | `recipient_id` | Recipient ID |
| 3 | `recipient` | Recipient |
| 4 | `recipient_last_name` | Recipient last name |
| 5 | `recipient_first_name` | Recipient first name |
| 6 | `recipient_middle_initial` | Recipient middle initial |
| 7 | `political_party_of_recipient` | Political Party of Recipient |
| 8 | `electoral_district` | Electoral District |
| 9 | `electoral_event` | Electoral event |
| 10 | `fiscal_election_date` | Fiscal/Election date |
| 11 | `form_id` | Form ID |
| 12 | `financial_report` | Financial Report |
| 13 | `part_number_of_return` | Part Number of Return |
| 14 | `financial_report_part` | Financial Report part |
| 15 | `contributor_type` | Contributor type |
| 16 | `contributor_name` | Contributor name |
| 17 | `contributor_last_name` | Contributor last name |
| 18 | `contributor_first_name` | Contributor first name |
| 19 | `contributor_middle_initial` | Contributor middle initial |
| 20 | `contributor_city` | Contributor City |
| 21 | `contributor_province` | Contributor Province |
| 22 | `contributor_postal_code` | Contributor Postal code |
| 23 | `contribution_received_date` | Contribution Received date |
| 24 | `monetary_amount` | Monetary amount |
| 25 | `non_monetary_amount` | Non-Monetary amount |
| 26 | `contribution_given_through` | Contribution given through |
| 27 | `leadership_contestant` | Leadership contestant |
| 28 | `_source_file` | _(metadata: `_metadata.file_path`)_ |
| 29 | `_ingested_at` | _(metadata: `current_timestamp()`)_ |

---

## 5. Column Name Cleaning Logic

The source CSV headers contain spaces, slashes, hyphens, and a UTF-8 BOM prefix on the first column. A Python cleaning function handles all cases:

```python
import re

def clean_col_name(name):
    # Decode BOM: source is ISO-8859-1 but first header has UTF-8 BOM bytes
    name = name.encode("iso-8859-1").decode("utf-8", errors="ignore")
    # Remove any remaining non-ASCII characters
    name = re.sub(r'[^\x00-\x7F]+', '', name)
    name = name.strip()
    # Replace spaces, slashes, and special characters with underscores
    name = re.sub(r'[ ,;{}()\n\t=\/]+', '_', name)
    # Handle hyphens separately
    name = name.replace('-', '_')
    name = name.strip('_').lower()
    return name
```

---

## 6. Notebook — `01_ingest_bronze`

**Location:** `src/ingestion/01_ingest_bronze.py`
**Compute:** Serverless (Standard 16 GB, Python 3.12)

```python
# ============================================================
# PFIN | Phase 1 | Bronze Ingestion
# Notebook:  01_ingest_bronze
# Source:    landing container (ADLS Gen2)
# Target:    pfin_dev.bronze.elections_canada_contributions_raw
# ============================================================

import re
from pyspark.sql import functions as F
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────
STORAGE_ACCOUNT = "pfincanadacentralsa"
LANDING_BASE    = f"abfss://landing@{STORAGE_ACCOUNT}.dfs.core.windows.net"
TARGET_CATALOG  = "pfin_dev"
TARGET_SCHEMA   = "bronze"
TARGET_TABLE    = "elections_canada_contributions_raw"
FULL_TABLE_NAME = f"{TARGET_CATALOG}.{TARGET_SCHEMA}.{TARGET_TABLE}"

SOURCE_FILES = [
    f"{LANDING_BASE}/od_cntrbtn_de_e_2025.csv",
    f"{LANDING_BASE}/od_cntrbtn_de_e_2026.csv",
]

# ── READ ─────────────────────────────────────────────────────
df_raw = (
    spark.read
    .option("header", "true")
    .option("encoding", "iso-8859-1")
    .option("inferSchema", "false")    # Bronze: all columns as strings
    .option("multiLine", "false")
    .csv(SOURCE_FILES)
)

# ── CLEAN COLUMN NAMES ───────────────────────────────────────
def clean_col_name(name):
    name = name.encode("iso-8859-1").decode("utf-8", errors="ignore")
    name = re.sub(r'[^\x00-\x7F]+', '', name)
    name = name.strip()
    name = re.sub(r'[ ,;{}()\n\t=\/]+', '_', name)
    name = name.replace('-', '_')
    name = name.strip('_').lower()
    return name

cleaned_cols = [clean_col_name(c) for c in df_raw.columns]
print("Cleaned columns:", cleaned_cols)

# ── ADD METADATA COLUMNS ─────────────────────────────────────
df_bronze = (
    df_raw.toDF(*cleaned_cols)
    .withColumn("_source_file", F.col("_metadata.file_path"))
    .withColumn("_ingested_at", F.current_timestamp())
)

# ── WRITE TO DELTA ───────────────────────────────────────────
(
    df_bronze.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(FULL_TABLE_NAME)
)

# ── VALIDATE ─────────────────────────────────────────────────
row_count = spark.table(FULL_TABLE_NAME).count()
col_count = len(spark.table(FULL_TABLE_NAME).columns)

print(f"✅ Table : {FULL_TABLE_NAME}")
print(f"   Rows  : {row_count:,}")
print(f"   Cols  : {col_count}")
print(f"   Done  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
```

---

## 7. Infrastructure Changes During Phase 1

### 7.1 External Location — Recreated

The original external location `pfin_lakehouse` pointed to `abfss://landing@pfincanadacentralsa.dfs.core.windows.net/landing` which blocked access to files at the container root. It was dropped (with `FORCE` due to dependent catalog) and recreated:

```sql
DROP EXTERNAL LOCATION pfin_lakehouse FORCE;

CREATE EXTERNAL LOCATION pfin_lakehouse
URL 'abfss://landing@pfincanadacentralsa.dfs.core.windows.net/'
WITH (STORAGE CREDENTIAL pfin_storage_cred)
COMMENT 'External location for PFIN project — provides Unity Catalog access to ADLS Gen2 storage account pfincanadacentralsa';
```

**New URL:** `abfss://landing@pfincanadacentralsa.dfs.core.windows.net/` (container root)

### 7.2 External Volume — Recreated

The volume `pfin_dev.landing.zone` was dropped and recreated at a non-conflicting path to avoid overlap with Unity Catalog managed storage under `__unitystorage`:

```sql
DROP VOLUME IF EXISTS pfin_dev.landing.zone;

CREATE EXTERNAL VOLUME pfin_dev.landing.zone
LOCATION 'abfss://landing@pfincanadacentralsa.dfs.core.windows.net/raw/'
COMMENT 'Landing zone volume for raw source file drops';
```

**New location:** `/raw/` instead of `/landing/` to avoid overlap with `__unitystorage` directory.

### 7.3 Known Issue — Catalog Managed Storage

The `pfin_dev` catalog was created with the `landing` container as its managed storage location. Unity Catalog stores internal data at `/landing/__unitystorage/`. This is not ideal — the `landing` container should only hold raw source files. Documented as Phase 0 technical debt for future resolution.

---

## 8. Compute Configuration

| Property | Value |
|----------|-------|
| Type | Serverless |
| Memory | Standard (16 GB) |
| Python | 3.12 |
| Dependencies | None (built-in PySpark) |

**Note:** Serverless compute requires Unity Catalog external locations for ADLS access. Direct `abfss://` access via access keys is not supported on serverless — the `pfin_storage_cred` storage credential and `pfin_lakehouse` external location must be properly configured.

---

## 9. Exit Criteria

| Criterion | Status |
|-----------|--------|
| CSV files uploaded to ADLS landing zone | ✅ |
| Bronze Delta table created in Unity Catalog | ✅ |
| All columns stored as strings | ✅ |
| Metadata columns (`_source_file`, `_ingested_at`) added | ✅ |
| Row count validated: 284,136 | ✅ |
| Column count validated: 29 | ✅ |
| Notebook committed to repo: `src/ingestion/01_ingest_bronze.py` | ⬜ Pending |
| CSV files moved to proper folder structure | ⬜ Deferred |

---

## 10. Deferred Items

| Item | Reason | Target Phase |
|------|--------|--------------|
| Move CSV files to `raw/elections_canada/contributions/` | Quick path taken for Phase 1 | Phase 1 cleanup |
| Fix `pfin_dev` catalog managed storage location | Requires catalog recreation | Phase 4+ |
| Unity Catalog tags on external location | `ALTER EXTERNAL LOCATION SET TAGS` not supported | N/A — limitation |
| Auto Loader pipeline for incremental ingestion | Batch overwrite sufficient for Phase 1 | Phase 4+ |

---

## 11. Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| v1.0 | 2026-06-01 | Arsalan Eslami | Initial Phase 1 documentation |
