# PFIN — Phase 5: Dashboards & Reporting

**Project:** Canadian Political Contributions Analytics Platform
**Abbreviation:** pfin
**Version:** 1.0
**Date:** June 2026
**Owner:** Arsalan Eslami

---

## 1. Purpose and Scope

Phase 5 delivers the reporting and visualization layer of the PFIN platform. It builds Databricks AI/BI Dashboards connected to Gold and Silver Delta tables, configures Entra-based access so external viewers see only dashboards without workspace exposure, and establishes a compliance reporting framework based on Elections Canada contribution limits.

---

## 2. Prerequisites

Phase 5 depends on the successful completion of:

| Phase | Dependency |
|---|---|
| Phase 0 | Azure resources, Databricks workspace, Unity Catalog, Entra groups |
| Phase 1 | Bronze Delta table populated |
| Phase 2 | Silver domain tables (contributions, contributors, recipients, electoral_events) |
| Phase 3 | Gold aggregation tables (5 tables in pfin_dev.gold) |

---

## 3. Infrastructure

### 3.1 SQL Warehouse

| Setting | Value |
|---|---|
| Name | Serverless Starter Warehouse |
| Size | Small |
| Type | Serverless |
| Purpose | Executes all dashboard queries |
| Access | Publisher credential (Arsalan Eslami) |

### 3.2 Dashboard

| Setting | Value |
|---|---|
| Dashboard Name | PFIN - Political Contributions Analytics |
| Workspace URL | https://adb-7405606204960019.19.azuredatabricks.net |
| Pages | 7 |
| Datasets | 27 |
| Global Filter | Fiscal Year (multi-select, linked to all datasets) |
| Publish Mode | Share data permission (default) — queries run as publisher |

---

## 4. Dashboard Pages

### 4.1 Page 1 — Canadian Political Contributions — Overview

Summary-level view of contributions across parties, districts, and key metrics.

| Visualization | Type | Dataset | Key Fields |
|---|---|---|---|
| Total Amount Contributed | Counter | by_year | total_amount |
| Contribution Count | Counter | by_year | contribution_count |
| Unique Contributors | Counter | by_year | unique_contributors |
| Average Contribution | Counter | by_year | avg_contribution |
| Party Contribution Leaders | Bar chart | by_party | political_party, total_amount |
| Top 20 Electoral Districts | Bar chart | by_district | electoral_district, total_amount |

### 4.2 Page 2 — Contributor Insights

Contributor-level analysis including geographic distribution, contribution size patterns, and multi-party donors.

| Visualization | Type | Dataset | Key Fields |
|---|---|---|---|
| Contributions by Province | Pie/Donut | province_summary | contributor_province, total_amount |
| Contribution Size Distribution | Bar chart | contribution_distribution | amount_range, contribution_count |
| Top 100 Contributors | Table | top_contributors | rank_in_year, contributor_name, total_amount |
| Multi-Party Donors | Table | multi_party_donors | contributor_name, parties_contributed_to |

### 4.3 Page 3 — Anomaly & Trend Analysis

Year-over-year comparison and anomaly detection across districts.

| Visualization | Type | Dataset | Key Fields |
|---|---|---|---|
| Year-over-Year Party Comparison | Grouped bar | party_year_comparison | political_party, total_amount, fiscal_year |
| District Anomaly Detection | Table (conditional formatting) | top_districts_anomaly | electoral_district, avg_per_contributor, anomaly_flag |
| Anomaly Distribution Curve | Area chart | anomaly_distribution | avg_bucket, district_count, anomaly_count |

Anomaly flags: "High Avg" (red) when avg contribution per contributor exceeds $1,500; "Single Donor" (amber) when one contributor accounts for over $1,000 in a district.

### 4.4 Page 4 — Geographic Deep Dive

Provincial-level analysis with party breakdown and scatter analysis.

| Visualization | Type | Dataset | Key Fields |
|---|---|---|---|
| Top 10 Provinces by Contributions | Horizontal bar | province_top10 | province, total_amount |
| Province × Party Breakdown | Heatmap | province_by_party | province, political_party, total_amount |
| Avg Contribution vs Donor Count | Scatter | province_top10 | unique_contributors, avg_contribution, province |

### 4.5 Page 5 — Party Deep Dive

Party-level funding composition and donor behavior.

| Visualization | Type | Dataset | Key Fields |
|---|---|---|---|
| Monetary vs Non-Monetary by Party | Stacked bar | party_monetary_split | political_party, monetary, non_monetary |
| Non-Monetary Contribution Share | Horizontal bar | non_monetary_pct | political_party, non_monetary_pct |
| Avg Contribution vs Donor Count | Scatter | party_avg_vs_count | unique_contributors, avg_contribution, political_party |
| Total vs Average per Party | Combo (bar + line) | party_avg_vs_count | political_party, total_amount, avg_contribution |

### 4.6 Page 6 — Contributor Behavior

Donor frequency patterns and landscape analysis.

| Visualization | Type | Dataset | Key Fields |
|---|---|---|---|
| One-Time vs Repeat Donors | Pie | repeat_vs_new | donor_type, donor_count |
| Donor Frequency Distribution | Bar chart | contributor_frequency | contribution_count_bucket, contributor_count |
| Contributor Landscape | Scatter | contributor_scatter | num_contributions, total_contributed, province |

### 4.7 Page 7 — Compliance & Anomaly Reports

Regulatory compliance checks based on Elections Canada federal contribution limits.

| Visualization | Type | Dataset | Key Fields |
|---|---|---|---|
| Over-Limit Counter Cards | Counters | over_limit_contributors | count, max amount_over_limit, sum amount_over_limit |
| Contributors Exceeding Annual Limit | Table | over_limit_contributors | contributor_name, political_party, total_contributed, amount_over_limit |
| Single Contributions Exceeding Limit | Table | large_single_contributions | contributor_name, political_party, total_amount, contribution_received_date |
| High-Value Contributors Across Parties | Table | high_total_across_parties | contributor_name, grand_total, parties_count, parties_list |
| Frequent Small Donations | Table | frequent_small_donations | contributor_name, num_contributions, avg_per_contribution |
| Large Donors with Missing Information | Table | missing_data_large_donors | contributor_name, missing_field, total_contributed |

---

## 5. Datasets

### 5.1 Gold-Layer Datasets (1–11)

| # | Name | Source | Description |
|---|---|---|---|
| 1 | by_party | pfin_dev.gold.contributions_by_party | Contributions aggregated by political party |
| 2 | by_year | pfin_dev.gold.contributions_by_year | Annual contribution summary |
| 3 | by_district | pfin_dev.gold.contributions_by_district | Top 20 districts (excl. National/No District) |
| 4 | by_contributor_type | pfin_dev.gold.contributions_by_contributor_type | Breakdown by contributor type (Individuals only for 2025–2026) |
| 5 | top_contributors | pfin_dev.gold.top_contributors | Top 100 contributors per fiscal year |
| 6 | party_share | pfin_dev.gold.contributions_by_party | Party percentage share of total contributions |
| 7 | province_summary | pfin_dev.gold.top_contributors | Province-level aggregation from top contributors |
| 8 | multi_party_donors | pfin_dev.gold.top_contributors | Contributors who donated to 2+ parties |
| 9 | contribution_distribution | pfin_dev.silver (joined) | Contribution size buckets ($200 intervals) |
| 10 | party_year_comparison | pfin_dev.gold.contributions_by_party | Both years side-by-side (no fiscal year filter) |
| 11 | top_districts_anomaly | pfin_dev.gold.contributions_by_district | District anomaly flags (High Avg, Single Donor) |

### 5.2 Silver-Layer Datasets (12–22)

| # | Name | Source Tables | Description |
|---|---|---|---|
| 12 | contribution_curve | contributions, electoral_events | Fine-grained distribution ($200 buckets) |
| 13 | province_by_party | contributions, contributors, recipients, electoral_events | Province × party contribution matrix |
| 14 | province_top10 | contributions, contributors, electoral_events | Top 10 provinces by total contributions |
| 15 | party_province_matrix | contributions, contributors, recipients, electoral_events | Party × province totals for heatmap |
| 16 | party_monetary_split | contributions, recipients, electoral_events | Monetary vs non-monetary split by party |
| 17 | party_avg_vs_count | contributions, recipients, electoral_events | Avg/median contribution and donor counts per party |
| 18 | contributor_frequency | contributions, electoral_events | Donor frequency buckets (Single, Occasional, Regular, Frequent) |
| 19 | contributor_scatter | contributions, contributors, electoral_events | Top 200 contributors by total (>$500, capped at $50K, ≤50 contributions) |
| 20 | repeat_vs_new | contributions, electoral_events | One-time vs repeat donor split |
| 21 | non_monetary_pct | contributions, recipients, electoral_events | Non-monetary contribution percentage by party |
| 22 | anomaly_distribution | contributions_by_district (Gold) | District count by avg-contribution bucket with anomaly overlay |

### 5.3 Compliance Datasets (23–27)

| # | Name | Source Tables | Description |
|---|---|---|---|
| 23 | over_limit_contributors | contributions, contributors, recipients, electoral_events | Contributors exceeding annual limit per party ($1,750/2025, $1,775/2026) |
| 24 | high_total_across_parties | contributions, contributors, recipients, electoral_events | Contributors with >$3,500 total across all parties |
| 25 | large_single_contributions | contributions, contributors, recipients, electoral_events | Individual contributions exceeding the annual limit |
| 26 | missing_data_large_donors | contributions, contributors, electoral_events | Large donors (>$500) with missing province, city, or postal code |
| 27 | frequent_small_donations | contributions, contributors, recipients, electoral_events | 10+ contributions with avg <$100 (potential structuring) |

---

## 6. Compliance Rules

Based on Elections Canada federal contribution limits.

| Rule | 2025 Limit | 2026 Limit | Source |
|---|---|---|---|
| Annual contribution per registered party | $1,750 | $1,775 | Canada Elections Act |
| Annual contribution to all associations/nomination contestants/candidates per party | $1,750 | $1,775 | Canada Elections Act |
| Annual increase | +$25/year on January 1 | +$25/year on January 1 | Canada Elections Act |
| Eligible contributors | Individuals (Canadian citizens or permanent residents) only | Same | Canada Elections Act |
| Corporations and trade unions | Prohibited | Prohibited | Canada Elections Act |

### 6.1 Anomaly Detection Logic

| Flag | Condition | Severity |
|---|---|---|
| Over Annual Limit | Total contributions to a single party exceed $1,750 (2025) or $1,775 (2026) | High |
| High Avg per Contributor | Average contribution per contributor in a district exceeds $1,500 | Medium |
| Single Donor District | One contributor accounts for >$1,000 in a district | Medium |
| High Cross-Party Total | Total contributions across all parties exceed $3,500 | Medium |
| Large Single Contribution | A single contribution exceeds the annual limit | High |
| Frequent Small Donations | 10+ contributions with avg <$100 to one party (potential structuring) | Low |
| Missing Data — Large Donor | Contributor with >$500 total missing province, city, or postal code | Low |

---

## 7. Global Filter

| Setting | Value |
|---|---|
| Filter Name | Fiscal Year |
| Type | Multi-select |
| Default Value | All (2025, 2026) |
| Linked Datasets | All except Dataset 10 (party_year_comparison) |
| Mechanism | Field-based filter (Datasets 1, 12) and Parameter-based via array_contains (all others) |

---

## 8. Access Control

### 8.1 Dashboard Sharing

| Principal | Permission | Purpose |
|---|---|---|
| Arsalan Eslami | Can Manage (inherited) | Owner and publisher |
| Admins | Can Manage (inherited) | Workspace administrators |
| entra-pfin-engineer | Can Manage | Data engineers — full edit and publish access |
| Faraz Eslami | Can Manage | Named engineer access |
| entra-pfin-dashboard-public | Can view | External dashboard viewers — read-only |

### 8.2 Viewer Entitlements (Databricks Workspace)

For users in entra-pfin-dashboard-public (dashboard-only viewers):

| Entitlement | Setting |
|---|---|
| Consumer access | On |
| Databricks SQL access | On |
| Workspace access | Off |
| Unrestricted cluster creation | Off |
| Admin access | Off |

### 8.3 Publish Credentials

| Setting | Value |
|---|---|
| Mode | Share data permission (default) |
| Publisher | arsalan@areslamihotmail.onmicrosoft.com |
| Effect | All dashboard queries run using the publisher's credentials — viewers need no direct table or warehouse access |

### 8.4 Test Verification

| Test | Result |
|---|---|
| Test account | pfin-test-viewer (Test Viewer) |
| Entra group | entra-pfin-dashboard-public |
| Workspace entitlements | Consumer access + SQL access only (no workspace access) |
| Dashboard access | Read-only via shared link — verified on mobile |
| Workspace UI visibility | None — viewer sees only the published dashboard |

---

## 9. Data Quality Notes

| Observation | Impact | Resolution |
|---|---|---|
| NULL electoral_district in Gold | Inflated totals in district charts | COALESCE to "National / No District"; excluded from district visualizations |
| NULL contributor_province | Unknown geographic distribution | COALESCE to "Unknown"; flagged in missing data compliance report |
| Only "Individuals" contributor type | contributions_by_contributor_type has limited value | Expected — federal law bans corporate/union donations since 2007 |
| 2026 data partial | Only NDP contributions reported for 2026 | Expected — partial year data; dashboard filters by year |

---

## 10. Exit Criteria

| # | Criterion | Status |
|---|---|---|
| 1 | SQL Warehouse operational | ✅ Serverless Starter Warehouse |
| 2 | Dashboard published with 7 pages | ✅ |
| 3 | 27 datasets created and validated | ✅ |
| 4 | Global fiscal year filter linked to all datasets | ✅ |
| 5 | entra-pfin-engineer shared with Can Manage | ✅ |
| 6 | entra-pfin-dashboard-public shared with Can view | ✅ |
| 7 | Published with Share data permission (default) | ✅ |
| 8 | Test viewer verified on mobile — dashboard-only access | ✅ |
| 9 | Compliance reports based on Elections Canada limits | ✅ |
| 10 | Phase 5 documentation committed | Pending |

---

## 11. Risks and Considerations

| Risk | Impact | Mitigation |
|---|---|---|
| Publisher credential dependency | If publisher account is disabled, dashboard stops working | Add a service principal as publisher in Phase 6 |
| SQL Warehouse costs | Serverless charges per query | Acceptable for dev; monitor usage for production |
| 2026 partial data | Charts show incomplete picture for 2026 | Dashboard filter defaults to All; users should be aware 2026 is partial |
| Over-limit detection is per-party only | Cross-entity limits (associations + candidates) not fully modeled | Acceptable for Phase 5; refine in future iterations |
| Viewer can request access to workspace | Databricks shows "Request access" prompt | Workspace access entitlement is Off — requests can be ignored or denied |

---

## 12. Document Control

| Date | Version | Change | Author |
|---|---|---|---|
| 2026-06-02 | 1.0 | Initial Phase 5 dashboards and reporting documentation | Arsalan Eslami |

---

File location: `docs/phase-5/dashboards.md` in the pfin-analytics repository.
