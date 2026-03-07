# --- Trinetra: Run everything locally (Windows) ---

# Script path: C:\Users\Mahathi\Projects\trinethra\trinethra\run_all.ps1
# Outer repo root should be: C:\Users\Mahathi\Projects\trinethra
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $root

# Venv is inside inner trinethra/
$py = Join-Path $root "trinethra\.venv\Scripts\python.exe"

# model_service (8002)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\trinethra\services\model_service`"; & `"$py`" -m uvicorn app.main:app --reload --port 8002"

# automation_api (8003)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\trinethra\services\automation_api`"; & `"$py`" -m uvicorn app.main:app --reload --port 8003"

# explain_service (8001)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\trinethra\services\explain_service`"; & `"$py`" -m uvicorn app.main:app --reload --port 8001"

# monitoring_service (8004)  ✅ ADD THIS
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\trinethra\services\monitoring_service`"; & `"$py`" -m uvicorn app.main:app --reload --port 8004"

# ui (3000)
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd `"$root\ui`"; npm run dev"