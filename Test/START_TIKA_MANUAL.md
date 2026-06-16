# Manual Tika Startup Commands

## The Problem
The automated scripts have issues. Here's the **simple manual way** to start Tika servers.

## Solution: Start Tika Servers Manually

### Step 1: Set Java Environment
```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
```

### Step 2: Navigate to Project Directory
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
```

### Step 3: Start Tika Servers (One Command)

**Copy and paste this entire block:**

```powershell
# Start 7 Tika servers
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","9998" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","9999" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10000" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10002" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10003" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10004" -WindowStyle Minimized
Start-Sleep -Seconds 2
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10005" -WindowStyle Minimized

Write-Host "Tika servers starting on ports: 9998, 9999, 10000, 10002, 10003, 10004, 10005" -ForegroundColor Green
Write-Host "Wait 10 seconds for them to initialize..." -ForegroundColor Yellow
```

### Step 4: Wait and Verify

Wait 10 seconds, then test:
```powershell
curl http://localhost:9998/tika
```

Should return: `Apache Tika 2.9.2`

---

## Next Steps (After Tika is Running)

### Initialize the System
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
python src/main.py init
```

### Start Processing
```powershell
python src/main.py start
```

### Open Dashboard (New Terminal)
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
streamlit run src/ui/dashboard.py
```

---

## Quick Copy-Paste Version

**All in one block (after setting Java env):**

```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","9998" -WindowStyle Minimized; Start-Sleep -Seconds 2; Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","9999" -WindowStyle Minimized; Start-Sleep -Seconds 2; Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10000" -WindowStyle Minimized; Start-Sleep -Seconds 2; Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10002" -WindowStyle Minimized; Start-Sleep -Seconds 2; Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10003" -WindowStyle Minimized; Start-Sleep -Seconds 2; Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10004" -WindowStyle Minimized; Start-Sleep -Seconds 2; Start-Process java -ArgumentList "-jar","tika\tika-server-2.9.2.jar","--port","10005" -WindowStyle Minimized; Write-Host "Tika servers started!" -ForegroundColor Green
```

Then wait 10 seconds and verify:
```powershell
curl http://localhost:9998/tika
```
