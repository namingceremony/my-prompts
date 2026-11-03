
You are in VS Code on Windows (PowerShell terminal). Set up a separate Python 3.12 environment for Databricks Connect and test, with READ-ONLY queries, that VS Code can reach Databricks serverless compute. Act as an operator: follow the steps exactly and report with the template.

RULES
1. READ ONLY in Databricks. Never write, save, create, insert, merge, alter, drop or delete anything in Databricks. In particular bh_nan_pred.nan_pred_base_new and the bh_nan_pred schema are read-only: this rule may not be broken for any reason. Run only the code given below.
2. Do not edit, create or delete any file in the repository. Do not change the existing Python environment or any other venv; install packages only into the new venv of STEP 1.
3. Never print or report the workspace address, tokens, user names, e-mail addresses, URLs or data values. Report counts, versions, profile names and error types only. Replace the Windows user name in any path with <USER>.
4. Do not commit or push. If a step fails or prints a line starting with STOP, STOP and report that step's lines only, with any URL, address or name replaced by <VALUE>.
5. Report every line each step prints, exactly as printed; do not summarise.

BEFORE YOU START (the user does this by hand, not you): in the Databricks VS Code extension, sign in to the workspace and choose Serverless as compute.

STEP 0 - Python 3.12
py -3.12 --version
If this fails (Python 3.12 not found): STOP and report.

STEP 1 - the new environment (a few minutes)
$DBENV = "$env:USERPROFILE\venvs\dbconnect"
if (-not (Test-Path "$DBENV\Scripts\python.exe")) { py -3.12 -m venv $DBENV }
$DBPY = "$DBENV\Scripts\python.exe"
& $DBPY -m pip install --quiet databricks-connect pandas
& $DBPY -c "import sys; from importlib.metadata import version; print('python', sys.version.split()[0], '| databricks-connect', version('databricks-connect'), '| pandas', version('pandas'))"
If pip fails: STOP and report only the last line of the pip output, with any URL replaced by <VALUE>.

STEP 2 - sign-in profile (names only, never values)
if (Test-Path "$env:USERPROFILE\.databrickscfg") { "profiles: " + ((Select-String -Path "$env:USERPROFILE\.databrickscfg" -Pattern '^\[(.+)\]$' | ForEach-Object { $_.Matches[0].Groups[1].Value }) -join ', ') } else { "profiles: no .databrickscfg file" }
If the list does not contain DEFAULT but contains exactly one profile, run:
$env:DATABRICKS_CONFIG_PROFILE = '<that profile name>'
If there is no .databrickscfg file, continue anyway: the extension may provide the sign-in.

STEP 3 - connection test (read-only, about a minute)
@'
import sys
from databricks.connect import DatabricksSession

KEYS = (("auth", ("credential", "auth", "401", "unauthenticated", "token")),
        ("permission", ("permission_denied", "permission", "insufficient", "403", "not authorized")),
        ("not_found", ("not_found", "not found", "does not exist", "cannot be found")),
        ("dbfs_blocked", ("dbfs", "filestore", "not supported", "unsupported", "public dbfs root")),
        ("version", ("python version", "version mismatch", "incompatible")))


def kind(exc):
    text = str(exc).lower()
    found = [name for name, words in KEYS if any(word in text for word in words)]
    return type(exc).__name__ + (" [" + ", ".join(found) + "]" if found else "")


try:
    spark = DatabricksSession.builder.serverless(True).getOrCreate()
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
STEP 0 python: <line>
STEP 1 environment: <line>
STEP 2 profiles: <line> | DATABRICKS_CONFIG_PROFILE set: <no / yes, profile name>
STEP 3 tests: <every line printed>
STOPPED AT: <step and reason, or "completed">
