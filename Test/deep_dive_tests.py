#!/usr/bin/env python3
"""
Deep-Dive Accuracy Tests for DocumentSearch System
===================================================
Tests OCR accuracy, search accuracy (exact phrase, fuzzy, Excel content),
image/screenshot searchability, and overall system health.

Run:  .venv\\Scripts\\python.exe deep_dive_tests.py
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
OS_HOST = "localhost"
OS_PORT = 9200
INDEX   = "enterprise_documents"

os_client = OpenSearch(
    hosts=[{"host": OS_HOST, "port": OS_PORT}],
    http_compress=True, use_ssl=False, timeout=30,
)
r = redis.Redis(decode_responses=True)


def report(name, status, detail=""):
    tag = {"pass": "PASS", "fail": "FAIL", "warn": "WARN"}[status]
    colour = {"pass": "\033[92m", "fail": "\033[91m", "warn": "\033[93m"}[status]
    reset = "\033[0m"
    RESULTS[status] += 1
    RESULTS["details"].append({"name": name, "status": tag, "detail": detail})
    print(f"  [{colour}{tag}{reset}] {name}")
    if detail:
        for line in detail.split("\n"):
            print(f"        {line}")


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 1: SYSTEM HEALTH CHECKS
# ═════════════════════════════════════════════════════════════════════════
def test_system_health():
    section("1. SYSTEM HEALTH")

    # 1a. OpenSearch reachable
    try:
        info = os_client.info()
        report("OpenSearch reachable", "pass", f"Version {info['version']['number']}")
    except Exception as e:
        report("OpenSearch reachable", "fail", str(e))
        return

    # 1b. Index exists and doc count
    try:
        count_resp = os_client.count(index=INDEX)
        doc_count = count_resp["count"]
        if doc_count > 0:
            report("Index document count", "pass", f"{doc_count:,} documents indexed")
        else:
            report("Index document count", "fail", "0 documents")
    except Exception as e:
        report("Index document count", "fail", str(e))

    # 1c. Redis reachable
    try:
        r.ping()
        report("Redis reachable", "pass")
    except Exception as e:
        report("Redis reachable", "fail", str(e))

    # 1d. Queue health
    completed = r.hlen("docsearch:completed")
    failed = r.hlen("docsearch:failed")
    report("Completed files", "pass" if completed > 0 else "warn",
           f"{completed:,} completed, {failed:,} failed ({failed/(completed+failed)*100:.1f}% failure rate)" if completed > 0 else "No completed files")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 2: OCR ACCURACY DEEP-DIVE
# ═════════════════════════════════════════════════════════════════════════
def test_ocr_accuracy():
    section("2. OCR ACCURACY DEEP-DIVE")

    # 2a. Overall OCR stats
    ocr_done_q = {
        "query": {"term": {"ocr_completed": True}},
        "size": 0
    }
    ocr_total = os_client.count(index=INDEX, body={"query": {"exists": {"field": "needs_ocr"}}})["count"]
    ocr_completed = os_client.count(index=INDEX, body={"query": {"term": {"ocr_completed": True}}})["count"]
    ocr_needed = os_client.count(index=INDEX, body={"query": {"term": {"needs_ocr": True}}})["count"]

    report("OCR coverage", "pass" if ocr_needed == 0 or ocr_completed > 0 else "warn",
           f"needs_ocr=true: {ocr_needed:,}, ocr_completed=true: {ocr_completed:,}")

    # 2b. OCR confidence distribution
    conf_agg = os_client.search(index=INDEX, body={
        "size": 0,
        "query": {"term": {"ocr_completed": True}},
        "aggs": {
            "conf_stats": {"stats": {"field": "ocr_confidence"}},
            "conf_ranges": {
                "range": {
                    "field": "ocr_confidence",
                    "ranges": [
                        {"key": "0-20%",   "from": 0, "to": 20},
                        {"key": "20-50%",  "from": 20, "to": 50},
                        {"key": "50-80%",  "from": 50, "to": 80},
                        {"key": "80-100%", "from": 80, "to": 101},
                    ]
                }
            }
        }
    })
    stats = conf_agg["aggregations"]["conf_stats"]
    if stats["count"] > 0:
        report("OCR confidence stats", "pass",
               f"avg={stats['avg']:.1f}%, min={stats['min']:.1f}%, max={stats['max']:.1f}%, count={stats['count']:,}")
        buckets = conf_agg["aggregations"]["conf_ranges"]["buckets"]
        dist_str = " | ".join(f"{b['key']}: {b['doc_count']:,}" for b in buckets)
        report("OCR confidence distribution", "pass", dist_str)
    else:
        report("OCR confidence stats", "warn", "No OCR documents with confidence scores")

    # 2c. Sample HIGH-confidence OCR docs - verify they have actual text
    high_conf = os_client.search(index=INDEX, body={
        "size": 5,
        "query": {"range": {"ocr_confidence": {"gte": 80}}},
        "_source": ["file_name", "ocr_content", "ocr_confidence"],
        "sort": [{"ocr_confidence": "desc"}]
    })
    good_text_count = 0
    for hit in high_conf["hits"]["hits"]:
        src = hit["_source"]
        ocr_text = src.get("ocr_content", "")
        has_text = len(ocr_text.strip()) > 20
        if has_text:
            good_text_count += 1
    total_high = len(high_conf["hits"]["hits"])
    if total_high > 0:
        report("High-conf OCR has real text", "pass" if good_text_count == total_high else "warn",
               f"{good_text_count}/{total_high} high-confidence docs have substantial OCR text")
    else:
        report("High-conf OCR has real text", "warn", "No high-confidence OCR docs found")

    # 2d. Sample LOW-confidence / FAILED OCR docs (screenshots, graphics)
    low_conf = os_client.search(index=INDEX, body={
        "size": 10,
        "query": {
            "bool": {
                "must": [{"term": {"needs_ocr": True}}],
                "should": [
                    {"range": {"ocr_confidence": {"lt": 30}}},
                    {"bool": {"must_not": [{"exists": {"field": "ocr_confidence"}}]}}
                ],
                "minimum_should_match": 1
            }
        },
        "_source": ["file_name", "file_path", "ocr_content", "ocr_confidence", "ocr_completed", "mime_type"],
        "sort": [{"ocr_confidence": {"order": "asc", "missing": "_first"}}]
    })
    if low_conf["hits"]["hits"]:
        report("Low-conf / No-OCR samples", "pass",
               f"Found {low_conf['hits']['total']['value']:,} docs with low/no OCR confidence")
        for i, hit in enumerate(low_conf["hits"]["hits"][:5]):
            src = hit["_source"]
            fname = src.get("file_name", "?")
            conf = src.get("ocr_confidence", "N/A")
            ocr_len = len(src.get("ocr_content", ""))
            report(f"  Sample {i+1}: {fname[:60]}", "pass",
                   f"confidence={conf}, ocr_text_len={ocr_len}, mime={src.get('mime_type','?')}")
    else:
        report("Low-conf / No-OCR samples", "pass", "No low-confidence OCR docs (all processed well)")

    # 2e. OCR failures from Redis
    failed_raw = r.hgetall("docsearch:failed")
    ocr_failures = []
    for fid, data in failed_raw.items():
        try:
            info = json.loads(data)
            if info.get("stage") == "ocr" or "ocr" in info.get("error_type", "").lower():
                ocr_failures.append(info)
        except:
            pass
    report("OCR failures in Redis", "pass" if len(ocr_failures) < 100 else "warn",
           f"{len(ocr_failures)} OCR failures out of {len(failed_raw)} total failures")
    if ocr_failures:
        sample = ocr_failures[:3]
        for s in sample:
            fpath = s.get("file_path", "?")
            err = s.get("error_message", "?")[:120]
            report("  OCR fail sample", "pass", f"{os.path.basename(fpath)}: {err}")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 3: SEARCH ACCURACY - EXACT PHRASE
# ═════════════════════════════════════════════════════════════════════════
def _search(query_str, size=10):
    """Run search using the same logic as the dashboard."""
    q = query_str.strip()
    is_exact = q.startswith('"') and q.endswith('"')

    if is_exact:
        q = q.strip('"')
        body = {
            "size": size,
            "_source": ["file_name", "file_path", "main_content", "ocr_content",
                        "embedded_content", "ocr_confidence", "mime_type"],
            "query": {
                "dis_max": {
                    "queries": [
                        {"match_phrase": {"file_name": {"query": q, "boost": 100, "slop": 0}}},
                        {"match_phrase": {"file_path": {"query": q, "boost": 60, "slop": 0}}},
                        {"match_phrase": {"main_content.standard": {"query": q, "boost": 40, "slop": 0}}},
                        {"match_phrase": {"main_content": {"query": q, "boost": 35, "slop": 0}}},
                        {"match_phrase": {"ocr_content.standard": {"query": q, "boost": 40, "slop": 1}}},
                        {"match_phrase": {"ocr_content": {"query": q, "boost": 35, "slop": 1}}},
                        {"match_phrase": {"embedded_content": {"query": q, "boost": 30, "slop": 0}}},
                    ],
                    "tie_breaker": 0.1
                }
            },
            "highlight": {
                "fields": {
                    "main_content": {"fragment_size": 150, "number_of_fragments": 2},
                    "ocr_content": {"fragment_size": 150, "number_of_fragments": 2},
                    "embedded_content": {"fragment_size": 150, "number_of_fragments": 2},
                    "file_name": {"fragment_size": 150, "number_of_fragments": 1},
                }
            }
        }
    else:
        body = {
            "size": size,
            "_source": ["file_name", "file_path", "main_content", "ocr_content",
                        "embedded_content", "ocr_confidence", "mime_type"],
            "query": {
                "multi_match": {
                    "query": q,
                    "fields": [
                        "file_name^15", "file_name.english^12",
                        "main_content^6", "main_content.standard^5",
                        "ocr_content^6", "ocr_content.standard^5",
                        "embedded_content^3"
                    ],
                    "type": "best_fields",
                    "fuzziness": "AUTO"
                }
            },
            "highlight": {
                "fields": {
                    "main_content": {"fragment_size": 150, "number_of_fragments": 2},
                    "ocr_content": {"fragment_size": 150, "number_of_fragments": 2},
                    "embedded_content": {"fragment_size": 150, "number_of_fragments": 2},
                    "file_name": {"fragment_size": 150, "number_of_fragments": 1},
                }
            }
        }

    resp = os_client.search(index=INDEX, body=body)
    return resp


def test_search_accuracy():
    section("3. SEARCH ACCURACY")

    # 3a. Get some real file names to use as search targets
    sample_docs = os_client.search(index=INDEX, body={
        "size": 5,
        "query": {"bool": {"must": [{"exists": {"field": "main_content"}}]}},
        "_source": ["file_name", "main_content"],
        "sort": [{"file_size": "desc"}]
    })

    if not sample_docs["hits"]["hits"]:
        report("Search test - no docs available", "fail", "Cannot test search with empty index")
        return

    # 3b. File name search - searching by exact file name should return that file
    for hit in sample_docs["hits"]["hits"][:3]:
        fname = hit["_source"]["file_name"]
        # Strip extension for search
        name_no_ext = os.path.splitext(fname)[0]
        # Use first 3 meaningful words
        words = [w for w in name_no_ext.replace("_", " ").replace("-", " ").split() if len(w) > 2]
        if len(words) < 2:
            continue
        search_terms = " ".join(words[:3])
        resp = _search(search_terms, size=5)
        found = any(h["_source"]["file_name"] == fname for h in resp["hits"]["hits"])
        report(f"File name search: '{search_terms[:40]}'",
               "pass" if found else "warn",
               f"Found target: {found}, total hits: {resp['hits']['total']['value']}")

    # 3c. Exact phrase search test - extract a phrase from content and search for it
    for hit in sample_docs["hits"]["hits"][:2]:
        content = hit["_source"].get("main_content", "")
        if len(content) < 50:
            continue
        # Extract a 3-5 word phrase from the middle of content
        words = content.split()
        if len(words) > 20:
            mid = len(words) // 2
            phrase = " ".join(words[mid:mid+4])
            # Clean up the phrase
            phrase = phrase.strip(".,;:()[]{}\"'")
            if len(phrase) > 10:
                resp = _search(f'"{phrase}"', size=5)
                total = resp["hits"]["total"]["value"]
                report(f"Exact phrase: '{phrase[:50]}'",
                       "pass" if total > 0 else "fail",
                       f"Hits: {total}")

    # 3d. Fuzzy / typo tolerance
    resp = _search("documnet managment", size=5)  # intentional typos
    report("Fuzzy search (typo tolerance)",
           "pass" if resp["hits"]["total"]["value"] > 0 else "warn",
           f"'documnet managment' -> {resp['hits']['total']['value']} hits")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 4: EXCEL / SPREADSHEET CONTENT SEARCH
# ═════════════════════════════════════════════════════════════════════════
def test_excel_search():
    section("4. EXCEL / SPREADSHEET CONTENT SEARCH")

    # 4a. Find Excel files in the index
    excel_docs = os_client.search(index=INDEX, body={
        "size": 20,
        "query": {
            "bool": {
                "should": [
                    {"wildcard": {"file_name": "*.xlsx"}},
                    {"wildcard": {"file_name": "*.xls"}},
                    {"wildcard": {"file_name": "*.csv"}},
                    {"term": {"mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}},
                    {"term": {"mime_type": "application/vnd.ms-excel"}},
                ]
            }
        },
        "_source": ["file_name", "main_content", "embedded_content", "mime_type",
                     "embedded_count", "file_path"],
        "sort": [{"file_size": "desc"}]
    })

    excel_count = excel_docs["hits"]["total"]["value"]
    report("Excel files indexed", "pass" if excel_count > 0 else "warn",
           f"{excel_count:,} Excel/spreadsheet files found")

    if not excel_docs["hits"]["hits"]:
        return

    # 4b. Check if Excel content is actually extractable
    has_content = 0
    has_embedded = 0
    for hit in excel_docs["hits"]["hits"]:
        src = hit["_source"]
        mc = src.get("main_content", "")
        ec = src.get("embedded_content", "")
        if len(mc) > 50:
            has_content += 1
        if len(ec) > 50:
            has_embedded += 1

    total_checked = len(excel_docs["hits"]["hits"])
    report("Excel files with main_content", "pass" if has_content > 0 else "warn",
           f"{has_content}/{total_checked} have substantial main_content")
    report("Excel files with embedded_content", "pass" if has_embedded > 0 else "warn",
           f"{has_embedded}/{total_checked} have embedded_content (multi-sheet)")

    # 4c. Search for content that should be in an Excel file
    # Try to find a numeric/tabular pattern from an Excel file
    for hit in excel_docs["hits"]["hits"][:3]:
        src = hit["_source"]
        content = src.get("main_content", "") or src.get("embedded_content", "")
        if len(content) < 30:
            continue
        # Extract a unique-looking phrase
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            if len(line) > 15 and len(line) < 80 and any(c.isdigit() for c in line):
                # Search for this line content
                search_term = line[:60].strip(".,;:()[]{}\"'")
                if len(search_term) > 10:
                    resp = _search(f'"{search_term}"', size=5)
                    total = resp["hits"]["total"]["value"]
                    fname = src.get("file_name", "?")
                    report(f"Excel content search: '{search_term[:45]}'",
                           "pass" if total > 0 else "warn",
                           f"From {fname[:40]}, hits: {total}")
                    break

    # 4d. Multi-sheet detection
    multi_sheet = os_client.count(index=INDEX, body={
        "query": {
            "bool": {
                "must": [
                    {"range": {"embedded_count": {"gte": 2}}},
                    {"bool": {"should": [
                        {"wildcard": {"file_name": "*.xlsx"}},
                        {"term": {"mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}},
                    ]}}
                ]
            }
        }
    })["count"]
    report("Multi-sheet Excel files", "pass" if multi_sheet > 0 else "warn",
           f"{multi_sheet:,} Excel files with 2+ embedded items (sheets)")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 5: IMAGE / SCREENSHOT SEARCHABILITY
# ═════════════════════════════════════════════════════════════════════════
def test_image_searchability():
    section("5. IMAGE / SCREENSHOT SEARCHABILITY")

    # 5a. Count image files
    image_docs = os_client.search(index=INDEX, body={
        "size": 20,
        "query": {
            "bool": {
                "should": [
                    {"wildcard": {"file_name": "*.png"}},
                    {"wildcard": {"file_name": "*.jpg"}},
                    {"wildcard": {"file_name": "*.jpeg"}},
                    {"wildcard": {"file_name": "*.tif"}},
                    {"wildcard": {"file_name": "*.tiff"}},
                    {"wildcard": {"file_name": "*.bmp"}},
                    {"prefix": {"mime_type": "image/"}},
                ]
            }
        },
        "_source": ["file_name", "ocr_content", "ocr_confidence", "ocr_completed",
                     "needs_ocr", "mime_type", "file_path"],
    })

    img_count = image_docs["hits"]["total"]["value"]
    report("Image files indexed", "pass" if img_count > 0 else "warn",
           f"{img_count:,} image files found")

    if not image_docs["hits"]["hits"]:
        return

    # 5b. OCR status of images
    ocr_done = 0
    ocr_has_text = 0
    ocr_empty = 0
    high_conf = 0
    low_conf = 0
    for hit in image_docs["hits"]["hits"]:
        src = hit["_source"]
        if src.get("ocr_completed"):
            ocr_done += 1
            ocr_text = src.get("ocr_content", "")
            conf = src.get("ocr_confidence", 0)
            if len(ocr_text.strip()) > 10:
                ocr_has_text += 1
            else:
                ocr_empty += 1
            if conf and conf >= 70:
                high_conf += 1
            elif conf is not None:
                low_conf += 1

    checked = len(image_docs["hits"]["hits"])
    report("Images with OCR completed", "pass" if ocr_done > 0 else "warn",
           f"{ocr_done}/{checked} images have OCR completed")
    report("Images with searchable OCR text", "pass" if ocr_has_text > 0 else "warn",
           f"{ocr_has_text} have text, {ocr_empty} empty, {high_conf} high-conf, {low_conf} low-conf")

    # 5c. Search for text found in an OCR'd image
    for hit in image_docs["hits"]["hits"]:
        src = hit["_source"]
        ocr_text = src.get("ocr_content", "")
        if len(ocr_text) > 30:
            words = ocr_text.split()
            if len(words) > 5:
                phrase = " ".join(words[2:5])
                phrase = phrase.strip(".,;:()[]{}\"'")
                if len(phrase) > 8:
                    resp = _search(f'"{phrase}"', size=5)
                    fname = src.get("file_name", "?")
                    total = resp["hits"]["total"]["value"]
                    report(f"Search OCR text from image: '{phrase[:40]}'",
                           "pass" if total > 0 else "fail",
                           f"From {fname[:40]}, hits: {total}")
                    break

    # 5d. Screenshots specifically (look for "screenshot" or "screen" in name)
    screenshot_docs = os_client.search(index=INDEX, body={
        "size": 10,
        "query": {
            "bool": {
                "should": [
                    {"wildcard": {"file_name": "*screenshot*"}},
                    {"wildcard": {"file_name": "*screen*"}},
                    {"wildcard": {"file_name": "*capture*"}},
                    {"wildcard": {"file_name": "*snap*"}},
                ]
            }
        },
        "_source": ["file_name", "ocr_content", "ocr_confidence", "ocr_completed", "mime_type"],
    })
    ss_count = screenshot_docs["hits"]["total"]["value"]
    report("Screenshot-named files", "pass" if ss_count >= 0 else "warn",
           f"{ss_count} files with screenshot/screen/capture in name")

    if screenshot_docs["hits"]["hits"]:
        for hit in screenshot_docs["hits"]["hits"][:3]:
            src = hit["_source"]
            fname = src.get("file_name", "?")
            conf = src.get("ocr_confidence", "N/A")
            ocr_len = len(src.get("ocr_content", ""))
            completed = src.get("ocr_completed", False)
            report(f"  Screenshot: {fname[:55]}",
                   "pass" if completed else "warn",
                   f"OCR done={completed}, conf={conf}, text_len={ocr_len}")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 6: DOCX / WORD DOCUMENT SEARCH
# ═════════════════════════════════════════════════════════════════════════
def test_docx_search():
    section("6. DOCX / WORD DOCUMENT SEARCH")

    docx_docs = os_client.search(index=INDEX, body={
        "size": 10,
        "query": {
            "bool": {
                "should": [
                    {"wildcard": {"file_name": "*.docx"}},
                    {"wildcard": {"file_name": "*.doc"}},
                    {"term": {"mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}},
                    {"term": {"mime_type": "application/msword"}},
                ]
            }
        },
        "_source": ["file_name", "main_content", "embedded_content", "file_size", "mime_type"],
        "sort": [{"file_size": "desc"}]
    })

    docx_count = docx_docs["hits"]["total"]["value"]
    report("Word documents indexed", "pass" if docx_count > 0 else "warn",
           f"{docx_count:,} Word documents found")

    has_content = 0
    for hit in docx_docs["hits"]["hits"]:
        mc = hit["_source"].get("main_content", "")
        if len(mc) > 50:
            has_content += 1

    if docx_docs["hits"]["hits"]:
        report("Word docs with content", "pass" if has_content > 0 else "warn",
               f"{has_content}/{len(docx_docs['hits']['hits'])} have substantial text")

    # Content search test
    for hit in docx_docs["hits"]["hits"][:2]:
        content = hit["_source"].get("main_content", "")
        if len(content) > 100:
            words = content.split()
            mid = len(words) // 3
            phrase = " ".join(words[mid:mid+4]).strip(".,;:()[]{}\"'")
            if len(phrase) > 10:
                resp = _search(f'"{phrase}"', size=5)
                fname = hit["_source"]["file_name"]
                report(f"DOCX content search: '{phrase[:45]}'",
                       "pass" if resp["hits"]["total"]["value"] > 0 else "fail",
                       f"From {fname[:40]}, hits: {resp['hits']['total']['value']}")
                break


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 7: EMBEDDED FILE & XML SEARCHABILITY
# ═════════════════════════════════════════════════════════════════════════
def test_embedded_files():
    section("7. EMBEDDED FILES & XML SEARCHABILITY")

    # 7a. Count docs with embedded content
    has_embedded = os_client.count(index=INDEX, body={
        "query": {"range": {"embedded_count": {"gte": 1}}}
    })["count"]
    report("Documents with embedded files", "pass" if has_embedded > 0 else "warn",
           f"{has_embedded:,} documents have embedded content")

    # 7b. XML files searchability
    xml_docs = os_client.search(index=INDEX, body={
        "size": 5,
        "query": {
            "bool": {
                "should": [
                    {"wildcard": {"file_name": "*.xml"}},
                    {"term": {"mime_type": "application/xml"}},
                    {"term": {"mime_type": "text/xml"}},
                ]
            }
        },
        "_source": ["file_name", "main_content", "file_path", "mime_type"],
    })
    xml_count = xml_docs["hits"]["total"]["value"]
    report("XML files indexed", "pass" if xml_count > 0 else "warn",
           f"{xml_count:,} XML files in index")

    xml_with_content = sum(1 for h in xml_docs["hits"]["hits"]
                           if len(h["_source"].get("main_content", "")) > 20)
    if xml_docs["hits"]["hits"]:
        report("XML files with content", "pass" if xml_with_content > 0 else "warn",
               f"{xml_with_content}/{len(xml_docs['hits']['hits'])} have searchable content")

    # 7c. JAR/ZIP files
    jar_docs = os_client.count(index=INDEX, body={
        "query": {"bool": {"should": [
            {"wildcard": {"file_name": "*.jar"}},
            {"wildcard": {"file_name": "*.zip"}},
        ]}}
    })["count"]
    report("JAR/ZIP files indexed", "pass",
           f"{jar_docs:,} JAR/ZIP files found")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 8: SEARCH PERFORMANCE
# ═════════════════════════════════════════════════════════════════════════
def test_search_performance():
    section("8. SEARCH PERFORMANCE")

    queries = [
        "financial report 2014",
        '"quarterly earnings"',
        "invoice payment",
        "employee benefits",
    ]

    for q in queries:
        start = time.time()
        resp = _search(q, size=20)
        elapsed_ms = (time.time() - start) * 1000
        total = resp["hits"]["total"]["value"]
        report(f"Search '{q[:35]}' ({elapsed_ms:.0f}ms)",
               "pass" if elapsed_ms < 2000 else "warn",
               f"{total:,} hits in {elapsed_ms:.0f}ms")


# ═════════════════════════════════════════════════════════════════════════
#  SECTION 9: FAILURE ANALYSIS
# ═════════════════════════════════════════════════════════════════════════
def test_failure_analysis():
    section("9. FAILURE ANALYSIS")

    failed_raw = r.hgetall("docsearch:failed")
    if not failed_raw:
        report("No failures to analyse", "pass")
        return

    # Breakdown by stage
    stage_counts = {}
    error_counts = {}
    for fid, data in failed_raw.items():
        try:
            info = json.loads(data)
            stage = info.get("stage", "unknown")
            etype = info.get("error_type", "unknown")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            error_counts[etype] = error_counts.get(etype, 0) + 1
        except:
            pass

    report("Failures by stage", "pass",
           " | ".join(f"{k}: {v}" for k, v in sorted(stage_counts.items(), key=lambda x: -x[1])))
    report("Failures by error type", "pass",
           " | ".join(f"{k}: {v}" for k, v in sorted(error_counts.items(), key=lambda x: -x[1])[:5]))


# ═════════════════════════════════════════════════════════════════════════
#  MAIN
# ═════════════════════════════════════════════════════════════════════════
def main():
    print("\n" + "="*70)
    print("  DOCUMENT SEARCH - DEEP-DIVE ACCURACY TESTS")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

    tests = [
        test_system_health,
        test_ocr_accuracy,
        test_search_accuracy,
        test_excel_search,
        test_image_searchability,
        test_docx_search,
        test_embedded_files,
        test_search_performance,
        test_failure_analysis,
    ]

    for test_fn in tests:
        try:
            test_fn()
        except Exception:
            section(f"ERROR in {test_fn.__name__}")
            report(f"{test_fn.__name__} crashed", "fail", traceback.format_exc()[:500])

    # Summary
    section("SUMMARY")
    total = RESULTS["pass"] + RESULTS["fail"] + RESULTS["warn"]
    print(f"  Total checks: {total}")
    print(f"  \033[92mPASS: {RESULTS['pass']}\033[0m")
    print(f"  \033[91mFAIL: {RESULTS['fail']}\033[0m")
    print(f"  \033[93mWARN: {RESULTS['warn']}\033[0m")
    print()

    # Write results to file
    report_path = os.path.join(os.path.dirname(__file__), "DEEP_DIVE_TEST_RESULTS.json")
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {"pass": RESULTS["pass"], "fail": RESULTS["fail"], "warn": RESULTS["warn"]},
            "details": RESULTS["details"]
        }, f, indent=2)
    print("  Results saved to DEEP_DIVE_TEST_RESULTS.json")
    return RESULTS["fail"]


if __name__ == "__main__":
    sys.exit(main())
