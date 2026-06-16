# OpenSearch Fixed - Ready to Start!

## What Was Wrong
OpenSearch 2.14.0 has security (SSL) enabled by default, but no certificates were configured.

## What I Fixed
Added this line to `opensearch.yml`:
```yaml
plugins.security.disabled: true
```

This disables security for local testing.

## Now Start OpenSearch

Open a **new terminal** and run:

```powershell
cd C:\Users\DELL\Downloads\opensearch-2.14.0-windows-x64\opensearch-2.14.0\bin
.\opensearch.bat
```

**Wait ~60 seconds** until you see messages like:
- "Node started"
- "Cluster health status changed from RED to GREEN"

## Verify It's Running

In another terminal:
```powershell
curl http://localhost:9200
```

You should see JSON output with OpenSearch version info.

## Next Steps

Once OpenSearch is running:

1. **Start Tika** (Terminal 2):
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
cd bin
.\start_tika.bat
```

2. **Initialize System** (Terminal 3):
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot"
$env:Path += ";C:\Program Files\Eclipse Adoptium\jdk-25.0.2.10-hotspot\bin"
python src/main.py init
python src/main.py start
```

3. **Open Dashboard** (Terminal 4):
```powershell
cd C:\Users\DELL\Downloads\DocumentSearch\DocumentSearch
streamlit run src/ui/dashboard.py
```

---

## Important Notes

⚠️ **Security is disabled** - This is fine for local testing but NOT for production!

✅ **OpenSearch should now start without SSL errors**

🚀 **You're ready to run the document search system!**
