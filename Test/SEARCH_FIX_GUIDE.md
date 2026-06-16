# 🔍 **SEARCH ISSUES FIX GUIDE**

**Date:** 2026-02-05  
**Status:** ✅ **Fixes Applied in Code**

---

## 🚨 **SUMMARY OF ISSUES**

1.  **"Nested Items" Error**: Searching with long sentences caused system errors.
    *   **Reason:** The field `embedded_files` was mapped as `type: nested`, which conflicts with standard full-text queries.
    *   **Fix:** Changed mapping to `type: object` and excluded it from basic search queries.

2.  **Excel/DOCX Content Not Found**:
    *   **Reason 1 (Keyword Limit):** The exact-match field (`.keyword`) was limited to 256 characters. Excel cells often exceed this, causing them to be ignored for exact matching.
    *   **Reason 2 (Stop Words):** Common words (the, a, is, to) were stripped out by the analyzer, making exact searches failed.
    *   **Reason 3 (Query Type):** The search logic was using `match_phrase` on keyword fields, which is incorrect. Terms need `term` queries.

---

## ✅ **APPLIED FIXES**

### **1. Mapping Updates (`src/indexing/opensearch_client.py`)**
*   **Increased Keyword Limit:** `ignore_above` increased from **256** to **8192** characters.
    *   *Result:* Long Excel cell values are now fully indexed and searchable.
*   **Fixed Field Type:** Changed `embedded_files` from `nested` to `object`.
    *   *Result:* Disables the "nested items" error when searching.
*   **Improved Analysis:** Removed `stop` word filter.
    *   *Result:* Searching "To be or not" will now work accurately.

### **2. Query Logic Updates (`src/api/query_builder.py`)**
*   **Exact Matching:** Updated to use `term` queries for keyword fields.
    *   *Result:* 100% accurate matching for IDs, codes, and exact cell values.
*   **Safety Checks:** Added logic to exclude sensitive fields and truncate extremely long queries (>5000 chars) to prevent crashes.

---

## 🚀 **HOW TO APPLY THE FIXES**

**IMPORTANT:** These changes require re-creating the OpenSearch index. You must follow these steps to see the results.

### **Step 1: Stop the System**
```powershell
python src/main.py stop
```

### **Step 2: Delete Old Index (Required for Mapping Changes)**
You can use `curl` or the Python script below.

**Option A (Curl):**
```bash
curl -X DELETE "http://localhost:9200/enterprise_documents"
```

**Option B (Python Helper):**
Create a file `reset_index.py`:
```python
from indexing.opensearch_client import OpenSearchClient
client = OpenSearchClient()
client.client.indices.delete(index="enterprise_documents", ignore=[400, 404])
print("Index deleted successfully.")
```
Run it: `python reset_index.py`

### **Step 3: Restart System**
```powershell
python src/main.py start
```
*The system will automatically create the NEW index with the FIXED mapping upon startup.*

### **Step 4: Re-Index Documents**
Since the index was deleted, you need to re-scan your documents.
```powershell
python src/main.py start --mode full
```

---

## 🎯 **VERIFICATION**

After re-indexing, try these searches:

1.  **Long Sentence:** Copy a paragraph (>50 words) from a document and search it.
    *   *Expected:* No error, accurate results.
2.  **Excel Value:** Search for a specific cell value like `Total Revenue Q3 2024`.
    *   *Expected:* Document found at top of results.
3.  **Exact Phrase:** Search `"to be or not to be"` (with quotes).
    *   *Expected:* Matches exact phrase including stop words.

---
**Fixes are implemented in the specific source files. Run the steps above to apply them.**
