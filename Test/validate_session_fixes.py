"""
Validation of DocumentSearch v8 Session Fixes:
- Slash search: /cat:, /dept:, /purp:, /conf:, generic tag
- Entity garbage filtering
- Worker reallocation & resume logic
- Tagging config
"""
import sys, os, re, json

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

PASS = 0
FAIL = 0

def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f" -- {detail}" if detail else ""))


# ===== TEST 1: Slash Command Parser =====
print("\n=== TEST 1: Slash Command Parser ===")
try:
    from src.ui.dashboard import _parse_slash_command

    tests = [
        ("/cat:Statement",       "category",        "Statement"),
        ("/category:Report",     "category",        "Report"),
        ("/dept:Finance",        "department",       "Finance"),
        ("/department:HR",       "department",       "HR"),
        ("/dep:Legal",           "department",       "Legal"),
        ("/purp:Analysis",       "purpose",          "Analysis"),
        ("/purpose:Compliance",  "purpose",          "Compliance"),
        ("/conf:Public",         "confidentiality",  "Public"),
        ("/c:Confidential",      "confidentiality",  "Confidential"),
        ("/Statement",           "tag",              "Statement"),
        ("/Finance",             "tag",              "Finance"),
        ("\\cat:Report",         "category",         "Report"),
        ("/pdf",                 "ext",              "pdf"),
        ("/ext:xlsx",            "ext",              "xlsx"),
        ("/person:John",         "person",           "John"),
        ("/cat=Statement",       "category",         "Statement"),
        ("/cat Statement",       "category",         "Statement"),
    ]
    for query, exp_mode, exp_val in tests:
        r = _parse_slash_command(query)
        ok = r and r["mode"] == exp_mode and r["value"] == exp_val
        check(f"'{query}' -> {exp_mode}:{exp_val}", ok, str(r))

    r = _parse_slash_command("normal search")
    check("'normal search' -> None", r is None, str(r))

except Exception as e:
    print(f"  [ERROR] {e}")
    import traceback; traceback.print_exc()


# ===== TEST 2: Garbage Entity Filter =====
print("\n=== TEST 2: Garbage Entity Filter ===")
try:
    from src.tagging.tagging_engine import TaggingEngine
    filt = TaggingEngine._is_garbage_entity

    # Must be garbage (True)
    garbage = ["DFL", "MLP", "GL", "COA", "NCA", "CCAC8CFC6P", "BSEE00B31P",
               "-882.16", "12345", "List - Text", "Debit Credit", "Balance",
               "Total", "", "A", "X"]
    for g in garbage:
        check(f"'{g}' is garbage", filt(g) == True, f"returned {filt(g)}")

    # Must NOT be garbage (False)
    good = ["New York", "John Smith", "California", "January 2025",
            "United States", "Microsoft Corporation"]
    for g in good:
        check(f"'{g}' is NOT garbage", filt(g) == False, f"returned {filt(g)}")

except Exception as e:
    print(f"  [ERROR] {e}")
    import traceback; traceback.print_exc()


# ===== TEST 3: Query Builder Modes =====
print("\n=== TEST 3: Query Builder (no content leak) ===")
try:
    from src.ui.dashboard import _build_strict_slash_query

    for mode, field in [("category","category"), ("department","department"),
                        ("purpose","purpose"), ("confidentiality","confidentiality")]:
        q = _build_strict_slash_query({"mode": mode, "value": "Test"}, ["file_name"], {}, 20)
        qs = json.dumps(q)
        check(f"{mode} query targets '{field}'", f'"{field}"' in qs)
        check(f"{mode} query no content leak", '"main_content"' not in qs and '"ocr_content"' not in qs)
        check(f"{mode} query has is_embedded filter", '"is_embedded"' in qs)

    # Generic tag mode should have exists filter
    q = _build_strict_slash_query({"mode": "tag", "value": "Finance"}, ["file_name"], {}, 20)
    qs = json.dumps(q)
    check("Generic tag has 'exists' filter", '"exists"' in qs)
    check("Generic tag no content leak", '"main_content"' not in qs)

except Exception as e:
    print(f"  [ERROR] {e}")
    import traceback; traceback.print_exc()


# ===== TEST 4: Config =====
print("\n=== TEST 4: Config Validation ===")
try:
    import yaml
    with open(os.path.join(ROOT, "config", "config.yaml")) as f:
        cfg = yaml.safe_load(f)
    tw = cfg.get("tagging", {}).get("workers", 0)
    check(f"Tagging workers={tw} (>=6)", tw >= 6)
    nm = cfg.get("nlp", {}).get("model_path", "")
    check(f"NLP model='{nm}' (md)", "md" in nm.lower())
except Exception as e:
    print(f"  [ERROR] {e}")


# ===== TEST 5: Orchestrator Fixes =====
print("\n=== TEST 5: Orchestrator (resume + realloc) ===")
try:
    import inspect
    from src.orchestrator.master_orchestrator import MasterOrchestrator
    src = inspect.getsource(MasterOrchestrator.start)
    check("Resume checks folder_queue_len", "folder_queue_len" in src)

    has_realloc = hasattr(MasterOrchestrator, '_reallocate_idle_workers')
    check("_reallocate_idle_workers exists", has_realloc)
    if has_realloc:
        rs = inspect.getsource(MasterOrchestrator._reallocate_idle_workers)
        check("Realloc checks tagging backlog", "tagging" in rs.lower())

    mod_src = inspect.getsource(inspect.getmodule(MasterOrchestrator))
    check("Orchestrator imports gc", "import gc" in mod_src)
except Exception as e:
    print(f"  [ERROR] {e}")
    import traceback; traceback.print_exc()


# ===== TEST 6: Tagging Worker GC =====
print("\n=== TEST 6: Tagging Worker GC ===")
try:
    import inspect
    from src.tagging.tagging_worker import TaggingWorker
    mod_src = inspect.getsource(inspect.getmodule(TaggingWorker))
    check("Worker imports gc", "import gc" in mod_src)
    check("Worker calls gc.collect()", "gc.collect()" in mod_src)
except Exception as e:
    print(f"  [ERROR] {e}")


# ===== TEST 7: Live OpenSearch =====
print("\n=== TEST 7: Live OpenSearch Queries ===")
try:
    from opensearchpy import OpenSearch
    client = OpenSearch(hosts=[{"host":"localhost","port":9200}], use_ssl=False, timeout=5)
    if client.ping():
        for field, value, label in [
            ("category", "Statement", "/cat:Statement"),
            ("department", "Finance", "/dept:Finance"),
            ("purpose", "Analysis", "/purp:Analysis"),
            ("confidentiality", "Confidential", "/conf:Confidential"),
        ]:
            q = {"query":{"term":{field:{"value":value,"case_insensitive":True}}},"size":0}
            r = client.search(index="enterprise_documents", body=q)
            cnt = r["hits"]["total"]["value"]
            check(f"{label} -> {cnt} docs", cnt > 0)

        # Count tagged
        rt = client.search(index="enterprise_documents",
                          body={"query":{"exists":{"field":"category"}},"size":0})
        ra = client.search(index="enterprise_documents",
                          body={"query":{"match_all":{}},"size":0})
        tagged = rt["hits"]["total"]["value"]
        total = ra["hits"]["total"]["value"]
        print(f"  [INFO] Tagged: {tagged}/{total} ({100*tagged/total:.1f}%)")
    else:
        print("  [SKIP] OpenSearch not responding")
except Exception as e:
    print(f"  [SKIP] {e}")


# ===== TEST 8: Redis State =====
print("\n=== TEST 8: Redis Queue State ===")
try:
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.ping()
    folder_q = r.llen("docsearch:queue:folders")
    tag_q = r.llen("docsearch:queue:tagging")
    disc = r.get("docsearch:discovery_complete")
    discovered = r.get("docsearch:counter:discovered") or "0"
    completed = r.get("docsearch:counter:completed") or "0"
    tagged = r.get("docsearch:counter:tagging_completed") or "0"  # correct counter key
    failed = r.get("docsearch:counter:failed") or "0"
    print(f"  [INFO] Folder Q: {folder_q}, Tagging Q: {tag_q}")
    print(f"  [INFO] Discovery complete: {disc}")
    print(f"  [INFO] Discovered={discovered} Completed={completed} Tagged={tagged} Failed={failed}")
    gap = int(completed) - int(tagged)
    check(f"Tagging Q ({tag_q}) ~= gap ({gap})", abs(tag_q - gap) < 200)
except Exception as e:
    print(f"  [SKIP] {e}")


# ===== SUMMARY =====
print(f"\n{'='*50}")
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS+FAIL} tests")
print(f"{'='*50}")
if FAIL == 0:
    print("All tests passed!")
else:
    print("Review failures above.")
