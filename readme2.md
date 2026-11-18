from __future__ import annotations

import argparse
import math
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

ORS = "ORS_ID"
LABEL = "ORS_NAN"
MISSING = {"", "TEXT MISSING", "TEXT NOT AVAILABLE", "NAN", "NONE", "NULL", "NA", "N/A"}
DATE_COLS = ["orig_dt", "PROC_DT", "CLCL_PAID_DT", "clcl_recv_dt", "CLCL_LOW_SVC_DT", "LATEST_SVC_DT",
             "admission_date"]
MODEL_A_COLS = [
    "PROVIDERCOMMENTS", "PROVIDERREQUESTREASON", "DIAG_DESC", "CLCL_CL_SUB_TYPE", "CLM_STS_CD",
    "CAUS_DESC", "SNCTN_CD", "INN_OON_CD", "CLAIMSTATUS", "CLAIMTYPE", "CLAIMINDICATOR",
    "ISS_CATGY_TYP_CD", "RVNU_DESC", "Provider_Type", "PROV_ST_CD", "plsrv_desc",
    "Provider_Speciality", "SRC_CLM_RSN_CD", "member_state", "ADJD_PROC_MOD1_CD",
    "ADJD_MED_CLM_SRVC_LN_NUM", "SRC_CHRG_AMT", "SRC_NTCOV_AMT", "CDML_PAID_AMT", "CDML_COPAY_AMT",
    "CDML_DED_AMT", "allow_amt",
]
SERIAL = re.compile(r"^\d{5}(\.\d+)?$")
ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
CUTS = (0.30, 0.40, 0.50)
BINS = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8384, 1.000001)


def stop(message: str) -> None:
    raise SystemExit(f"STOP: {message}")


def pct(part: float, whole: float) -> str:
    return "n/a" if not whole else f"{100.0 * part / whole:.1f}%"


def wilson(hits: int, total: int) -> str:
    if not total:
        return "n/a"
    z = 1.96
    p = hits / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return f"{100 * max(0.0, centre - half):.1f}-{100 * min(1.0, centre + half):.1f}"


def read_text(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str, keep_default_na=False, na_filter=False)
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)


def read_typed(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(path)
    return pd.read_csv(path, low_memory=False)


def opened(ors: str) -> date | None:
    text = str(ors).strip()
    if len(text) < 5 or not text[0].isalpha() or not text[1:5].isdigit():
        return None
    day = int(text[2:5])
    if not 1 <= day <= 366:
        return None
    value = date(2020 + int(text[1]), 1, 1) + timedelta(days=day - 1)
    return value if value.year == 2020 + int(text[1]) else None


def items(value: object) -> frozenset:
    out = set()
    for part in str(value).split(","):
        part = part.strip()
        if part.endswith(".0") and part[:-2].lstrip("-").isdigit():
            part = part[:-2]
        if part.upper() not in MISSING:
            out.add(part)
    return frozenset(out)


def dates_in(value: object) -> list[date]:
    out = []
    for part in str(value).split(","):
        match = ISO.match(part.strip())
        if match:
            try:
                out.append(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
            except ValueError:
                continue
    return out


def auc(score: pd.Series, y: pd.Series) -> float | None:
    mask = score.notna() & y.notna()
    s, t = score[mask].astype(float), y[mask].astype(int)
    pos, neg = int((t == 1).sum()), int((t == 0).sum())
    if not pos or not neg:
        return None
    ranks = s.rank(method="average")
    return float((ranks[t == 1].sum() - pos * (pos + 1) / 2) / (pos * neg))


def load_outputs(paths: list[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        if not path.is_file():
            stop(f"{path.name} not found")
        frame = read_text(path)
        for column in ("ors_id", "actual_label", "primary_probability_rework"):
            if column not in frame.columns:
                stop(f"column {column} not found in {path.name}")
        frame["_file"] = path.name
        frames.append(frame)
    data = pd.concat(frames, ignore_index=True)
    data["ors_id"] = data["ors_id"].str.strip()
    data = data.drop_duplicates("ors_id")
    data["_y"] = data["actual_label"].str.strip().map({"NAN": 1, "Rework": 0})
    data["_p"] = pd.to_numeric(data["primary_probability_rework"], errors="coerce")
    data["_open"] = data["ors_id"].map(opened)
    data["_month"] = data["_open"].map(lambda d: d.strftime("%Y-%m") if d else "unknown")
    data["_week"] = data["_open"].map(lambda d: f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
                                      if d else "unknown")
    return data


def model_lines(name: str, frame: pd.DataFrame, threshold: float) -> list[str]:
    lab = frame[frame["_y"].notna() & frame["_p"].notna()]
    n, nan = len(lab), int(lab["_y"].sum())
    if not n:
        return [f"{name}: no labelled scored rows"]
    called = lab[lab["_p"] < threshold]
    tp = int(called["_y"].sum())
    value = auc(1 - lab["_p"], lab["_y"])
    line = (f"{name}: n {n} | NAN {nan} ({pct(nan, n)}) | AUC {'n/a' if value is None else f'{value:.3f}'}"
            f" | Model A NAN calls {len(called)} ({pct(len(called), n)}) precision {pct(tp, len(called))}"
            f" ({wilson(tp, len(called))}) recall {pct(tp, nan)}")
    cuts = []
    for cut in CUTS:
        released = lab[lab["_p"] <= cut]
        hits = int(released["_y"].sum())
        cuts.append(f"P<={cut:.2f}: {len(released)} ({pct(len(released), n)}) precision "
                    f"{pct(hits, len(released))} ({wilson(hits, len(released))})")
    inside = lab[lab["_p"] < threshold]
    inside_auc = auc(1 - inside["_p"], inside["_y"])
    return [line, "    " + " | ".join(cuts)
            + f" | AUC inside NAN calls {'n/a' if inside_auc is None else f'{inside_auc:.3f}'}"]


def decile_lines(name: str, frame: pd.DataFrame) -> list[str]:
    scored = frame[frame["_p"].notna()]
    if scored.empty:
        return [f"{name}: no scores"]
    bands = pd.cut(scored["_p"], BINS, right=False)
    parts = []
    for band, group in scored.groupby(bands, observed=False):
        labelled = group["_y"].dropna()
        parts.append(f"[{band.left:.2f},{min(band.right, 1.0):.2f}) {len(group)} "
                     f"({pct(len(group), len(scored))}) NAN {pct(labelled.sum(), len(labelled))}")
    return [f"{name} score bands (rows, share, NAN rate):", "    " + " | ".join(parts)]


def section_labels(data: pd.DataFrame) -> None:
    print("== 1 labels by ORS open period (label maturity)")
    labelled = data["_y"].notna()
    print(f"rows {len(data)} | labelled {int(labelled.sum())} | blank labels {int((~labelled).sum())} | "
          f"open date unknown {int((data['_month'] == 'unknown').sum())}")
    for key in ("_month", "_week"):
        table = data[labelled].groupby(key)["_y"].agg(["size", "sum"])
        print(("by month: " if key == "_month" else "by week: ")
              + " | ".join(f"{idx} {int(r['size'])} ({pct(r['sum'], r['size'])} NAN)"
                           for idx, r in table.iterrows()))


def section_model(data: pd.DataFrame, reference: pd.DataFrame | None, threshold: float,
                  label: str) -> None:
    print(f"== 2 Model A health ({label})")
    for line in model_lines("all", data, threshold):
        print(line)
    for month, group in data.groupby("_month"):
        for line in model_lines(month, group, threshold):
            print(line)
    for line in decile_lines("pilot", data):
        print(line)
    if reference is not None:
        for line in model_lines("REFERENCE (holdout)", reference, threshold):
            print(line)
        for line in decile_lines("reference", reference):
            print(line)


def segment_flags(grouped: pd.DataFrame) -> pd.DataFrame:
    flags = pd.DataFrame({"ors_id": grouped[ORS].str.strip()})
    flags["letter_suffix"] = grouped[ORS].map(lambda v: not str(v).strip()[11:15].isdigit())
    flags["no_request_reason"] = grouped["PROVIDERREQUESTREASON"].map(lambda v: not items(v))
    flags["aba_bha"] = grouped["Provider_Speciality"].map(lambda v: "BHA" in {i.upper() for i in items(v)})
    flags["adjustment_69_70"] = grouped["SRC_CLM_RSN_CD"].map(lambda v: bool({"69", "70"} & items(v)))
    return flags.drop_duplicates("ors_id")


def section_segments(data: pd.DataFrame, grouped: pd.DataFrame, threshold: float) -> None:
    print("== 3 Model A by segment (pilot rows)")
    joined = data.merge(segment_flags(grouped), on="ors_id", how="left")
    print(f"pilot rows matched in the grouped file: {int(joined['letter_suffix'].notna().sum())} of {len(joined)}")
    for flag in ("letter_suffix", "no_request_reason", "aba_bha", "adjustment_69_70"):
        for value in (True, False):
            group = joined[joined[flag] == value]
            for line in model_lines(f"{flag}={value}", group, threshold)[:1]:
                print(line)


def section_inputs(inputs: list[Path], grouped: pd.DataFrame) -> None:
    print("== 4 input integrity (pilot input files against the clean grouped file)")
    clean = grouped.drop_duplicates(ORS).set_index(grouped.drop_duplicates(ORS)[ORS].str.strip())
    for path in inputs:
        if not path.is_file():
            print(f"{path.name}: not found")
            continue
        frame = read_text(path)
        if ORS not in frame.columns:
            print(f"{path.name}: no {ORS} column")
            continue
        ors = frame[ORS].str.strip()
        found = ors.isin(clean.index)
        print(f"{path.name}: format {path.suffix.lower()} | rows {len(frame)} | found in grouped file "
              f"{int(found.sum())}")
        serial = []
        for column in DATE_COLS:
            if column in frame.columns:
                hits = frame[column].map(lambda v: any(SERIAL.match(p.strip()) for p in str(v).split(",")))
                serial.append(f"{column} {int(hits.sum())}")
        print("    rows with Excel-serial-like dates: " + (" | ".join(serial) if serial else "no date columns"))
        diffs = []
        sub = frame[found.values]
        base = clean.loc[ors[found].values]
        for column in MODEL_A_COLS:
            if column not in frame.columns or column not in base.columns:
                diffs.append(f"{column} missing")
                continue
            left = sub[column].map(items).to_numpy()
            right = base[column].map(items).to_numpy()
            count = sum(1 for a, b in zip(left, right) if a != b)
            if count:
                diffs.append(f"{column} {count}")
        print("    Model A columns with different values: " + (" | ".join(diffs) if diffs else "none"))
        typed = read_typed(path)
        kinds = [f"{c} {typed[c].dtype}" for c in MODEL_A_COLS if c in typed.columns
                 and str(typed[c].dtype) not in ("object", "float64", "int64")]
        if kinds:
            print("    unusual typed columns: " + " | ".join(kinds))


def section_rescore(data: pd.DataFrame, grouped_path: Path, threshold: float, limit: int) -> pd.DataFrame | None:
    print("== 5 Model A re-scored from the clean grouped file")
    from claim_validator.primary_model import PrimaryModel, PrimaryModelConfig, _json_value

    model = PrimaryModel.load(PrimaryModelConfig.load(REPO_ROOT))
    typed = pd.read_csv(grouped_path, low_memory=False)
    typed[ORS] = typed[ORS].astype(str).str.strip()
    typed = typed.drop_duplicates(ORS).set_index(ORS)
    wanted = [o for o in data["ors_id"] if o in typed.index][:limit]
    if not wanted:
        print("no pilot ORS found in the grouped file")
        return None
    rows = typed.loc[wanted, list(model.columns)]
    records = [{c: _json_value(v) for c, v in zip(model.columns, values)}
               for values in rows.itertuples(index=False, name=None)]
    scores = []
    for start in range(0, len(records), 500):
        frame = pd.DataFrame(records[start:start + 500], columns=list(model.columns), dtype=object)
        scores.extend(float(v) for v in model._predictor.predict(frame)["probability_rework"])
    fresh = pd.DataFrame({"ors_id": wanted, "_p_clean": scores})
    merged = data.merge(fresh, on="ors_id", how="inner")
    diff = (merged["_p_clean"] - merged["_p"]).abs()
    print(f"compared {len(merged)} | max abs difference {diff.max():.6f} | differing by >0.001 "
          f"{int((diff > 0.001).sum())} | by >0.05 {int((diff > 0.05).sum())} | "
          f"P<=0.30 pilot {int((merged['_p'] <= 0.30).sum())} vs clean {int((merged['_p_clean'] <= 0.30).sum())}")
    clean = merged.assign(_p=merged["_p_clean"])
    for line in model_lines("clean scores, all", clean, threshold):
        print(line)
    return clean


def section_drift(new: pd.DataFrame, old: pd.DataFrame | None) -> None:
    print("== 6 data profile by ORS open month (old training-era file vs new file)")
    for name, frame in (("old", old), ("new", new)):
        if frame is None:
            continue
        work = pd.DataFrame({"ors": frame[ORS].str.strip()})
        work["open"] = work["ors"].map(opened)
        work["month"] = work["open"].map(lambda d: d.strftime("%Y-%m") if d else "unknown")
        work["y"] = pd.to_numeric(frame[LABEL], errors="coerce") if LABEL in frame.columns else float("nan")
        work["events"] = frame["UDW_ADJD_MCE_ID"].map(lambda v: len(items(v))) if "UDW_ADJD_MCE_ID" in frame.columns else float("nan")
        proc = frame["PROC_DT"].map(dates_in) if "PROC_DT" in frame.columns else pd.Series([[]] * len(frame))
        work["proc_n"] = proc.map(len)
        work["post_open"] = [bool(o and any(d > o for d in ds)) for o, ds in zip(work["open"], proc)]
        flags = segment_flags(frame)
        work = work.join(flags.set_index("ors_id"), on="ors")
        latest = max((d for ds in proc for d in ds), default=None)
        print(f"{name}: rows {len(work)} | latest processing date {latest}")
        for month, group in work.groupby("month"):
            labelled = group["y"].dropna()
            print(f"  {name} {month}: n {len(group)} | NAN {pct(labelled.sum(), len(labelled))} | "
                  f"letter suffix {pct(group['letter_suffix'].sum(), len(group))} | no request reason "
                  f"{pct(group['no_request_reason'].sum(), len(group))} | ABA {pct(group['aba_bha'].sum(), len(group))} | "
                  f"69/70 {pct(group['adjustment_69_70'].sum(), len(group))} | post-open processing "
                  f"{pct(group['post_open'].sum(), len(group))} | one processing date "
                  f"{pct((group['proc_n'] == 1).sum(), len(group))} | mean event ids {group['events'].mean():.2f}")


def section_overlap(new: pd.DataFrame, old: pd.DataFrame) -> None:
    print("== 7 ORS in both files: label old (rows) x new (columns)")
    a = old[[ORS, LABEL]].assign(**{ORS: old[ORS].str.strip()}).drop_duplicates(ORS).set_index(ORS)
    b = new[[ORS, LABEL]].assign(**{ORS: new[ORS].str.strip()}).drop_duplicates(ORS).set_index(ORS)
    common = a.index.intersection(b.index)
    print(f"ORS in both {len(common)}")
    if len(common):
        table = pd.crosstab(a.loc[common, LABEL].replace({"": "blank"}),
                            b.loc[common, LABEL].replace({"": "blank"}))
        for value, row in table.iterrows():
            print(f"  old {value}: " + ", ".join(f"new {k} {int(v)}" for k, v in row.items()))


def section_validator(data: pd.DataFrame) -> None:
    print("== 8 validator decision paths (rows the validator ran) x actual label")
    if "validator_decision_path" not in data.columns:
        print("no validator_decision_path column")
        return
    ran = data[data.get("validator_run", "") == "yes"] if "validator_run" in data.columns else data
    table = pd.crosstab(ran["validator_decision_path"].replace({"": "none"}),
                        ran["actual_label"].replace({"": "blank"}))
    for path, row in table.iterrows():
        print(f"  {path}: " + ", ".join(f"{k} {int(v)}" for k, v in row.items()))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Pilot diagnostics: labels, Model A health, input integrity, drift. Counts only; no LLM calls.")
    parser.add_argument("--output", type=Path, nargs="+", required=True, help="pilot batch output CSV file(s)")
    parser.add_argument("--grouped", type=Path, help="clean grouped CSV for the new table (k30 output)")
    parser.add_argument("--inputs", type=Path, nargs="*", default=[], help="the input files the pilot runs used")
    parser.add_argument("--old-grouped", type=Path, help="training-era grouped file (9 Oct)")
    parser.add_argument("--reference-output", type=Path, help="holdout batch output with scores and labels")
    parser.add_argument("--rescore", type=int, default=0, help="re-score up to N pilot ORS with Model A")
    parser.add_argument("--threshold", type=float, default=0.8384)
    args = parser.parse_args()

    data = load_outputs(args.output)
    reference = load_outputs([args.reference_output]) if args.reference_output else None
    grouped = read_text(args.grouped) if args.grouped else None
    old = read_text(args.old_grouped) if args.old_grouped else None

    section_labels(data)
    section_model(data, reference, args.threshold, "scores as used in the pilot")
    if grouped is not None:
        section_segments(data, grouped, args.threshold)
        if args.inputs:
            section_inputs(args.inputs, grouped)
        if args.rescore:
            section_rescore(data, args.grouped, args.threshold, args.rescore)
        section_drift(grouped, old)
        if old is not None:
            section_overlap(grouped, old)
    section_validator(data)


if __name__ == "__main__":
    main()
