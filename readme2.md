
BEFORE PASTING (you, by hand):
1. Copy sop_rag_claim_validator\scripts\k30_eda_grouping.py into the SOP-RAG project's scripts folder on this laptop (Documents\SOP-RAG\scripts\k30_eda_grouping.py).
2. Paste everything below into Copilot.

You are in VS Code on Windows (PowerShell terminal). Run the EDA grouping script on the OLD raw table and compare its output with the existing 9 Oct grouped file, to prove the script reproduces the notebook. Act as an operator: follow the steps exactly and report with the template.

RULES
1. READ ONLY in Databricks. Never write, save, create, insert, merge, alter, drop or delete anything in Databricks. The bh_nan_pred schema and the old table are read-only: this rule may not be broken for any reason. Run only the commands below; do not edit the script.
2. Do not edit or delete any repository file. The only files written are the CSV of STEP 1 under artifacts\claim_validator\eda. Never open or print the CSV files or %USERPROFILE%\.databrickscfg.
3. Never print or report table names, the workspace address, tokens, account names, e-mail addresses, URLs or data values. Report counts, column names and statuses only. Replace the Windows user name in any path with <USER>.
4. If a step prints a line starting with STOP, follow the instruction for that step; otherwise STOP and report that step's lines.
5. Report every line each step prints, exactly as printed. Do not summarise.
6. Do NOT run the script on bh_nan_pred.nan_pred_base_new in this prompt.

STEP 0 - files, environment and copy check
$SRC = "$env:USERPROFILE\Documents\SOP-RAG"
Set-Location $SRC
$DBPY = "$env:USERPROFILE\miniforge3\envs\py312\python.exe"
$REF = "artifacts\claim_validator\df_one_to_one_grouped_9OCTV1.csv"
$env:CV_OLD_TABLE = 'Deepakshi_sandbox.nan_pred_base'
"script present: $(Test-Path scripts\k30_eda_grouping.py) | python present: $(Test-Path $DBPY) | reference present: $(Test-Path $REF) | old table name set: $([bool]$env:CV_OLD_TABLE)"
& $DBPY -c "import hashlib,sys; t=open(sys.argv[1],'rb').read().replace(b'\r\n',b'\n').rstrip(b'\n'); print(hashlib.sha256(t).hexdigest())" scripts\k30_eda_grouping.py
Expected hash: a7550056453e6967ef5b215c8c7a45ec8ddf2a739c2b09c62938ec2793300ca3
If the hash differs: STOP and report (the copy is not exact).
If the reference is not present: run
Get-ChildItem artifacts\claim_validator -Filter *.csv | Where-Object { $_.Name -match 'grouped' } | Select-Object -ExpandProperty Name
then STOP and report the file names.

STEP 1 - group the old table (read-only on Databricks serverless; can take 5-20 minutes)
& $DBPY scripts\k30_eda_grouping.py run --source $env:CV_OLD_TABLE --out artifacts\claim_validator\eda\parity_old_table.csv --teammate-labels
If it prints a STOP line ending in "rerun with --ansi off", run once more:
& $DBPY scripts\k30_eda_grouping.py run --source $env:CV_OLD_TABLE --out artifacts\claim_validator\eda\parity_old_table.csv --teammate-labels --ansi off --force
Any other STOP: STOP and report.

STEP 2 - compare with the 9 Oct file (on this laptop only, a few minutes)
& $DBPY scripts\k30_eda_grouping.py compare --new artifacts\claim_validator\eda\parity_old_table.csv --reference $REF

REPORT
Reply with exactly this template, filled in, and nothing else:
STEP 0: <lines>
STEP 1: <every line printed, for each run>
STEP 2: <every line printed>
STOPPED AT: <step and reason, or "completed">
