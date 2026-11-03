
You are in VS Code on Windows (PowerShell terminal). Run the verified EDA grouping script on the NEW raw table to produce the grouped file (one row per ORS, same format as the 9 Oct file) that will be scored by Model A and the validator. Act as an operator: follow the steps exactly and report with the template.

RULES
1. READ ONLY in Databricks. Never write, save, create, insert, merge, alter, drop or delete anything in Databricks. bh_nan_pred.nan_pred_base_new and the bh_nan_pred schema are read-only: this rule may not be broken for any reason. Run only the commands below; do not edit the script.
2. Do not edit or delete any repository file. The only file written is the CSV of STEP 1 under artifacts\claim_validator\eda. Never open or print the CSV file or %USERPROFILE%\.databrickscfg.
3. Never print or report the workspace address, tokens, account names, e-mail addresses, URLs or data values. Report counts, column names and statuses only. Replace the Windows user name in any path with <USER>.
4. If a step prints a line starting with STOP, STOP and report that step's lines.
5. Report every line each step prints, exactly as printed. Do not summarise.

STEP 0 - environment
Set-Location "$env:USERPROFILE\Documents\SOP-RAG"
$DBPY = "$env:USERPROFILE\miniforge3\envs\py312\python.exe"
"script present: $(Test-Path scripts\k30_eda_grouping.py) | python present: $(Test-Path $DBPY) | kind() update present: $(Select-String -Path scripts\k30_eda_grouping.py -Pattern 'getCondition' -Quiet)"

STEP 1 - group the new table (read-only on Databricks serverless; can take 5-20 minutes)
& $DBPY -u scripts\k30_eda_grouping.py run --source bh_nan_pred.nan_pred_base_new --out artifacts\claim_validator\eda\df_one_to_one_grouped_new.csv --drop-personal

STEP 2 - ORS open months of the grouped file (on this laptop only; counts per month)
@'
import pandas as pd

frame = pd.read_csv(r"artifacts\claim_validator\eda\df_one_to_one_grouped_new.csv", dtype=str, keep_default_na=False, usecols=["ORS_ID", "ORS_NAN", "orig_dt"])
first = frame["orig_dt"].str.split(",").str[0].str.strip().str[:7]
label = frame["ORS_NAN"].str.strip().replace({"": "blank"})
table = pd.crosstab(first, label)
print("ORS by first orig_dt month (rows) x ORS_NAN (columns):")
print(table.to_string())
'@ | & $DBPY -

REPORT
Reply with exactly this template, filled in, and nothing else:
STEP 0: <line>
STEP 1: <every line printed>
STEP 2: <every line printed>
STOPPED AT: <step and reason, or "completed">
