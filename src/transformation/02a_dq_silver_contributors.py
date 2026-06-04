# Databricks notebook source
# MAGIC %md
# MAGIC # PFIN — Data Quality: Silver Contributors
# MAGIC
# MAGIC **Runs after:** `02_transform_silver`
# MAGIC
# MAGIC Normalizes contributor names from component fields, standardizes postal codes,
# MAGIC and logs DQ metrics to `ops.data_quality_log`.

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 1: Configuration and Helpers

# COMMAND ----------

from pyspark.sql import functions as F, Row
from datetime import datetime

catalog = "pfin_dev"
full_table = f"{catalog}.silver.contributors"
dq_log_table = f"{catalog}.ops.data_quality_log"
dq_phase = "dq_silver_contributors"

# --- Reusable functions (called multiple times) ---

def is_present(col_name):
    """True if column is not null and not blank."""
    return F.col(col_name).isNotNull() & (F.trim(F.col(col_name)) != "")

def clean_alpha(col_name):
    """Uppercase, trim, strip non-alpha chars. Returns original if null/empty."""
    return F.when(is_present(col_name),
        F.upper(F.trim(F.regexp_replace(F.col(col_name), "[^A-Za-z\\s]", "")))
    ).otherwise(F.col(col_name))

def build_full_name(first, middle, last):
    """Rebuild name from components if first+last exist; otherwise normalize existing."""
    rebuilt = F.trim(F.regexp_replace(
        F.concat_ws(" ", F.col(first), F.col(middle), F.col(last)), "\\s+", " "
    ))
    fallback = F.upper(F.trim(F.regexp_replace(
        F.regexp_replace(F.col("contributor_name"), "[^A-Za-z\\s]", ""), "\\s+", " "
    )))
    return F.when(is_present(first) & is_present(last), rebuilt).otherwise(fallback)

print(f"Target: {full_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 2: Read Data and Pre-DQ Metrics

# COMMAND ----------

df = spark.table(full_table)
total_rows = df.count()
pre_distinct = df.select("contributor_name").distinct().count()
pre_postal_spaces = df.filter(F.col("contributor_postal_code").rlike("\\s")).count()

print(f"Total rows: {total_rows}")
print(f"Distinct names (before): {pre_distinct}")
print(f"Postal codes with spaces: {pre_postal_spaces}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 3: Detect Duplicate Names (Pre-DQ)

# COMMAND ----------

duplicates = (
    df.withColumn("normalized", build_full_name(
        "contributor_first_name", "contributor_middle_initial", "contributor_last_name"
    ))
    .groupBy("normalized")
    .agg(F.countDistinct("contributor_name").alias("variations"),
         F.collect_set("contributor_name").alias("examples"))
    .filter(F.col("variations") > 1)
    .orderBy(F.col("variations").desc())
)

dup_count = duplicates.count()
print(f"Name groups with multiple formats: {dup_count}")
if dup_count > 0:
    duplicates.show(20, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 4: Clean Fields, Rebuild Names, Fix Postal Codes

# COMMAND ----------

df_cleaned = (
    df
    .withColumn("contributor_first_name", clean_alpha("contributor_first_name"))
    .withColumn("contributor_last_name", clean_alpha("contributor_last_name"))
    .withColumn("contributor_middle_initial",
        F.when(is_present("contributor_middle_initial"),
            F.upper(F.trim(F.regexp_replace(F.col("contributor_middle_initial"), "[^A-Za-z]", "")))
        ).otherwise(None)
    )
    .withColumn("contributor_name",
        build_full_name("contributor_first_name", "contributor_middle_initial", "contributor_last_name")
    )
    .withColumn("contributor_postal_code",
        F.when(F.col("contributor_postal_code").isNotNull(),
            F.upper(F.regexp_replace(F.col("contributor_postal_code"), "\\s+", ""))
        ).otherwise(None)
    )
)

has_components = is_present("contributor_first_name") & is_present("contributor_last_name")
rebuilt_count = df_cleaned.filter(has_components).count()
fallback_count = df_cleaned.filter(~has_components).count()

print(f"Names rebuilt from components: {rebuilt_count}")
print(f"Names normalized (fallback): {fallback_count}")
df_cleaned.select("contributor_first_name", "contributor_middle_initial",
                   "contributor_last_name", "contributor_name").show(10, truncate=False)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 5: Post-DQ Metrics

# COMMAND ----------

post_distinct = df_cleaned.select("contributor_name").distinct().count()
names_resolved = pre_distinct - post_distinct
post_postal_spaces = df_cleaned.filter(F.col("contributor_postal_code").rlike("\\s")).count()

print(f"Distinct names (after): {post_distinct}")
print(f"Duplicates resolved: {names_resolved}")
print(f"Postal codes with spaces (after): {post_postal_spaces}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 6: Write Back to Silver

# COMMAND ----------

df_cleaned.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(full_table)

verify_count = spark.table(full_table).count()
assert verify_count == total_rows, f"Row count mismatch: expected {total_rows}, got {verify_count}"
print(f"Updated {full_table} — {verify_count} rows verified.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Step 7: Log DQ Results and Summary

# COMMAND ----------

run_ts = str(datetime.now())

dq_results = [
    Row(phase=dq_phase, check_name="name_normalization", status="PASS",
        detail=f"Rebuilt {rebuilt_count}, fallback {fallback_count}. Duplicates resolved: {names_resolved}. Distinct: {pre_distinct} → {post_distinct}",
        checked_at=run_ts, run_start=""),
    Row(phase=dq_phase, check_name="postal_code_standardization", status="PASS",
        detail=f"Fixed {pre_postal_spaces} postal codes. Remaining with spaces: {post_postal_spaces}",
        checked_at=run_ts, run_start=""),
    Row(phase=dq_phase, check_name="row_count_integrity",
        status="PASS" if verify_count == total_rows else "FAIL",
        detail=f"Expected {total_rows}, got {verify_count}",
        checked_at=run_ts, run_start=""),
]

spark.createDataFrame(dq_results).write.mode("append").saveAsTable(dq_log_table)

print("=" * 60)
print("  PFIN Data Quality — Silver Contributors — COMPLETE")
print("=" * 60)
print(f"  Total rows:              {total_rows}")
print(f"  Rebuilt from components: {rebuilt_count}")
print(f"  Normalized (fallback):   {fallback_count}")
print(f"  Distinct names before:   {pre_distinct}")
print(f"  Distinct names after:    {post_distinct}")
print(f"  Duplicates resolved:     {names_resolved}")
print(f"  Postal codes fixed:      {pre_postal_spaces}")
print(f"  Row count verified:      {verify_count == total_rows}")
print("=" * 60)
