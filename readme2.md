

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROFILE = "CV_READONLY"
LOOKUP_DIR = "dbfs:/FileStore/lookup_files/"
ORS = "ORS_ID"
LABEL = "ORS_NAN"
MISSING = "TEXT MISSING"
DROP_COLS = ["meme_first_name", "meme_last_name"]
PERSONAL_COLS = ["BTH_DT", "PRPR_NPI", "PRPR_NAME", "MCTN_ID"]
AMOUNT_COLS = ["SRC_CHRG_AMT", "SRC_NTCOV_AMT", "CDML_PAID_AMT", "CDML_COPAY_AMT", "CDML_DED_AMT",
               "allow_amt"]
NULL_LIKE_27 = ["Null", "NULL", "null", "NaN", "TEXT NOT AVAILABLE", "TEXT NOT AVAILABLE.", ""]
NULL_LIKE_29 = ["Null", "NULL", "null", "NaN", "TEXT NOT AVAILABLE"]
NAVIGUARD_COLS = ["SRC_CLM_RSN_DESC", "plsrv_desc", "PROVIDERCOMMENTS", "PROVIDERREQUESTREASON"]
NAVIGUARD = "(?i)(navigaurd|naviguard)"
COLLECT_COLS = [
    "CLCL_ID", "ORS_NAN", "CLCL_CL_SUB_TYPE", "CLCL_LOW_SVC_DT", "CLCL_PAID_DT",
    "clcl_recv_dt", "PROC_DT", "CLM_STS_CD", "UDW_ADJD_MCE_ID", "UDW_MED_CLM_ID",
    "LATEST_SVC_DT", "ADJD_MED_CLM_SRVC_LN_NUM", "SRC_CLM_RSN_CD", "SRC_CLM_RSN_DESC",
    "REVENUE_CODE", "RVNU_DESC", "CAUS_CD", "PLSRV_CD", "plsrv_desc", "CAUS_DESC",
    "PRPR_NAME", "MCTN_ID", "PRPR_NPI", "Provider_Type", "Provider_Speciality",
    "PROV_ST_CD", "BTH_DT", "INN_OON_CD", "SNCTN_CD", "ORIG_PROC_CD", "DIAG_CD",
    "DIAG_DESC", "CLAIMSTATUS", "CLAIMTYPE", "ISBEHAVIOURHEALTH", "PROVIDERCOMMENTS",
    "PROVIDERREQUESTREASON", "CLAIMINDICATOR", "member_state", "ISS_CATGY_TYP_CD",
    "ISS_CATGY_TYP_DESC", "admission_date", "ADJD_PROC_MOD1_CD", "CLM_TYP_CD", "CLM_TYP_DESC",
    "total_attachments", "PROC_UNIT_CNT", "orig_dt", "SNCTN_DESC", "REQUESTREASONADJUSTER",
    "ADJD_PROC_MOD2_CD", "ADJD_PROC_MOD3_CD", "ADJD_PROC_MOD4_CD", "COB_IND", "render_state",
    "RNDR_PROV_CTY_NM", "adj_fp_flag", "Provider_Type_Desc", "Provider_Speciality_Desc",
    "Filing_Days", "Void_history", "previous_adjustment_code", "SRC_OVRD_CD", "PND_CD", "CO_CD",
    "FI_ASO",
]
DERIVED_COLS = ["Provider_Type_Desc", "Provider_Speciality_Desc", "Filing_Days", "Void_history",
                "previous_adjustment_code"]
MODEL_A_COLS = [
    "PROVIDERCOMMENTS", "PROVIDERREQUESTREASON", "DIAG_DESC", "CLCL_CL_SUB_TYPE", "CLM_STS_CD",
    "CAUS_DESC", "SNCTN_CD", "INN_OON_CD", "CLAIMSTATUS", "CLAIMTYPE", "CLAIMINDICATOR",
    "ISS_CATGY_TYP_CD", "RVNU_DESC", "Provider_Type", "PROV_ST_CD", "plsrv_desc",
    "Provider_Speciality", "SRC_CLM_RSN_CD", "member_state", "ADJD_PROC_MOD1_CD",
    "ADJD_MED_CLM_SRVC_LN_NUM", "SRC_CHRG_AMT", "SRC_NTCOV_AMT", "CDML_PAID_AMT", "CDML_COPAY_AMT",
    "CDML_DED_AMT", "allow_amt",
]
VALIDATOR_COLS = [
    "CLCL_ID", "orig_dt", "clcl_recv_dt", "PROC_DT", "CLCL_PAID_DT", "UDW_ADJD_MCE_ID", "CAUS_CD",
    "CO_CD", "FI_ASO", "Provider_Type_Desc", "Provider_Speciality_Desc", "PLSRV_CD",
    "REVENUE_CODE", "ORIG_PROC_CD", "ADJD_PROC_MOD2_CD", "ADJD_PROC_MOD3_CD", "ADJD_PROC_MOD4_CD",
    "DIAG_CD", "admission_date", "CLCL_LOW_SVC_DT", "LATEST_SVC_DT", "SRC_OVRD_CD", "PND_CD",
]
FORBIDDEN_CODE = tuple(a + b for a, b in (
    (".wri", "te"), ("saveAs", "Table"), ("insert", "Into"), ("INSE", "RT "), ("CREA", "TE "),
    ("DR", "OP "), ("MER", "GE "), ("ALT", "ER "), ("DELE", "TE "), ("TRUNC", "ATE"),
    ("spark", ".sql("), ("writeT", "o(")))
FORBIDDEN_WHERE = (";", "insert", "create", "drop", "merge", "alter", "delete", "truncate", "update",
                   "grant", "revoke")
KEYS = (("cast", ("cast_invalid_input", "cannot be cast", "numberformat", "invalid input syntax",
                  "datetime", "cast")),
        ("auth", ("credential", "unauthenticated", "401", "token")),
        ("permission", ("permission_denied", "insufficient", "403", "not authorized")),
        ("not_found", ("table_or_view_not_found", "not found", "does not exist",
                       "unresolved_column", "cannot be resolved")),
        ("memory", ("memory", "oom", "maxresultsize", "too large")),
        ("network", ("timed out", "timeout", "unreachable", "connection reset")))


def stop(message: str) -> None:
    raise SystemExit(f"STOP: {message}")


def kind(exc: Exception) -> str:
    text = str(exc).lower()
    found = [name for name, words in KEYS if any(word in text for word in words)]
    return type(exc).__name__ + (" [" + ", ".join(found) + "]" if found else "")


def names(items: list[str]) -> str:
    return ", ".join(items) if items else "none"


def read_only_guard() -> None:
    text = Path(__file__).read_text(encoding="utf-8")
    found = [token for token in FORBIDDEN_CODE if token in text]
    if found:
        stop(f"this script contains a Databricks write or SQL call ({len(found)}); refusing to run")


def session(profile: str, ansi: str):
    from databricks.connect import DatabricksSession

    spark = DatabricksSession.builder.profile(profile).serverless(True).getOrCreate()
    if ansi == "off":
        spark.conf.set("spark.sql.ansi.enabled", "false")
    try:
        mode = spark.conf.get("spark.sql.ansi.enabled")
    except Exception:
        mode = "unknown"
    print(f"connected | spark {spark.version} | ANSI mode {mode}", flush=True)
    return spark


def group(spark, source: str, where: str | None, keep_blank_labels: bool, drop_personal: bool):
    from pyspark.sql import functions as F
    from pyspark.sql.types import ArrayType, DateType, NumericType, TimestampType

    raw = spark.table(source)
    if where:
        raw = raw.filter(where)
    columns = raw.columns
    listed = [c for c in COLLECT_COLS + AMOUNT_COLS if c not in DERIVED_COLS]
    print(f"source columns {len(columns)} | listed columns missing in the source: "
          f"{names([c for c in listed if c not in columns])}")
    kept = set(COLLECT_COLS + AMOUNT_COLS + DROP_COLS + [ORS])
    print(f"source columns not kept by the grouping: {names([c for c in columns if c not in kept])}")
    for required in (ORS, LABEL, "CLCL_ID", "ISBEHAVIOURHEALTH", "CAUS_CD"):
        if required not in columns:
            stop(f"column {required} not found in the source")
    print(f"source rows {raw.count():,} | ORS {raw.select(ORS).distinct().count():,}", flush=True)

    df = raw.drop(*DROP_COLS)
    df = df.dropDuplicates()
    df = df.filter(
        F.col("CLCL_ID").isNotNull()
        & (F.trim(F.col("CLCL_ID").cast("string")) != "")
        & (F.col("CLCL_ID").cast("string") != "Null")
    )
    health = F.col("ISBEHAVIOURHEALTH").cast("string")
    df = df.filter(
        F.col("ISBEHAVIOURHEALTH").isNotNull()
        & (F.trim(health) != "")
        & (health != "Null") & (health != "null")
        & (health != "false") & (health != "False") & (health != "FALSE")
    ).filter(F.col("CAUS_CD").cast("string").isin("1", "6"))
    single = (df.groupBy(ORS).agg(F.countDistinct("CLCL_ID").alias("distinct_CLCL_count"))
              .filter("distinct_CLCL_count = 1").select(ORS))
    df = df.join(single, on=ORS, how="inner")
    print(f"in scope (claim ID present, behavioural health, cause 1 or 6, one claim per ORS): "
          f"rows {df.count():,} | ORS {df.select(ORS).distinct().count():,}", flush=True)

    skip = {LABEL} if keep_blank_labels else set()
    if keep_blank_labels:
        blank = F.trim(F.col(LABEL).cast("string")).isin(*NULL_LIKE_27, MISSING)
        df = df.withColumn(LABEL, F.when(F.col(LABEL).isNull() | blank, F.lit(None))
                           .otherwise(F.col(LABEL)))
    dates ={f.name for f in df.schema.fields if isinstance(f.dataType, (DateType, TimestampType))}
    for c in [c for c in df.columns if c not in AMOUNT_COLS and c not in dates and c not in skip]:
        df = df.withColumn(
            c,
            F.when(F.col(c).isNull() & ~F.col(c).cast("string").isNull(), MISSING)
            .when(F.trim(F.col(c).cast("string")) == "", MISSING)
            .when(F.col(c).cast("string") == "NaN", MISSING)
            .otherwise(F.col(c)),
        )
    for c in AMOUNT_COLS:
        if c in df.columns:
            df = df.withColumn(c, F.when(F.col(c).isNull(), 0).otherwise(F.col(c)))
    for field in df.schema.fields:
        c = field.name
        if c in skip or isinstance(field.dataType, (DateType, TimestampType)):
            continue
        if isinstance(field.dataType, NumericType):
            df = df.withColumn(c, F.when(F.col(c).isNull(), 0).otherwise(F.col(c)))
        else:
            text = F.col(c).cast("string")
            df = df.withColumn(
                c,
                F.when(text.isNull(), MISSING)
                .when(F.trim(text) == "", MISSING)
                .when(text.isin(*NULL_LIKE_27), MISSING)
                .otherwise(F.col(c)),
            )
    fields = df.schema.fields
    string_cols = [f.name for f in fields if str(f.dataType).startswith("String")]
    for c in string_cols:
        if c in skip:
            continue
        text = F.col(c).cast("string")
        df = df.withColumn(
            c,
            F.when(text.isNull(), MISSING)
            .when(F.trim(text) == "", MISSING)
            .when(text.isin(*NULL_LIKE_29), MISSING)
            .otherwise(F.col(c)),
        )
    for field in fields:
        if field.name in string_cols or field.name in skip:
            continue
        if isinstance(field.dataType, NumericType):
            df = df.withColumn(field.name,
                               F.when(F.col(field.name).isNull(), 0).otherwise(F.col(field.name)))

    spec = (spark.read.format("delta").load(LOOKUP_DIR + "provider_type_desc")
            .select(F.trim(F.col("Type")).alias("spec_key"),
                    F.trim(F.col("Description")).alias("Provider_Speciality_Desc"))
            .filter(F.col("spec_key").isNotNull() & (F.trim(F.col("spec_key")) != "")))
    kind_lookup = (spark.read.format("delta").load(LOOKUP_DIR + "provider_speciality_desc")
                   .select(F.trim(F.col("Prov_type")).alias("type_key"),
                           F.trim(F.col("Description")).alias("Provider_Type_Desc"))
                   .filter(F.col("type_key").isNotNull() & (F.trim(F.col("type_key")) != "")
                           & (F.col("type_key") != "NULL")))
    for c in ("Provider_Type_Desc", "Provider_Speciality_Desc"):
        if c in df.columns:
            df = df.drop(c)
    df = df.join(kind_lookup, F.trim(F.col("Provider_Type").cast("string")) == F.col("type_key"),
                 "left").drop("type_key")
    df = df.join(spec, F.trim(F.col("Provider_Speciality").cast("string")) == F.col("spec_key"),
                 "left").drop("spec_key")
    df = df.fillna({"Provider_Type_Desc": MISSING, "Provider_Speciality_Desc": MISSING})

    df = df.withColumn("Filing_Days", F.datediff(F.col("CLCL_PAID_DT").cast("date"),
                                                 F.col("clcl_recv_dt").cast("date")))
    reason = F.col("SRC_CLM_RSN_CD").cast("string").isin(["69", "70"])
    df = (df.withColumn("Void_history", F.when(reason, "Y").otherwise("N"))
          .withColumn("previous_adjustment_code", F.when(reason, "Y").otherwise("N")))
    for c in AMOUNT_COLS:
        if c in df.columns:
            df = df.withColumn(c, F.when(F.col(c) < 0, 0).when(F.col(c) == 0.01, 0)
                               .otherwise(F.col(c)))

    existing = df.columns
    exprs = [F.collect_set(F.col(c).cast("string")).alias(c) for c in COLLECT_COLS if c in existing]
    exprs += [F.sum_distinct(F.col(c)).alias(c) for c in AMOUNT_COLS if c in existing]
    grouped = df.groupBy([ORS]).agg(*exprs)

    if grouped.schema[LABEL].dataType.simpleString().startswith("array"):
        grouped = grouped.withColumn(LABEL, F.array_min(F.col(LABEL)))
    grouped = grouped.withColumn("ADJD_MED_CLM_SRVC_LN_NUM",
                                 F.array_max(F.col("ADJD_MED_CLM_SRVC_LN_NUM")).cast("int"))
    grouped = grouped.withColumn("Filing_Days", F.array_max(F.col("Filing_Days")).cast("int"))

    condition = None
    for field in grouped.schema.fields:
        if field.name not in NAVIGUARD_COLS:
            continue
        if isinstance(field.dataType, ArrayType):
            found = F.array_join(F.col(field.name), " ").rlike(NAVIGUARD)
        else:
            found = F.col(field.name).cast("string").rlike(NAVIGUARD)
        condition = found if condition is None else (condition | found)
    if condition is None:
        stop("none of the Naviguard rule columns is present")
    rule = condition & (F.col("Filing_Days") > 180) & (F.col(LABEL) == 1)
    grouped = grouped.withColumn("_label_rule", F.when(rule, "Y").otherwise("N"))
    grouped = grouped.withColumn(LABEL, F.when(rule, 0).otherwise(F.col(LABEL)))

    export = grouped
    for field in export.schema.fields:
        if isinstance(field.dataType, ArrayType):
            export = export.withColumn(field.name, F.array_join(F.col(field.name), ", "))
    if drop_personal:
        export = export.drop(*PERSONAL_COLS)
    return export


def run(args: argparse.Namespace) -> None:
    read_only_guard()
    if args.where and any(word in args.where.lower() for word in FORBIDDEN_WHERE):
        stop("--where may only hold a filter condition")
    out = Path(args.out)
    if out.exists() and not args.force:
        stop(f"{out.name} exists already; choose another --out or add --force")
    spark = session(args.profile, args.ansi)
    try:
        export = group(spark, args.source, args.where, not args.teammate_labels, args.drop_personal)
        frame = export.toPandas()
    except SystemExit:
        raise
    except Exception as exc:
        hint = " | rerun with --ansi off" if "[cast" in kind(exc) else ""
        stop(f"Databricks step failed: {kind(exc)}{hint}")
    changed = int((frame.pop("_label_rule") == "Y").sum())
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out, index=False)
    labels = frame[LABEL].astype("string").fillna("").str.strip()
    label_counts = labels.replace({"": "blank"}).value_counts()
    print(f"grouped rows {len(frame):,} | distinct ORS {frame[ORS].nunique():,} | columns "
          f"{len(frame.columns)} | written {out.name}")
    print("ORS_NAN: " + ", ".join(f"{value} {count:,}" for value, count in label_counts.items())
          + f" | changed to Rework by the Naviguard rule {changed:,}")
    print(f"Model A columns missing: {names([c for c in MODEL_A_COLS if c not in frame.columns])}")
    print(f"validator columns missing: {names([c for c in VALIDATOR_COLS if c not in frame.columns])}")


def items(value: str) -> frozenset:
    return frozenset(part.strip() for part in value.split(",") if part.strip())


def numeric_equal(left: str, right: str) -> bool:
    try:
        return abs(float(left) - float(right)) <= 1e-6
    except ValueError:
        return False


def compare(args: argparse.Namespace) -> None:
    for path in (args.new, args.reference):
        if not Path(path).is_file():
            stop(f"{Path(path).name} not found")
    new = pd.read_csv(args.new, dtype=str, keep_default_na=False)
    ref = pd.read_csv(args.reference, dtype=str, keep_default_na=False)
    for name, frame in (("new", new), ("reference", ref)):
        if ORS not in frame.columns:
            stop(f"column {ORS} not found in the {name} file")
        print(f"{name}: rows {len(frame):,} | distinct ORS {frame[ORS].nunique():,} | columns "
              f"{len(frame.columns)}")
    only_new = [c for c in new.columns if c not in ref.columns]
    only_ref = [c for c in ref.columns if c not in new.columns]
    shared = [c for c in ref.columns if c in new.columns and c != ORS]
    same_order = [c for c in new.columns if c in ref.columns] == [c for c in ref.columns if c in new.columns]
    print(f"columns only in new: {names(only_new)} | only in reference: {names(only_ref)} | "
          f"shared columns in the same order: {'yes' if same_order else 'no'}")
    a = new.drop_duplicates(ORS).set_index(ORS)
    b = ref.drop_duplicates(ORS).set_index(ORS)
    common = a.index.intersection(b.index)
    print(f"ORS in both {len(common):,} | only in new {len(a.index.difference(b.index)):,} | only "
          f"in reference {len(b.index.difference(a.index)):,}")
    if len(common) == 0:
        return
    a, b = a.loc[common], b.loc[common]
    identical = []
    for column in shared:
        left, right = a[column].to_numpy(), b[column].to_numpy()
        exact = left == right
        rest = [i for i in range(len(left)) if not exact[i]]
        order = sum(1 for i in rest if items(left[i]) == items(right[i]))
        numeric = sum(1 for i in rest if items(left[i]) != items(right[i])
                      and numeric_equal(left[i], right[i]))
        different = len(rest) - order - numeric
        if not rest:
            identical.append(column)
            continue
        print(f"  {column}: identical {int(exact.sum()):,} | same values, other order {order:,} | "
              f"same number, other format {numeric:,} | different {different:,}")
    print(f"columns identical for every shared ORS: {len(identical)} of {len(shared)}")
    if LABEL in shared:
        pairs = pd.crosstab(a[LABEL].replace({"": "blank"}), b[LABEL].replace({"": "blank"}))
        print("ORS_NAN new (rows) x reference (columns):")
        for value, row in pairs.iterrows():
            print(f"  {value}: " + ", ".join(f"{column} {count:,}" for column, count in row.items()))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_command = commands.add_parser("run", help="group a Databricks table into one row per ORS")
    run_command.add_argument("--source", required=True, help="Databricks table to read")
    run_command.add_argument("--out", required=True, help="CSV file to write on this laptop")
    run_command.add_argument("--where", default=None, help="optional filter condition (SQL)")
    run_command.add_argument("--teammate-labels", action="store_true",
                             help="fill empty labels as the notebook did (parity check only)")
    run_command.add_argument("--drop-personal", action="store_true",
                             help="leave out birth date, provider NPI, provider name and TIN")
    run_command.add_argument("--ansi", choices=["session", "off"], default="session")
    run_command.add_argument("--profile", default=PROFILE)
    run_command.add_argument("--force", action="store_true")
    compare_command = commands.add_parser("compare", help="compare two grouped CSV files")
    compare_command.add_argument("--new", required=True)
    compare_command.add_argument("--reference", required=True)
    args = parser.parse_args()
    if args.command == "run":
        run(args)
    else:
        compare(args)


if __name__ == "__main__":
    main()

