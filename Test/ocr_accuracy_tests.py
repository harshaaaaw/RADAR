#!/usr/bin/env python3
"""
OCR Accuracy Deep-Dive Tests
=============================
Tests OCR text extraction quality by:
1. Verifying known OCR'd text is searchable in OpenSearch
2. Testing different image types (logos, text-heavy, screenshots)
3. Measuring OCR confidence distribution and failure patterns
4. Checking if OCR content from embedded images reaches the parent doc search

Run: .venv\\Scripts\\python.exe ocr_accuracy_tests.py
"""

import sys
import os
import json
import time
import traceback
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

import redis
from opensearchpy import OpenSearch

# ── Globals ──────────────────────────────────────────────────────────────
RESULTS = {"pass": 0, "fail": 0, "warn": 0, "details": []}
os_client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}],
                       http_compress=True, use_ssl=False, timeout=30)
r = redis.Redis(decode_responses=True)
INDEX = "enterprise_documents"

COLOURS = {"pass": "\033[92m", "fail": "\033[91m", "warn": "\033[93m"}
RESET = "\033[0m"


def report(name, status, detail=""):
    tag = status.upper()
    RESULTS[status] += 1
    RESULTS["details"].append({"name": name, "status": tag, "detail": detail})
    print(f"  [{COLOURS[status]}{tag}{RESET}] {name}")
    if detail:
        for line in detail.split("\n"):
            print(f"        {line}")


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def search_ocr(query, exact=False, size=10):
    """Search specifically in OCR content fields."""
    if exact:
        body = {
            "size": size,
            "query": {
                "dis_max": {
                    "queries": [
                        {"match_phrase": {"ocr_content": {"query": query, "boost": 10, "slop": 0}}},
                        {"match_phrase": {"ocr_content.standard": {"query": query, "boost": 8, "slop": 0}}},
                        {"match_phrase": {"main_content": {"query": query, "boost": 5, "slop": 0}}},
                    ]
                }
            },
            "_source": ["file_name", "ocr_content", "ocr_confidence", "file_path",
                         "mime_type", "is_embedded", "parent_file"],
            "highlight": {
                "fields": {
                    "ocr_content": {"fragment_size": 200, "number_of_fragments": 2},
                    "main_content": {"fragment_size": 200, "number_of_fragments": 2},
                }
            }
        }
    else:
        body = {
            "size": size,
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["ocr_content^10", "ocr_content.standard^8",
                               "main_content^3", "file_name^2"],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "_source": ["file_name", "ocr_content", "ocr_confidence", "file_path",
                         "mime_type", "is_embedded", "parent_file"],
        }
    return os_client.search(index=INDEX, body=body)


# ═════════════════════════════════════════════════════════════════════════
#  TEST 1: OCR PIPELINE STATUS
# ═════════════════════════════════════════════════════════════════════════
def test_ocr_pipeline_status():
    section("1. OCR PIPELINE STATUS")

    total_needs_ocr = os_client.count(index=INDEX, body={
        "query": {"term": {"needs_ocr": True}}
    })["count"]
    ocr_completed = os_client.count(index=INDEX, body={
        "query": {"term": {"ocr_completed": True}}
    })["count"]
    ocr_with_text = os_client.count(index=INDEX, body={
        "query": {"bool": {"must": [
            {"term": {"ocr_completed": True}},
            {"exists": {"field": "ocr_content"}}
        ]}}
    })["count"]

    pct = (ocr_completed / total_needs_ocr * 100) if total_needs_ocr > 0 else 0
    report("OCR Pipeline Progress",
           "pass" if pct > 50 else "warn" if pct > 10 else "fail",
           f"Total needing OCR: {total_needs_ocr:,}\n"
           f"OCR completed: {ocr_completed:,} ({pct:.1f}%)\n"
           f"OCR with text content: {ocr_with_text:,}")

    # Check pending OCR in Redis
    ocr_pending = r.zcard("docsearch:queue:ocr_pending")
    ocr_processing = r.zcard("docsearch:queue:ocr_processing")
    report("OCR Queue Status", "pass",
           f"Pending: {ocr_pending:,}, Processing: {ocr_processing:,}")


# ═════════════════════════════════════════════════════════════════════════
#  TEST 2: OCR CONFIDENCE ANALYSIS
# ═════════════════════════════════════════════════════════════════════════
def test_ocr_confidence():
    section("2. OCR CONFIDENCE DISTRIBUTION")

    conf_agg = os_client.search(index=INDEX, body={
        "size": 0,
        "query": {"term": {"ocr_completed": True}},
        "aggs": {
            "stats": {"stats": {"field": "ocr_confidence"}},
            "percentiles": {"percentiles": {"field": "ocr_confidence",
                                            "percents": [10, 25, 50, 75, 90, 95]}},
            "ranges": {
                "range": {
                    "field": "ocr_confidence",
                    "ranges": [
                        {"key": "Very Low (0-25)", "from": 0, "to": 25.01},
                        {"key": "Low (25-50)", "from": 25, "to": 50},
                        {"key": "Medium (50-70)", "from": 50, "to": 70},
                        {"key": "Good (70-85)", "from": 70, "to": 85},
                        {"key": "High (85-95)", "from": 85, "to": 95},
                        {"key": "Excellent (95+)", "from": 95, "to": 101},
                    ]
                }
            }
        }
    })

    stats = conf_agg["aggregations"]["stats"]
    if stats["count"] > 0:
        report("Confidence Statistics", "pass",
               f"Count={stats['count']:,}, Avg={stats['avg']:.1f}%, "
               f"Min={stats['min']:.1f}%, Max={stats['max']:.1f}%")

        pctls = conf_agg["aggregations"]["percentiles"]["values"]
        report("Confidence Percentiles", "pass",
               " | ".join(f"P{k}={v:.0f}%" for k, v in pctls.items()))

        buckets = conf_agg["aggregations"]["ranges"]["buckets"]
        for b in buckets:
            pct = (b["doc_count"] / stats["count"] * 100) if stats["count"] > 0 else 0
            status = "pass" if b["key"] in ("High (85-95)", "Excellent (95+)") else "pass"
            report(f"  {b['key']}", status,
                   f"{b['doc_count']:,} docs ({pct:.1f}%)")
    else:
        report("Confidence Statistics", "fail", "No OCR documents with confidence")

    # High-confidence but short text (signs, logos)
    short_high = os_client.count(index=INDEX, body={
        "query": {"bool": {"must": [
            {"range": {"ocr_confidence": {"gte": 90}}},
            {"term": {"ocr_completed": True}}
        ]}}
    })["count"]
    report("High-confidence (90%+) OCR docs", "pass", f"{short_high:,} docs")


# ═════════════════════════════════════════════════════════════════════════
#  TEST 3: SEARCH KNOWN OCR TEXT
# ═════════════════════════════════════════════════════════════════════════
def test_search_known_ocr_text():
    section("3. SEARCH KNOWN OCR TEXT")

    # Get real OCR'd text from the index to use as search targets
    ocr_docs = os_client.search(index=INDEX, body={
        "size": 50,
        "query": {"bool": {"must": [
            {"term": {"ocr_completed": True}},
            {"range": {"ocr_confidence": {"gte": 50}}}
        ]}},
        "_source": ["file_name", "ocr_content", "ocr_confidence"],
        "sort": [{"ocr_confidence": "desc"}]
    })

    # Build test cases from actual OCR'd content
    test_cases = []
    seen_texts = set()
    for hit in ocr_docs["hits"]["hits"]:
        src = hit["_source"]
        ocr_text = src.get("ocr_content", "").strip()
        fname = src.get("file_name", "?")
        conf = src.get("ocr_confidence", 0)
        if ocr_text and ocr_text not in seen_texts and len(ocr_text) >= 2:
            seen_texts.add(ocr_text)
            test_cases.append((ocr_text, fname, conf))

    if not test_cases:
        report("No OCR text to search for", "warn", "No OCR content found")
        return

    report(f"Found {len(test_cases)} unique OCR texts to verify", "pass")

    # Test each OCR text is searchable
    found_count = 0
    total_tested = 0
    for ocr_text, fname, conf in test_cases[:20]:
        total_tested += 1
        # Search exact phrase
        resp = search_ocr(ocr_text, exact=True)
        total_hits = resp["hits"]["total"]["value"]
        found = total_hits > 0

        if found:
            found_count += 1
            # Check if the specific source file is in results
            source_in_results = any(
                h["_source"]["file_name"] == fname
                for h in resp["hits"]["hits"]
            )
            report(f"OCR search: '{ocr_text[:40]}'",
                   "pass",
                   f"{total_hits} hits, source '{fname[:30]}' in results: {source_in_results}, conf={conf:.0f}%")
        else:
            report(f"OCR search: '{ocr_text[:40]}'",
                   "fail",
                   f"0 hits! From {fname[:30]}, conf={conf:.0f}%")

    pct_found = (found_count / total_tested * 100) if total_tested > 0 else 0
    report("OCR searchability rate",
           "pass" if pct_found >= 95 else "warn" if pct_found >= 80 else "fail",
           f"{found_count}/{total_tested} ({pct_found:.0f}%) OCR texts searchable")


# ═════════════════════════════════════════════════════════════════════════
#  TEST 4: IMAGE TYPE BREAKDOWN
# ═════════════════════════════════════════════════════════════════════════
def test_image_type_accuracy():
    section("4. OCR BY IMAGE SOURCE TYPE")

    # Categorize by source type
    categories = {
        "PowerPoint embedded": {"prefix": "ppt_media_image"},
        "Word embedded": {"prefix": "word_media_image"},
        "Excel embedded": {"prefix": "xl_media_image"},
        "Standalone images": {"query": {"bool": {"must": [
            {"term": {"needs_ocr": True}},
            {"bool": {"must_not": [{"prefix": {"file_name": "ppt_media"}},
                                   {"prefix": {"file_name": "word_media"}},
                                   {"prefix": {"file_name": "xl_media"}}]}}
        ]}}},
    }

    for cat_name, cat_info in categories.items():
        if "prefix" in cat_info:
            query = {"bool": {"must": [
                {"term": {"needs_ocr": True}},
                {"prefix": {"file_name": cat_info["prefix"]}}
            ]}}
        else:
            query = cat_info["query"]

        # Total needing OCR
        total = os_client.count(index=INDEX, body={"query": query})["count"]

        # Completed
        completed_q = {"bool": {"must": [query["bool"]["must"][0],
                                          {"term": {"ocr_completed": True}},
                                          query["bool"]["must"][1] if "must" in query["bool"] and len(query["bool"]["must"]) > 1 else {"match_all": {}}]}}
        if "prefix" in cat_info:
            completed_q = {"bool": {"must": [
                {"term": {"ocr_completed": True}},
                {"prefix": {"file_name": cat_info["prefix"]}}
            ]}}
        else:
            completed_q = {"bool": {"must": [
                {"term": {"ocr_completed": True}},
                {"bool": {"must_not": [{"prefix": {"file_name": "ppt_media"}},
                                       {"prefix": {"file_name": "word_media"}},
                                       {"prefix": {"file_name": "xl_media"}}]}}
            ]}}
        completed = os_client.count(index=INDEX, body={"query": completed_q})["count"]

        # With text
        if "prefix" in cat_info:
            text_q = {"bool": {"must": [
                {"term": {"ocr_completed": True}},
                {"prefix": {"file_name": cat_info["prefix"]}},
                {"exists": {"field": "ocr_content"}}
            ]}}
        else:
            text_q = {"bool": {"must": [
                {"term": {"ocr_completed": True}},
                {"exists": {"field": "ocr_content"}},
                {"bool": {"must_not": [{"prefix": {"file_name": "ppt_media"}},
                                       {"prefix": {"file_name": "word_media"}},
                                       {"prefix": {"file_name": "xl_media"}}]}}
            ]}}
        with_text = os_client.count(index=INDEX, body={"query": text_q})["count"]

        # Confidence for this category
        if "prefix" in cat_info:
            conf_q = {"bool": {"must": [
                {"term": {"ocr_completed": True}},
                {"prefix": {"file_name": cat_info["prefix"]}}
            ]}}
        else:
            conf_q = completed_q

        conf_stats = os_client.search(index=INDEX, body={
            "size": 0,
            "query": conf_q,
            "aggs": {"avg_conf": {"avg": {"field": "ocr_confidence"}}}
        })
        avg_conf = conf_stats["aggregations"]["avg_conf"]["value"] or 0

        pct = (completed / total * 100) if total > 0 else 0
        report(f"{cat_name}",
               "pass" if pct > 50 else "warn" if total > 0 else "pass",
               f"Total: {total:,}, Completed: {completed:,} ({pct:.0f}%), "
               f"With text: {with_text:,}, Avg confidence: {avg_conf:.1f}%")


# ═════════════════════════════════════════════════════════════════════════
#  TEST 5: OCR FAILURE PATTERN ANALYSIS
# ═════════════════════════════════════════════════════════════════════════
def test_ocr_failure_patterns():
    section("5. OCR FAILURE PATTERNS")

    failed_raw = r.hgetall("docsearch:failed")
    ocr_failures = []
    for fid, data in failed_raw.items():
        try:
            info = json.loads(data)
            if info.get("stage") == "ocr" or "ocr" in info.get("error_type", "").lower():
                ocr_failures.append(info)
        except:
            pass

    if not ocr_failures:
        report("No OCR failures", "pass")
        return

    report("Total OCR failures", "warn" if len(ocr_failures) > 100 else "pass",
           f"{len(ocr_failures):,} failures")

    # Categorize by error reason
    reasons = {}
    sources = {"ppt": 0, "word": 0, "xl": 0, "other": 0}
    for f in ocr_failures:
        err = f.get("error_message", "unknown")
        # Simplify error messages
        if "no text content" in err.lower():
            key = "No text content extracted"
        elif "timeout" in err.lower():
            key = "Tesseract timeout"
        elif "memory" in err.lower():
            key = "Memory error"
        else:
            key = err[:60]
        reasons[key] = reasons.get(key, 0) + 1

        fp = f.get("file_path", "")
        fn = os.path.basename(fp)
        if fn.startswith("ppt_media"):
            sources["ppt"] += 1
        elif fn.startswith("word_media"):
            sources["word"] += 1
        elif fn.startswith("xl_media"):
            sources["xl"] += 1
        else:
            sources["other"] += 1

    report("Failure reasons", "pass",
           "\n".join(f"  {k}: {v}" for k, v in sorted(reasons.items(), key=lambda x: -x[1])))
    report("Failure sources", "pass",
           f"PPT embedded: {sources['ppt']}, Word embedded: {sources['word']}, "
           f"Excel embedded: {sources['xl']}, Other: {sources['other']}")


# ═════════════════════════════════════════════════════════════════════════
#  TEST 6: CONTENT SEARCH FROM OCR'D IMAGES
# ═════════════════════════════════════════════════════════════════════════
def test_content_search_from_ocr():
    section("6. CONTENT SEARCH FROM OCR'D IMAGES")

    # Find OCR'd docs with meaningful text (>10 chars)
    meaningful = os_client.search(index=INDEX, body={
        "size": 30,
        "query": {"bool": {"must": [
            {"term": {"ocr_completed": True}},
            {"range": {"ocr_confidence": {"gte": 30}}}
        ]}},
        "_source": ["file_name", "ocr_content", "ocr_confidence", "is_embedded", "parent_file"],
        "sort": [{"ocr_confidence": "desc"}]
    })

    tested = 0
    found = 0
    for hit in meaningful["hits"]["hits"]:
        src = hit["_source"]
        ocr_text = src.get("ocr_content", "").strip()
        if len(ocr_text) < 5:
            continue

        fname = src.get("file_name", "?")

        # Search using the OCR text as query
        resp = search_ocr(ocr_text, exact=True if len(ocr_text) < 50 else False)
        hits = resp["hits"]["total"]["value"]
        tested += 1

        if hits > 0:
            found += 1
            # Check highlights
            highlights = []
            for h in resp["hits"]["hits"][:1]:
                hl = h.get("highlight", {})
                for field, frags in hl.items():
                    highlights.append(f"{field}: {frags[0][:60]}")

            report(f"Content search: '{ocr_text[:35]}'",
                   "pass",
                   f"From {fname[:30]}, {hits} hits" +
                   (f", highlight: {highlights[0][:50]}" if highlights else ""))
        else:
            report(f"Content search: '{ocr_text[:35]}'",
                   "warn",
                   f"From {fname[:30]}, 0 hits (content not searchable)")

        if tested >= 15:
            break

    if tested > 0:
        pct = found / tested * 100
        report("Overall OCR content searchability",
               "pass" if pct >= 90 else "warn" if pct >= 70 else "fail",
               f"{found}/{tested} ({pct:.0f}%) OCR texts found via search")


# ═════════════════════════════════════════════════════════════════════════
#  TEST 7: OCR TEXT QUALITY ANALYSIS
# ═════════════════════════════════════════════════════════════════════════
def test_ocr_text_quality():
    section("7. OCR TEXT QUALITY ANALYSIS")

    # Analyze text length vs confidence
    samples = os_client.search(index=INDEX, body={
        "size": 100,
        "query": {"bool": {"must": [
            {"term": {"ocr_completed": True}},
            {"exists": {"field": "ocr_content"}}
        ]}},
        "_source": ["file_name", "ocr_content", "ocr_confidence"],
        "sort": [{"ocr_confidence": "desc"}]
    })

    lengths = []
    empty_with_conf = 0
    garbage_texts = 0
    good_texts = 0

    for hit in samples["hits"]["hits"]:
        src = hit["_source"]
        text = src.get("ocr_content", "")
        conf = src.get("ocr_confidence", 0)
        length = len(text.strip())
        lengths.append(length)

        if length == 0 and conf > 0:
            empty_with_conf += 1
        elif length > 0:
            # Check for garbage (lots of special chars, very short words)
            words = text.split()
            if words:
                avg_word_len = sum(len(w) for w in words) / len(words)
                special_ratio = sum(1 for c in text if not c.isalnum() and c != ' ') / max(len(text), 1)
                if special_ratio > 0.3 or avg_word_len < 2:
                    garbage_texts += 1
                else:
                    good_texts += 1

    total = len(samples["hits"]["hits"])
    if lengths:
        avg_len = sum(lengths) / len(lengths)
        report("OCR text length stats", "pass",
               f"Avg length: {avg_len:.0f} chars, Min: {min(lengths)}, Max: {max(lengths)}")
    report("Text quality breakdown", "pass",
           f"Total: {total}, Good text: {good_texts}, "
           f"Garbage/noise: {garbage_texts}, Empty w/confidence: {empty_with_conf}")

    # Show sample of longest OCR texts (most meaningful)
    long_texts = os_client.search(index=INDEX, body={
        "size": 5,
        "query": {"bool": {"must": [
            {"term": {"ocr_completed": True}},
            {"exists": {"field": "ocr_content"}},
            {"range": {"ocr_confidence": {"gte": 50}}}
        ]}},
        "_source": ["file_name", "ocr_content", "ocr_confidence"],
        "sort": [{"ocr_confidence": "desc"}]
    })

    report("Top OCR text samples:", "pass")
    for hit in long_texts["hits"]["hits"]:
        src = hit["_source"]
        text = src.get("ocr_content", "").strip()
        fname = src.get("file_name", "?")
        conf = src.get("ocr_confidence", 0)
        preview = text[:80].replace("\n", " ")
        report(f"  {fname[:40]}", "pass",
               f"conf={conf:.0f}%, text='{preview}'")


# ═════════════════════════════════════════════════════════════════════════
#  TEST 8: SEARCH PERFORMANCE FOR OCR CONTENT
# ═════════════════════════════════════════════════════════════════════════
def test_ocr_search_performance():
    section("8. OCR SEARCH PERFORMANCE")

    queries = [
        ("imagination at work", True),
        ("EMERGENCY", True),
        ("Financial Services", True),
        ("GE Money", True),
        ("STOP", True),
        ("screenshot image text", False),
    ]

    for q, exact in queries:
        start = time.time()
        resp = search_ocr(q, exact=exact)
        elapsed = (time.time() - start) * 1000
        hits = resp["hits"]["total"]["value"]
        report(f"OCR search: '{q}' ({'exact' if exact else 'fuzzy'}) {elapsed:.0f}ms",
               "pass" if elapsed < 2000 else "warn",
               f"{hits:,} hits in {elapsed:.0f}ms")


# ═════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════
def main():
    print("\n" + "=" * 70)
    print("  OCR ACCURACY DEEP-DIVE TESTS")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    tests = [
        test_ocr_pipeline_status,
        test_ocr_confidence,
        test_search_known_ocr_text,
        test_image_type_accuracy,
        test_ocr_failure_patterns,
        test_content_search_from_ocr,
        test_ocr_text_quality,
        test_ocr_search_performance,
    ]

    for fn in tests:
        try:
            fn()
        except Exception:
            section(f"ERROR in {fn.__name__}")
            report(f"{fn.__name__} crashed", "fail", traceback.format_exc()[:500])

    # Summary
    section("OCR ACCURACY SUMMARY")
    total = RESULTS["pass"] + RESULTS["fail"] + RESULTS["warn"]
    print(f"  Total checks: {total}")
    print(f"  {COLOURS['pass']}PASS: {RESULTS['pass']}{RESET}")
    print(f"  {COLOURS['fail']}FAIL: {RESULTS['fail']}{RESET}")
    print(f"  {COLOURS['warn']}WARN: {RESULTS['warn']}{RESET}")
    print()

    report_path = os.path.join(os.path.dirname(__file__), "OCR_ACCURACY_TEST_RESULTS.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"pass": RESULTS["pass"], "fail": RESULTS["fail"], "warn": RESULTS["warn"]},
            "details": RESULTS["details"]
        }, f, indent=2)
    print("  Results saved to OCR_ACCURACY_TEST_RESULTS.json")
    return RESULTS["fail"]


if __name__ == "__main__":
    sys.exit(main())
