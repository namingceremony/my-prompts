
You are in VS Code on Windows (PowerShell terminal). Run READ-ONLY Databricks Connect tests with the existing sign-in profile CV_READONLY. Act as an operator: follow the steps exactly and report with the template.

RULES
1. READ ONLY in Databricks. Never write, save, create, insert, merge, alter, drop or delete anything in Databricks. bh_nan_pred.nan_pred_base_new and the bh_nan_pred schema are read-only: this rule may not be broken for any reason. Run only the code below.
2. Never open, read, print or edit %USERPROFILE%\.databrickscfg except with the exact command in STEP 1, which prints section names only. Never print the workspace address, token, account names, e-mail addresses or URLs. Do not edit any repository file. Do not install anything.
3. Report counts, versions, profile names and error types only. If a step fails or prints STOP, STOP and report that step's lines, with any URL, address or name replaced by <VALUE>.
4. Report every line each step prints, exactly as printed.

STEP 1 - environment and profile
$DBPY = "$env:USERPROFILE\miniforge3\envs\py312\python.exe"
if (Test-Path $DBPY) { & $DBPY -c "import sys; from importlib.metadata import version; print('python', sys.version.split()[0], '| databricks-connect', version('databricks-connect'))" } else { "STOP: environment py312 not found in the Miniforge folder" }
"profiles: " + ((Select-String -Path "$env:USERPROFILE\.databrickscfg" -Pattern '^\[(.+)\]$' | ForEach-Object { $_.Matches[0].Groups[1].Value }) -join ', ')
If CV_READONLY is not in the list: STOP and report.

STEP 2 - read-only tests (about a minute)
$env:DATABRICKS_CONFIG_PROFILE = 'CV_READONLY'
@'
import sys
from databricks.connect import DatabricksSession

KEYS = (("auth", ("credential", "auth", "401", "unauthenticated", "token", "oauth")),
        ("permission", ("permission_denied", "permission", "insufficient", "403", "not authorized", "scope")),
        ("not_found", ("not_found", "not found", "does not exist", "cannot be found")),
        ("dbfs_blocked", ("dbfs", "filestore", "not supported", "unsupported", "public dbfs root")),
        ("version", ("python version", "version mismatch", "incompatible")),
        ("network", ("timed out", "timeout", "connection", "unreachable", "proxy", "ssl", "certificate")))


def kind(exc):
    text = str(exc).lower()
    found = [name for name, words in KEYS if any(word in text for word in words)]
    return type(exc).__name__ + (" [" + ", ".join(found) + "]" if found else "")


try:
    spark = DatabricksSession.builder.profile("CV_READONLY").serverless(True).getOrCreate()
    print("TEST 1 connect: OK | spark", spark.version)
except Exception as exc:
    print("TEST 1 connect: FAILED |", kind(exc))
    sys.exit(0)

try:
    columns = spark.table("bh_nan_pred.nan_pred_base_new").columns
    print("TEST 2 source table: OK | columns", len(columns))
except Exception as exc:
    print("TEST 2 source table: FAILED |", kind(exc))

for name in ("provider_type_desc", "provider_speciality_desc"):
    try:
        rows = spark.read.format("delta").load("dbfs:/FileStore/lookup_files/" + name).count()
        print("TEST 3 lookup", name + ": OK | rows", rows)
    except Exception as exc:
        print("TEST 3 lookup", name + ": FAILED |", kind(exc))
'@ | & $DBPY -

REPORT
Reply with exactly this template, filled in, and nothing else:
STEP 1: <lines>
STEP 2 tests: <every line printed>
STOPPED AT: <step and reason, or "completed">
