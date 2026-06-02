# ============================================================
# PFIN | Phase 4 | Political Finance Analytics Rules
# Notebook:  04_compliance_rules
# Source:    pfin_dev.silver.{contributions, contributors,
#            recipients, electoral_events}
# Target:    pfin_dev.gold.compliance_flags
#            pfin_dev.gold.eo_disclosure_list
# ============================================================

from pyspark.sql import functions as F
from pyspark.sql.window import Window
from datetime import datetime

# ── CONFIG ──────────────────────────────────────────────────
CATALOG  = "pfin_dev"
SILVER   = f"{CATALOG}.silver"
GOLD     = f"{CATALOG}.gold"
OPS      = f"{CATALOG}.ops"

CAP_LIMIT          = 3425.00
EO_THRESHOLD       = 200.00
APPROACHING_FLOOR  = 3000.00
STRUCTURING_MIN_TX = 10        # min transactions to check structuring
STRUCTURING_MAX_AVG= 50.00     # max avg amount for structuring flag
TOP_RECIPIENTS     = 3         # min distinct recipients for multi-recipient flag

run_start = datetime.now()
print(f"[{run_start}] Phase 4 — Compliance Rules started")
print(f"  Catalog        : {CATALOG}")
print(f"  Cap limit      : ${CAP_LIMIT:,.2f}")
print(f"  EO threshold   : ${EO_THRESHOLD:,.2f}")
print("-" * 60)


# ============================================================
# STEP 1: READ SILVER TABLES
# ============================================================
print(f"\n[{datetime.now()}] Reading Silver tables...")

df_contributions  = spark.table(f"{SILVER}.contributions")
df_contributors   = spark.table(f"{SILVER}.contributors")
df_recipients     = spark.table(f"{SILVER}.recipients")
df_events         = spark.table(f"{SILVER}.electoral_events")

for name, df in [
    ("contributions",    df_contributions),
    ("contributors",     df_contributors),
    ("recipients",       df_recipients),
    ("electoral_events", df_events),
]:
    print(f"  silver.{name}: {df.count():,} rows")


# ============================================================
# STEP 2: BUILD BASE — donor totals per fiscal year
# ============================================================
print(f"\n[{datetime.now()}] Building donor totals per fiscal year...")

# Join contributions with events to get fiscal_year
df_with_year = (
    df_contributions
    .join(df_events.select("electoral_event_key", "fiscal_year"),
          on="electoral_event_key", how="left")
)

# Aggregate per donor per year
df_donor_totals = (
    df_with_year
    .groupBy("contributor_key", "fiscal_year")
    .agg(
        F.sum("monetary_amount").cast("decimal(14,2)").alias("total_donated_amount"),
        F.count("*").alias("contribution_count"),
        F.avg("monetary_amount").cast("decimal(14,2)").alias("avg_contribution_amount"),
        F.countDistinct("recipient_id").alias("distinct_recipients"),
    )
)

print(f"  Donor-year combinations: {df_donor_totals.count():,}")


# ============================================================
# STEP 3: CAP STATUS
# ============================================================
print(f"\n[{datetime.now()}] Applying contribution cap rules...")

df_with_cap = (
    df_donor_totals
    .withColumn(
        "cap_status",
        F.when(F.col("total_donated_amount") > CAP_LIMIT, "over_cap")
         .when(F.col("total_donated_amount") == CAP_LIMIT, "at_cap")
         .when(F.col("total_donated_amount") >= APPROACHING_FLOOR, "approaching_cap")
         .otherwise("under_cap")
    )
    .withColumn(
        "refund_amount",
        F.greatest(
            (F.col("total_donated_amount") - F.lit(CAP_LIMIT)).cast("decimal(14,2)"),
            F.lit(0.00).cast("decimal(14,2)")
        )
    )
)

# Print cap summary
cap_summary = (
    df_with_cap
    .groupBy("cap_status")
    .agg(
        F.count("*").alias("donor_count"),
        F.sum("refund_amount").cast("decimal(14,2)").alias("total_refund_exposure")
    )
    .orderBy("cap_status")
)
cap_summary.show(truncate=False)


# ============================================================
# STEP 4: EO DISCLOSURE FLAG
# ============================================================
print(f"\n[{datetime.now()}] Applying Elections Ontario disclosure threshold...")

df_with_eo = (
    df_with_cap
    .withColumn(
        "is_eo_reportable",
        F.col("total_donated_amount") > EO_THRESHOLD
    )
)

eo_count = df_with_eo.filter(F.col("is_eo_reportable")).count()
print(f"  Donors above EO disclosure threshold (>${EO_THRESHOLD:,.2f}): {eo_count:,}")


# ============================================================
# STEP 5: IDENTITY / ELIGIBILITY FLAGS
# ============================================================
print(f"\n[{datetime.now()}] Applying identity and eligibility flags...")

# ── Flag: Non-Ontario donor ──────────────────────────────────
df_province_flag = (
    df_contributors
    .withColumn(
        "is_non_ontario",
        F.when(
            F.col("contributor_province").isNull() |
            (F.trim(F.col("contributor_province")) == ""),
            False   # unknown province — do not flag as non-Ontario
        ).otherwise(
            F.upper(F.trim(F.col("contributor_province"))) != "ON"
        )
    )
    .withColumn(
        "is_province_unknown",
        F.col("contributor_province").isNull() |
        (F.trim(F.col("contributor_province")) == "")
    )
)

# ── Flag: Missing donor name ─────────────────────────────────
df_name_flag = (
    df_province_flag
    .withColumn(
        "is_missing_name",
        (F.col("contributor_first_name").isNull() | (F.trim(F.col("contributor_first_name")) == "")) &
        (F.col("contributor_last_name").isNull()  | (F.trim(F.col("contributor_last_name")) == ""))
    )
)

# ── Flag: Shared address (different names at same address) ───
window_addr = Window.partitionBy("contributor_postal_code", "contributor_city")
df_addr_flag = (
    df_name_flag
    .withColumn(
        "distinct_names_at_address",
        F.countDistinct("contributor_name").over(window_addr)
    )
    .withColumn(
        "is_shared_address",
        F.col("distinct_names_at_address") > 1
    )
    .drop("distinct_names_at_address")
)

print(f"  Non-Ontario donors   : {df_addr_flag.filter('is_non_ontario').count():,}")
print(f"  Province unknown     : {df_addr_flag.filter('is_province_unknown').count():,}")
print(f"  Missing name         : {df_addr_flag.filter('is_missing_name').count():,}")
print(f"  Shared address       : {df_addr_flag.filter('is_shared_address').count():,}")


# ============================================================
# STEP 6: ADDITIONAL ENHANCEMENT RULES
# ============================================================
print(f"\n[{datetime.now()}] Applying enhancement rules...")

# ── Flag: Structuring — many small donations ─────────────────
df_structuring = (
    df_with_eo
    .withColumn(
        "is_structuring_pattern",
        (F.col("contribution_count") > STRUCTURING_MIN_TX) &
        (F.col("avg_contribution_amount") < STRUCTURING_MAX_AVG)
    )
)

# ── Flag: Multiple recipients (highly active donor) ──────────
df_multi_recipient = (
    df_structuring
    .withColumn(
        "is_multi_recipient",
        F.col("distinct_recipients") >= TOP_RECIPIENTS
    )
)

structuring_count     = df_multi_recipient.filter("is_structuring_pattern").count()
multi_recipient_count = df_multi_recipient.filter("is_multi_recipient").count()
print(f"  Structuring pattern  : {structuring_count:,} donor-years")
print(f"  Multi-recipient      : {multi_recipient_count:,} donor-years")


# ============================================================
# STEP 7: ASSEMBLE compliance_flags
# ============================================================
print(f"\n[{datetime.now()}] Assembling compliance_flags...")

NOW = F.lit(datetime.now().isoformat()).cast("timestamp")

# Join donor-level flags to contributor dimension
df_compliance = (
    df_multi_recipient
    .join(
        df_addr_flag.select(
            "contributor_key",
            "contributor_name",
            "contributor_last_name",
            "contributor_first_name",
            "contributor_middle_initial",
            "contributor_type",
            "contributor_province",
            "contributor_postal_code",
            "contributor_city",
            "is_non_ontario",
            "is_province_unknown",
            "is_missing_name",
            "is_shared_address",
        ),
        on="contributor_key", how="left"
    )
    .select(
        "contributor_key",
        "contributor_name",
        "contributor_type",
        "contributor_province",
        "contributor_postal_code",
        "contributor_city",
        "fiscal_year",
        "total_donated_amount",
        "contribution_count",
        "avg_contribution_amount",
        "distinct_recipients",
        "cap_status",
        "refund_amount",
        "is_eo_reportable",
        "is_non_ontario",
        "is_province_unknown",
        "is_shared_address",
        "is_missing_name",
        "is_structuring_pattern",
        "is_multi_recipient",
    )
    .withColumn("_aggregated_at", NOW)
    .orderBy(
        F.when(F.col("cap_status") == "over_cap",        1)
         .when(F.col("cap_status") == "at_cap",          2)
         .when(F.col("cap_status") == "approaching_cap", 3)
         .otherwise(4),
        F.desc("total_donated_amount")
    )
)

(df_compliance.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{GOLD}.compliance_flags"))

spark.sql(f"ALTER TABLE {GOLD}.compliance_flags CLUSTER BY (fiscal_year, cap_status)")
spark.sql(f"ALTER TABLE {GOLD}.compliance_flags ENABLE PREDICTIVE OPTIMIZATION")
rc = spark.table(f"{GOLD}.compliance_flags").count()
print(f"  compliance_flags: {rc:,} rows ✓")


# ============================================================
# STEP 8: ASSEMBLE eo_disclosure_list
# ============================================================
print(f"\n[{datetime.now()}] Assembling eo_disclosure_list...")

df_eo = (
    df_compliance
    .filter(F.col("is_eo_reportable") == True)
    .select(
        "contributor_key",
        F.col("contributor_name").alias("contributor_last_name"),   # adjust if split names available
        "contributor_type",
        "contributor_city",
        "contributor_province",
        "contributor_postal_code",
        "fiscal_year",
        "total_donated_amount",
        "is_eo_reportable",
        "cap_status",
        "_aggregated_at",
    )
    .orderBy(F.desc("total_donated_amount"))
)

(df_eo.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{GOLD}.eo_disclosure_list"))

spark.sql(f"ALTER TABLE {GOLD}.eo_disclosure_list CLUSTER BY (fiscal_year)")
spark.sql(f"ALTER TABLE {GOLD}.eo_disclosure_list ENABLE PREDICTIVE OPTIMIZATION")
rc_eo = spark.table(f"{GOLD}.eo_disclosure_list").count()
print(f"  eo_disclosure_list: {rc_eo:,} rows ✓")


# ============================================================
# STEP 9: DATA QUALITY CHECKS
# ============================================================
print(f"\n[{datetime.now()}] Running data quality checks...")

dq_results = []
all_passed = True

def dq_check(name, passed, detail=""):
    global all_passed
    status = "PASS" if passed else "FAIL"
    if not passed: all_passed = False
    print(f"  [{status}] {name}{' — ' + detail if detail else ''}")
    dq_results.append((name, status, detail, datetime.now().isoformat()))

# Row counts
dq_check("compliance_flags has rows",
    spark.table(f"{GOLD}.compliance_flags").count() > 0)

dq_check("eo_disclosure_list has rows",
    spark.table(f"{GOLD}.eo_disclosure_list").count() > 0)

# All over_cap have refund_amount > 0
bad_refund = (
    spark.table(f"{GOLD}.compliance_flags")
    .filter((F.col("cap_status") == "over_cap") & (F.col("refund_amount") <= 0))
    .count()
)
dq_check("All over_cap donors have refund_amount > 0", bad_refund == 0, f"{bad_refund} violations")

# No EO rows with total <= EO_THRESHOLD
bad_eo = (
    spark.table(f"{GOLD}.eo_disclosure_list")
    .filter(F.col("total_donated_amount") <= EO_THRESHOLD)
    .count()
)
dq_check(f"No eo_disclosure_list rows with total_donated_amount <= ${EO_THRESHOLD:.2f}",
    bad_eo == 0, f"{bad_eo} violations")

# No NULL cap_status
null_cap = (
    spark.table(f"{GOLD}.compliance_flags")
    .filter(F.col("cap_status").isNull())
    .count()
)
dq_check("No NULL cap_status in compliance_flags", null_cap == 0, f"{null_cap} nulls")

print(f"\n  {'✅ All checks passed' if all_passed else '❌ Some checks failed'}")

# Write DQ log
df_dq = spark.createDataFrame(
    dq_results,
    schema="check_name STRING, status STRING, detail STRING, checked_at STRING"
).withColumn("phase", F.lit("phase_4")) \
 .withColumn("run_start", F.lit(run_start.isoformat()))

(df_dq.write.format("delta").mode("append")
    .option("mergeSchema","true")
    .saveAsTable(f"{OPS}.data_quality_log"))

if not all_passed:
    raise Exception("Phase 4 compliance checks failed. See pfin_dev.ops.data_quality_log.")


# ============================================================
# STEP 10: SUMMARY
# ============================================================
run_end  = datetime.now()
duration = (run_end - run_start).total_seconds()

print(f"\n{'='*60}")
print(f"Phase 4 complete in {duration:.1f}s")
print(f"{'='*60}")

total_refund = (
    spark.table(f"{GOLD}.compliance_flags")
    .filter(F.col("cap_status") == "over_cap")
    .agg(F.sum("refund_amount").cast("decimal(14,2)")).collect()[0][0] or 0
)

print(f"  compliance_flags     : {spark.table(f'{GOLD}.compliance_flags').count():,} rows")
print(f"  eo_disclosure_list   : {spark.table(f'{GOLD}.eo_disclosure_list').count():,} rows")
print(f"  Total refund exposure: ${total_refund:,.2f}")
print(f"{'='*60}")
