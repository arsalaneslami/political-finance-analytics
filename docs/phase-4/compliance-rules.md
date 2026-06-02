# PFIN — Phase 4: Political Finance Analytics Rules

**Project:** Canadian Political Contributions Analytics Platform  
**Abbreviation:** pfin  
**Phase:** 4 — Political Finance Analytics Rules  
**Version:** 1.0  
**Date:** June 2026  
**Owner:** Arsalan Eslami  
**Notebook:** `src/rules/04_compliance_rules.py`  
**Source:** `pfin_dev.silver.{contributions, contributors, recipients, electoral_events}`  
**Target:** `pfin_dev.gold.compliance_flags`, `pfin_dev.gold.eo_disclosure_list`

---

## 1. Purpose and Scope

Phase 4 defines and encodes domain-specific compliance and analytics rules on top of the Silver domain tables. The output is two new Gold tables:

- `compliance_flags` — all donor-year combinations with all rule flags applied
- `eo_disclosure_list` — export-ready list of donors meeting the Elections Ontario disclosure threshold

These rules are based on Ontario provincial political finance law applicable to the 2025–2026 fiscal period. All column names follow the PFIN snake_case naming convention.

---

## 2. Source Column Mapping

| Concept | Silver Table | Silver Column Name | Type |
|---|---|---|---|
| Donor identifier | contributors | `contributor_key` | STRING |
| Donor full name | contributors | `contributor_name` | STRING |
| Donor first name | contributors | `contributor_first_name` | STRING |
| Donor last name | contributors | `contributor_last_name` | STRING |
| Donor type | contributors | `contributor_type` | STRING |
| Donor city | contributors | `contributor_city` | STRING |
| Donor province | contributors | `contributor_province` | STRING |
| Donor postal code | contributors | `contributor_postal_code` | STRING |
| Donation monetary amount | contributions | `monetary_amount` | DECIMAL(12,2) |
| Donation non-monetary | contributions | `non_monetary_amount` | DECIMAL(12,2) |
| Donation total amount | contributions | `total_amount` | DECIMAL(12,2) |
| Donation date | contributions | `contribution_received_date` | DATE |
| Fiscal year | electoral_events | `fiscal_year` | INT |
| Recipient party | recipients | `political_party` | STRING |
| Electoral district | recipients | `electoral_district` | STRING |

---

## 3. Contribution Cap Rules

Ontario law sets a maximum total contribution limit per donor per fiscal year. The cap applies to the sum of all `monetary_amount` values grouped by `contributor_key` and `fiscal_year`.

### 3.1 Cap Definition

| Parameter | Value |
|---|---|
| Maximum allowed per donor per year | $3,425.00 |
| Grouping key | `contributor_key` + `fiscal_year` |
| Amount column used | `monetary_amount` |
| Aggregated column name (Gold) | `total_donated_amount` |

### 3.2 Cap Status Levels

| `cap_status` Value | Condition | Meaning |
|---|---|---|
| `over_cap` | `total_donated_amount` > 3425.00 | Compliance violation. Refund required. |
| `at_cap` | `total_donated_amount` = 3425.00 | At legal maximum. Cannot donate again. |
| `approaching_cap` | `total_donated_amount` >= 3000.00 AND < 3425.00 | Approaching limit. Monitor this donor. |
| `under_cap` | `total_donated_amount` < 3000.00 | Normal. No action required. |

### 3.3 Refund Calculation

| Column Name | Formula | Description |
|---|---|---|
| `refund_amount` | `GREATEST(total_donated_amount - 3425.00, 0)` | Amount to be returned to the donor |
| `total_refund_exposure` | `SUM(refund_amount)` across all `over_cap` donors | Total financial exposure for the campaign |

> **Example:** `contributor_name = Harminder Bains`, `total_donated_amount = 19900.00` → `refund_amount = 16475.00`

---

## 4. Elections Ontario Disclosure Rules

Any donor whose total monetary contributions exceed $200 in a fiscal year must be reported to Elections Ontario. This rule is independent of the $3,425 cap — both rules apply simultaneously.

| Parameter | Value |
|---|---|
| Disclosure threshold | $200 total `monetary_amount` per donor per fiscal year |
| Grouping key | `contributor_key` + `fiscal_year` |
| Output Gold table | `pfin_dev.gold.eo_disclosure_list` |
| Flag column name | `is_eo_reportable` |
| Flag type | BOOLEAN |

> `is_eo_reportable = TRUE` when `total_donated_amount > 200.00` for that `contributor_key` + `fiscal_year` combination.

---

## 5. Identity Detection and Eligibility Rules

| Rule Name | Detection Logic | Silver Columns Used | Flag Column | Severity |
|---|---|---|---|---|
| Non-Ontario donor | `contributor_province != 'ON'` (case-insensitive). Blank = unknown, do not flag. | `contributor_province` | `is_non_ontario` | Medium |
| Province unknown | `contributor_province` IS NULL or empty. Tracked separately from non-Ontario. | `contributor_province` | `is_province_unknown` | Low |
| Missing donor name | Both `contributor_first_name` AND `contributor_last_name` are NULL or empty. | `contributor_first_name`, `contributor_last_name` | `is_missing_name` | High |
| Shared address, different names | `contributor_postal_code` + `contributor_city` match but `contributor_name` differs across rows. | `contributor_postal_code`, `contributor_city`, `contributor_name` | `is_shared_address` | Low — common for families |

> **Note:** Credit card detection is not possible in PFIN — the source data does not include payment card details.

---

## 6. Additional Enhancement Rules

| Rule | Logic | Rationale |
|---|---|---|
| Structuring pattern | `contribution_count > 10` AND `avg_contribution_amount < 50.00` | Breaking one large donation into many small ones to avoid detection |
| Multi-recipient donor | `distinct_recipients >= 3` in one fiscal year | Highly active donors who may warrant closer review |
| Year-over-year cap tracking | Group by `contributor_key` across `fiscal_year` to detect donors who always approach or reach the cap | Useful for compliance trend analysis across 2025 and 2026 |
| Province unknown | `contributor_province` IS NULL — tracked separately as `is_province_unknown` | Blank province should not be flagged as non-Ontario but tracked for data completeness |

---

## 7. Gold Output Tables

### 7.1 compliance_flags

**Table:** `pfin_dev.gold.compliance_flags`  
**Grain:** One row per `contributor_key` + `fiscal_year`  
**Cluster keys:** `fiscal_year`, `cap_status`

| Column Name | Type | Description |
|---|---|---|
| `contributor_key` | STRING | FK to silver.contributors |
| `contributor_name` | STRING | Full donor name |
| `contributor_type` | STRING | Individual, Business, etc. |
| `contributor_province` | STRING | Standardized 2-letter province code |
| `contributor_postal_code` | STRING | Formatted postal code |
| `contributor_city` | STRING | City |
| `fiscal_year` | INT | Fiscal/election year |
| `total_donated_amount` | DECIMAL(14,2) | Sum of monetary_amount for this donor + year |
| `contribution_count` | BIGINT | Number of individual contributions |
| `avg_contribution_amount` | DECIMAL(14,2) | Average contribution amount |
| `distinct_recipients` | BIGINT | Number of distinct recipients donated to |
| `cap_status` | STRING | over_cap / at_cap / approaching_cap / under_cap |
| `refund_amount` | DECIMAL(14,2) | Amount to refund if over_cap, else 0.00 |
| `is_eo_reportable` | BOOLEAN | TRUE if total_donated_amount > 200.00 |
| `is_non_ontario` | BOOLEAN | TRUE if contributor_province != ON |
| `is_province_unknown` | BOOLEAN | TRUE if contributor_province is NULL or empty |
| `is_shared_address` | BOOLEAN | TRUE if address shared with a different contributor_name |
| `is_missing_name` | BOOLEAN | TRUE if both first and last name are NULL or empty |
| `is_structuring_pattern` | BOOLEAN | TRUE if contribution_count > 10 AND avg < $50 |
| `is_multi_recipient` | BOOLEAN | TRUE if distinct_recipients >= 3 |
| `_aggregated_at` | TIMESTAMP | When this row was computed |

### 7.2 eo_disclosure_list

**Table:** `pfin_dev.gold.eo_disclosure_list`  
**Grain:** One row per `contributor_key` + `fiscal_year` where `is_eo_reportable = TRUE`  
**Cluster keys:** `fiscal_year`

| Column Name | Type | Description |
|---|---|---|
| `contributor_key` | STRING | FK to silver.contributors |
| `contributor_last_name` | STRING | Donor last name |
| `contributor_type` | STRING | Individual, Business, etc. |
| `contributor_city` | STRING | City |
| `contributor_province` | STRING | Province code |
| `contributor_postal_code` | STRING | Postal code |
| `fiscal_year` | INT | Fiscal/election year |
| `total_donated_amount` | DECIMAL(14,2) | Total donated in this fiscal year |
| `is_eo_reportable` | BOOLEAN | Always TRUE in this table |
| `cap_status` | STRING | Cap level for reference |
| `_aggregated_at` | TIMESTAMP | When this row was computed |

---

## 8. Flag Priority Summary

| Priority | Flag / Condition | Column | Color |
|---|---|---|---|
| 1 — Highest | `cap_status = over_cap` | `cap_status` | Red |
| 2 | `is_missing_name = TRUE` | `is_missing_name` | Red |
| 3 | `cap_status = at_cap` | `cap_status` | Orange |
| 4 | `cap_status = approaching_cap` | `cap_status` | Yellow |
| 5 | `is_non_ontario = TRUE` | `is_non_ontario` | Pink |
| 6 | `is_shared_address = TRUE` | `is_shared_address` | Light Yellow |
| 7 | `is_eo_reportable = TRUE` | `is_eo_reportable` | Blue (info) |

---

## 9. Pipeline Configuration

| Item | Value |
|---|---|
| Notebook path | `src/rules/04_compliance_rules.py` |
| Lakeflow Job name | `pfin-dev-compliance-rules` |
| Write mode | Overwrite (full rebuild) |
| Depends on | `pfin-dev-silver-gold` (Phase 3 must complete first) |
| Target tables | `pfin_dev.gold.compliance_flags`, `pfin_dev.gold.eo_disclosure_list` |

---

## 10. Exit Criteria

| # | Criterion | Verification |
|---|---|---|
| 1 | `compliance_flags` populated | `SELECT COUNT(*) > 0` |
| 2 | `eo_disclosure_list` populated | `SELECT COUNT(*) > 0` |
| 3 | All `over_cap` donors have `refund_amount > 0` | `SELECT COUNT(*) WHERE cap_status = 'over_cap' AND refund_amount <= 0 = 0` |
| 4 | No donor in `eo_disclosure_list` with `total_donated_amount <= 200` | `SELECT COUNT(*) WHERE total_donated_amount <= 200 = 0` |
| 5 | Notebook committed to Git | `src/rules/04_compliance_rules.py` in develop branch |
| 6 | Documentation committed | `docs/phase-4/compliance-rules.md` in develop branch |

---

## 11. Document Control

| Date | Version | Change | Author |
|---|---|---|---|
| 2026-06-01 | 1.0 | Initial Phase 4 analytics rules documentation | Arsalan Eslami |
