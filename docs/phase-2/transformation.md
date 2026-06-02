# Phase 2 — Transformation (Bronze → Silver)

**Project:** Canadian Political Contributions Analytics Platform (PFIN)
**Owner:** Faraz Eslami
**Status:** Complete
**Date:** 2026-06-01

---

## 1. Objective

Clean, type-cast, deduplicate, and normalize the flat Bronze table into four Silver domain tables in Unity Catalog. Silver is the first layer where data types are enforced, encoding is corrected, and the single source table is split into a star-schema-like structure for downstream consumption.

---

## 2. Source

| Property | Value |
|---|---|
| Table | `pfin_dev.bronze.elections_canada_contributions_raw` |
| Format | Delta |
| Rows | 284,136 |
| Columns | 29 (27 source + `_source_file` + `_ingested_at`) |
| Column types | All strings (no type assumptions at Bronze) |

---

## 3. Target Silver Tables

### 3.1 `pfin_dev.silver.recipients`

Grain: one row per unique `recipient_id`. Represents candidates, parties, EDAs, and other political entities that receive contributions.

| Column | Type | Notes |
|---|---|---|
| recipient_id | INT | Primary key (cast from source) |
| recipient_name | STRING | Full name of the recipient |
| recipient_last_name | STRING | Nullable — NULL for parties/associations |
| recipient_first_name | STRING | Nullable |
| recipient_middle_initial | STRING | Nullable (99% NULL) |
| political_entity | STRING | BOM-cleaned: Registered parties, Candidates, etc. |
| political_party | STRING | Encoding-fixed: Bloc Québécois, Parti Rhinocéros Party |
| electoral_district | STRING | Nullable — only populated for candidates |

Row count: **1,004**

### 3.2 `pfin_dev.silver.contributors`

Grain: one row per unique contributor, keyed on `SHA-256(last_name, first_name, postal_code)`.

| Column | Type | Notes |
|---|---|---|
| contributor_key | STRING | SHA-256 surrogate key (PK) |
| contributor_type | STRING | Always "Individuals" in current dataset |
| contributor_name | STRING | Full name (last, first middle) |
| contributor_last_name | STRING | |
| contributor_first_name | STRING | Nullable |
| contributor_middle_initial | STRING | Nullable (82% NULL) |
| contributor_city | STRING | Uppercased, trimmed, encoding-fixed |
| contributor_province | STRING | Standardized 2-letter code (36 variants → 13 codes + NULL) |
| contributor_postal_code | STRING | Uppercase, no spaces |

Row count: **123,453**

### 3.3 `pfin_dev.silver.electoral_events`

Grain: one row per unique `(electoral_event, fiscal_election_date)` combination.

| Column | Type | Notes |
|---|---|---|
| electoral_event_key | STRING | SHA-256 surrogate key (PK) |
| electoral_event | STRING | Nullable — "None" strings converted to NULL |
| fiscal_election_date | DATE | Cast from string (YYYY-MM-DD) |
| fiscal_year | INT | Derived from fiscal_election_date |

Row count: **44**

### 3.4 `pfin_dev.silver.contributions`

Grain: one row per individual contribution record (fact table).

| Column | Type | Notes |
|---|---|---|
| contribution_id | BIGINT | `monotonically_increasing_id()` |
| recipient_id | INT | FK → recipients |
| contributor_key | STRING | FK → contributors |
| electoral_event_key | STRING | FK → electoral_events |
| form_id | STRING | |
| financial_report | STRING | |
| part_number_of_return | STRING | |
| financial_report_part | STRING | |
| contribution_received_date | DATE | "0025" typo fixed → "2025"; NULLs preserved |
| monetary_amount | DECIMAL(12,2) | |
| non_monetary_amount | DECIMAL(12,2) | |
| total_amount | DECIMAL(12,2) | Derived: monetary + non_monetary |
| leadership_contestant | STRING | Nullable (85% NULL) |
| _source_file | STRING | Carried from Bronze |
| _ingested_at | TIMESTAMP | Carried from Bronze |
| _transformed_at | TIMESTAMP | Transformation timestamp |

Row count: **282,098**

---

## 4. Data Quality Rules Applied

### 4.1 Deduplication

- Method: `dropDuplicates()` on all 27 source columns (excluding `_source_file`, `_ingested_at`)
- Exact duplicates found and removed: **2,038**
- Remaining rows: 282,098

### 4.2 Encoding Fixes

The source CSV files contain French Canadian text that was double/triple-encoded through ISO-8859-1 → UTF-8 round-trips, producing garbled characters like `ÃÂ©` instead of `é`.

Fix applied: `decode(encode(col, "ISO-8859-1"), "UTF-8")` — two passes per column to handle both double and triple encoding, followed by stripping orphan `Â` characters.

Affected columns: `political_entity`, `recipient`, `recipient_last_name`, `recipient_first_name`, `political_party_of_recipient`, `electoral_district`, `electoral_event`, `contributor_name`, `contributor_last_name`, `contributor_first_name`, `contributor_city`, `contributor_postal_code`, `leadership_contestant`, `financial_report`.

### 4.3 BOM Stripping

`political_entity` had a UTF-8 BOM prefix (`ï»¿`) on two values originating from the first row of each CSV file. Stripped via regex, reducing 7 distinct values to 5.

### 4.4 Province Standardization

36 raw variants (trailing spaces, full names, typos, garbage) mapped to 13 standard two-letter codes. Unmappable values (e.g., `7`, `M4B 1N7`, `MI`) set to NULL.

| Raw Values | Standardized |
|---|---|
| AB, AB (space), Alberta, Alberta (space) | AB |
| BC, BC (space), British Columbia | BC |
| MB, MB (space) | MB |
| NB | NB |
| NL | NL |
| NS, NS (space) | NS |
| NT | NT |
| NU | NU |
| ON, ON (space), ONT, ONT., On, Ontario | ON |
| PE, PEI (space) | PE |
| QC, QC (space), aQC, Québec | QC |
| SK, SK (space), Saskatchewan | SK |
| YT | YT |
| 7, M4B 1N7, M6G 2T1, MI, None | NULL |

### 4.5 Date Handling

- `fiscal_election_date`: clean YYYY-MM-DD format, cast to DateType. No issues.
- `contribution_received_date`: one typo (`0025-04-07` → `2025-04-07`) fixed via regex. 914 NULLs preserved. Old dates (2015–2023) are legitimate — they represent contributions from prior years reported in 2025/2026 fiscal returns.

### 4.6 Monetary Amounts

- Cast to `DECIMAL(12,2)`. Values like `.23` (no leading zero) parse correctly.
- `non_monetary_amount`: all values are `.00` in current dataset.
- `total_amount`: derived as `COALESCE(monetary, 0) + COALESCE(non_monetary, 0)`.

### 4.7 Null Handling

- `"None"` strings in `electoral_event`, `contribution_given_through`, `leadership_contestant` → converted to NULL.
- `contribution_given_through`: 100% NULL across all rows — column dropped from Silver (not included in any Silver table).

---

## 5. Surrogate Key Design

### 5.1 Contributor Key

Natural key: `(contributor_last_name, contributor_first_name, contributor_postal_code)`.

- Middle initial excluded (82% NULL — would cause false splits).
- Generated via `SHA2(CONCAT_WS('|', UPPER(TRIM(last)), UPPER(TRIM(first)), UPPER(TRIM(postal))), 256)`.
- Trade-off: same person with different postal codes appears as two contributors. Acceptable for this dataset.

### 5.2 Electoral Event Key

Natural key: `(electoral_event, fiscal_election_date)`.

- Generated via `SHA2(CONCAT_WS('|', UPPER(TRIM(event)), date_string), 256)`.

---

## 6. Table Configuration

### 6.1 Liquid Clustering

Applied to `silver.contributions` on `contribution_received_date`. The three dimension tables are small enough (44–123K rows) that clustering provides no benefit.

### 6.2 Predictive Optimization

Enabled on all four Silver tables via `ALTER TABLE ... ENABLE PREDICTIVE OPTIMIZATION`.

---

## 7. Notebook

| Property | Value |
|---|---|
| Notebook | `02_transform_silver` |
| Repository path | `src/transformation/02_transform_silver.py` |
| Compute | Serverless (no UDFs, no cache, no sparkContext) |
| Idempotent | Yes — full overwrite on every run |
| Runtime | ~15 seconds |

---

## 8. Exit Criteria

| Criterion | Status |
|---|---|
| Silver tables created in `pfin_dev.silver` | ✅ |
| All columns correctly typed (dates, decimals, integers) | ✅ |
| No encoding artifacts in any text column | ✅ |
| Province codes standardized to 2-letter codes | ✅ |
| Exact duplicates removed (2,038) | ✅ |
| Surrogate keys generated for contributors and electoral events | ✅ |
| Liquid Clustering enabled on contributions | ✅ |
| Predictive Optimization enabled on all tables | ✅ |
| No nulls in primary key columns | ✅ |
| Row count validated: 282,098 = 284,136 − 2,038 | ✅ |
