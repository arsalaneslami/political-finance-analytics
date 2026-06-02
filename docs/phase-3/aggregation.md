# PFIN — Phase 3: Aggregation (Gold)

**Project:** Canadian Political Contributions Analytics Platform  
**Abbreviation:** pfin  
**Phase:** 3 — Aggregation (Gold)  
**Version:** 1.0  
**Date:** June 2026  
**Owner:** Arsalan Eslami  
**Notebook:** `src/aggregation/03_aggregate_gold.py`  
**Source:** `pfin_dev.silver.{contributions, contributors, recipients, electoral_events}`  
**Target:** `pfin_dev.gold.{contributions_by_party, contributions_by_district, contributions_by_contributor_type, contributions_by_year, top_contributors}`

---

## 1. Purpose and Scope

Phase 3 builds the Gold layer by aggregating cleaned Silver domain tables into business-oriented tables optimized for analytical queries and downstream dashboards. No dashboard work is done in this phase — that is Phase 5.

Phase 3 starts only after Phase 2 exit criteria are met: all four Silver tables populated and validated.

---

## 2. Source Tables (Silver)

| Table | Grain | Key Column(s) |
|---|---|---|
| `contributions` | One row per contribution record | `contribution_id` |
| `contributors` | One row per unique contributor | `contributor_key` |
| `recipients` | One row per unique recipient | `recipient_id` |
| `electoral_events` | One row per electoral event + fiscal date | `electoral_event_key` |

**Validated row counts (Phase 2 output):**

| Table | Row Count |
|---|---|
| `silver.contributions` | 282,098 |
| `silver.contributors` | 123,451 |
| `silver.recipients` | 1,004 |
| `silver.electoral_events` | 44 |

---

## 3. Gold Table Definitions

All Gold tables are written as managed Delta tables in `pfin_dev.gold`.

### 3.1 contributions_by_party

**Grain:** One row per `political_party` + `fiscal_year`  
**Cluster keys:** `fiscal_year`, `political_party`  
**Row count:** 17

| Column Name | Type | Description |
|---|---|---|
| `political_party` | STRING | Political party name (from recipients) |
| `fiscal_year` | INT | Fiscal/election year |
| `total_monetary` | DECIMAL(14,2) | Sum of monetary contributions |
| `total_non_monetary` | DECIMAL(14,2) | Sum of non-monetary contributions |
| `total_amount` | DECIMAL(14,2) | Sum of total contributions |
| `contribution_count` | BIGINT | Number of contribution records |
| `unique_contributors` | BIGINT | Count of distinct contributor_key values |
| `avg_contribution` | DECIMAL(14,2) | Average contribution amount |
| `_aggregated_at` | TIMESTAMP | When this row was computed |

### 3.2 contributions_by_district

**Grain:** One row per `electoral_district` + `fiscal_year` + `political_party`  
**Cluster keys:** `fiscal_year`, `electoral_district`  
**Row count:** 893

| Column Name | Type | Description |
|---|---|---|
| `electoral_district` | STRING | Electoral district name (from recipients) |
| `fiscal_year` | INT | Fiscal/election year |
| `political_party` | STRING | Political party name |
| `total_monetary` | DECIMAL(14,2) | Sum of monetary contributions |
| `total_amount` | DECIMAL(14,2) | Sum of total contributions |
| `contribution_count` | BIGINT | Number of contribution records |
| `unique_contributors` | BIGINT | Count of distinct contributor_key values |
| `_aggregated_at` | TIMESTAMP | When this row was computed |

### 3.3 contributions_by_contributor_type

**Grain:** One row per `contributor_type` + `fiscal_year`  
**Cluster keys:** `fiscal_year`, `contributor_type`  
**Row count:** 2

| Column Name | Type | Description |
|---|---|---|
| `contributor_type` | STRING | Type: Individuals, Businesses, etc. |
| `fiscal_year` | INT | Fiscal/election year |
| `total_monetary` | DECIMAL(14,2) | Sum of monetary contributions |
| `total_amount` | DECIMAL(14,2) | Sum of total contributions |
| `contribution_count` | BIGINT | Number of contribution records |
| `unique_contributors` | BIGINT | Count of distinct contributor_key values |
| `pct_of_total_amount` | DECIMAL(5,2) | Percentage of total contributions in that year |
| `_aggregated_at` | TIMESTAMP | When this row was computed |

### 3.4 contributions_by_year

**Grain:** One row per `fiscal_year`  
**Cluster keys:** `fiscal_year`  
**Row count:** 2

| Column Name | Type | Description |
|---|---|---|
| `fiscal_year` | INT | Fiscal/election year |
| `total_monetary` | DECIMAL(14,2) | Sum of monetary contributions |
| `total_non_monetary` | DECIMAL(14,2) | Sum of non-monetary contributions |
| `total_amount` | DECIMAL(14,2) | Sum of total contributions |
| `contribution_count` | BIGINT | Number of contribution records |
| `unique_contributors` | BIGINT | Count of distinct contributor_key values |
| `unique_recipients` | BIGINT | Count of distinct recipient_id values |
| `avg_contribution` | DECIMAL(14,2) | Average contribution amount |
| `median_contribution` | DECIMAL(14,2) | Median contribution amount (percentile_approx) |
| `_aggregated_at` | TIMESTAMP | When this row was computed |

### 3.5 top_contributors

**Grain:** One row per `contributor_key` + `fiscal_year`, top 100 per year  
**Cluster keys:** `fiscal_year`, `rank_in_year`  
**Row count:** 229

| Column Name | Type | Description |
|---|---|---|
| `contributor_key` | STRING | FK to silver.contributors |
| `contributor_name` | STRING | Full contributor name |
| `contributor_type` | STRING | Individual, Business, etc. |
| `contributor_province` | STRING | Province code |
| `fiscal_year` | INT | Fiscal/election year |
| `total_monetary` | DECIMAL(14,2) | Sum of monetary contributions |
| `total_amount` | DECIMAL(14,2) | Sum of total contributions |
| `contribution_count` | BIGINT | Number of contributions made |
| `parties_contributed_to` | STRING | Comma-separated list of parties donated to |
| `rank_in_year` | INT | Rank by total_amount within fiscal_year (row_number) |
| `_aggregated_at` | TIMESTAMP | When this row was computed |

---

## 4. Join Strategy

All Gold tables use `silver.contributions` as the fact table and join dimension tables as needed.

| Gold Table | Joins Required |
|---|---|
| `contributions_by_party` | contributions → recipients ON `recipient_id` → electoral_events ON `electoral_event_key` |
| `contributions_by_district` | contributions → recipients ON `recipient_id` → electoral_events ON `electoral_event_key` |
| `contributions_by_contributor_type` | contributions → contributors ON `contributor_key` → electoral_events ON `electoral_event_key` |
| `contributions_by_year` | contributions → electoral_events ON `electoral_event_key` |
| `top_contributors` | contributions → contributors ON `contributor_key` → recipients ON `recipient_id` → electoral_events ON `electoral_event_key` |

---

## 5. Pipeline Configuration

| Item | Value |
|---|---|
| Notebook path | `src/aggregation/03_aggregate_gold.py` |
| Lakeflow Job name (dev) | `pfin-dev-silver-gold` |
| Lakeflow Job name (prod) | `pfin-prod-silver-gold` |
| Write mode | Overwrite (full rebuild each run) |
| Compute | Serverless or `pfin-dev-interactive` |
| Schedule (prod) | Daily or on Silver pipeline completion |
| Source catalog | `pfin_dev` (dev) / `pfin_prod` (prod) |
| Target schema | `gold` |

Full rebuild is appropriate for the current data volume (~282K Silver rows). Switch to incremental merge if data grows significantly.

---

## 6. Liquid Clustering

| Gold Table | Cluster Keys |
|---|---|
| `contributions_by_party` | `fiscal_year`, `political_party` |
| `contributions_by_district` | `fiscal_year`, `electoral_district` |
| `contributions_by_contributor_type` | `fiscal_year`, `contributor_type` |
| `contributions_by_year` | `fiscal_year` |
| `top_contributors` | `fiscal_year`, `rank_in_year` |

Predictive Optimization is enabled on all Gold tables.

---

## 7. Data Quality Checks

| Check | Rule | Action on Failure |
|---|---|---|
| Row count > 0 | Every Gold table must have at least 1 row | Fail pipeline |
| No NULL keys | Group-by columns must not be NULL | Fail pipeline |
| Amount consistency | `SUM(contributions_by_party.total_amount)` per year = `contributions_by_year.total_amount` | Warn + log |
| Top contributors rank uniqueness | No duplicate `rank_in_year` per `fiscal_year` | Fail pipeline |

DQ results are written to `pfin_dev.ops.data_quality_log` after each run.

> **Fix applied:** `F.rank()` replaced with `F.row_number()` in `top_contributors` to guarantee unique ranks when total amounts are tied.

---

## 8. Exit Criteria

| # | Criterion | Verification |
|---|---|---|
| 1 | All five Gold tables populated in `pfin_dev.gold` | `SELECT COUNT(*) FROM each table > 0` |
| 2 | Data quality checks pass | DQ notebook runs green |
| 3 | Liquid Clustering applied | `DESCRIBE DETAIL` shows cluster columns |
| 4 | Predictive Optimization enabled | `ALTER TABLE ... ENABLE PREDICTIVE OPTIMIZATION` confirmed |
| 5 | Notebook committed to Git | `src/aggregation/03_aggregate_gold.py` in develop branch |
| 6 | Documentation committed | `docs/phase-3/aggregation.md` in develop branch |
| 7 | Lakeflow Job configured | `pfin-dev-silver-gold` job runs successfully |

---

## 9. Risks and Considerations

| Risk | Impact | Mitigation |
|---|---|---|
| Silver data quality issues surface in Gold | Incorrect aggregations | Run Phase 2 DQ checks before Gold build |
| Contributor dedup imperfect (SHA-256 key) | Inflated `unique_contributors` counts | Accept for now; refine in Phase 4 analytics rules |
| `median_contribution` requires sorting | Slow on large data | Uses `percentile_approx` for performance |
| Overwrite mode loses history | No point-in-time comparison | Acceptable for 2025–2026 scope |

---

## 10. Document Control

| Date | Version | Change | Author |
|---|---|---|---|
| 2026-06-01 | 1.0 | Initial Phase 3 aggregation documentation | Arsalan Eslami |
