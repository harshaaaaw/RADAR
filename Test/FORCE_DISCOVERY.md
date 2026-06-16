# Quick Fix - Force Fresh Discovery

## Problem
The system skipped discovery because it thinks it's already complete from a previous run.

## Solution

### Option 1: Delete the Queue Database (Recommended)
```powershell
# Stop the system (Ctrl+C in the python terminal)

# Delete the old queue database
Remove-Item C:\DocumentSearch\queue\queues.db -Force

# Restart the system
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
python src/main.py start
```

### Option 2: Use Init Command
```powershell
# Stop the system (Ctrl+C)

# Re-initialize (clears queues)
python src/main.py init

# Start again
python src/main.py start
```

---

## What This Does

- Clears the old queue database
- Forces fresh discovery of all 500 new files
- Starts processing from scratch

---

## After Restart, You Should See

```
Spawning 1 discovery workers...
  Started discovery-1 (PID: XXXX)
```

Then the discovery worker will find all 500 files and queue them for processing!

---

**Use Option 1 (delete queues.db) for fastest results!**
