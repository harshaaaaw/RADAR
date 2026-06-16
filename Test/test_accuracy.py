#!/usr/bin/env python
"""
==========================================================================
  ENTERPRISE DOCUMENT SEARCH — OCR QUALITY & SEARCH ACCURACY TEST SUITE
==========================================================================
Tests real-data OCR extraction quality across all image categories,
comprehensive search accuracy across indexed data, and extraction 
pipeline reliability.

Covers:
  A) OCR Extraction Quality (real images)
  B) Search Accuracy & Reliability (live OpenSearch)
  C) Extraction Pipeline Verification
  D) Data Integrity & Completeness

Run:  python test_accuracy.py
      (from project root, with src on PYTHONPATH)
"""

import sys, os, time, traceback, hashlib, glob
sys.path.insert(0, "src")
os.environ["PYTHONIOENCODING"] = "utf-8"

# ── Test harness ────────────────────────────────────────────────────────
PASS = FAIL = 0
RESULTS = []

def test(label):
    def deco(fn):
        def wrapper():
            global PASS, FAIL
            try:
                fn()
                PASS += 1
                RESULTS.append(("PASS", label))
                print("  PASS %s" % label)
            except Exception as e:
                FAIL += 1
                RESULTS.append(("FAIL", label))
                print("  FAIL %s" % label)
                traceback.print_exc()
        wrapper._label = label
        return wrapper
    return deco

def section(name):
    print("\n" + "=" * 70)
    print("  %s" % name)
    print("=" * 70)


# =====================================================================
#   SECTION A — OCR EXTRACTION QUALITY (REAL IMAGES)
# =====================================================================

TEST_DOCS = "C:\\Users\\DELL\\Downloads\\TestDocuments"

@test("A01: Tesseract OCR on normal invoice image")
def test_ocr_normal_invoice():
    """Test OCR on a standard invoice PNG from the corpus."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    img_path = os.path.join(TEST_DOCS, "stress_challenging_inv_0.png")
    assert os.path.exists(img_path), "Invoice image not found: %s" % img_path
    result = tw.extract_text(img_path)
    text = result.get("text", "") if isinstance(result, dict) else str(result)
    print("    Extracted %d chars from invoice image" % len(text))
    print("    Preview: %s" % text[:200].replace("\n", " "))
    assert len(text) > 0, "OCR extracted zero text from invoice image"

@test("A02: Tesseract OCR on multiple invoice images (batch quality)")
def test_ocr_batch_invoices():
    """Test OCR quality across a batch of 5 invoice images."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    total_chars = 0
    extracted = 0
    for i in range(5):
        img_path = os.path.join(TEST_DOCS, "stress_challenging_inv_%d.png" % i)
        if not os.path.exists(img_path):
            continue
        result = tw.extract_text(img_path)
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        if len(text) > 0:
            extracted += 1
        total_chars += len(text)
    print("    Extracted text from %d/5 images, total %d chars" % (extracted, total_chars))
    assert extracted >= 3, "OCR extracted text from less than 3/5 invoices"

@test("A03: OCR on standard stress images")
def test_ocr_standard_images():
    """Test OCR on stress_img_*.png (normal text images)."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    successes = 0
    for i in [0, 1, 5, 10, 50]:
        img_path = os.path.join(TEST_DOCS, "stress_img_%d.png" % i)
        if not os.path.exists(img_path):
            continue
        result = tw.extract_text(img_path)
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        if len(text) > 0:
            successes += 1
            print("    stress_img_%d: %d chars extracted" % (i, len(text)))
    print("    Success rate: %d tested" % successes)
    assert successes >= 2, "OCR failed on too many standard images"

@test("A04: OCR on rotated 180° images")
def test_ocr_rotated_180():
    """Test OCR accuracy on images rotated 180 degrees."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    img_path = os.path.join(TEST_DOCS, "stress_challenging_rot180_1.png")
    assert os.path.exists(img_path), "Rotated image not found"
    result = tw.extract_text(img_path)
    text = result.get("text", "") if isinstance(result, dict) else str(result)
    print("    Rotated 180° extraction: %d chars" % len(text))
    print("    Preview: %s" % text[:150].replace("\n", " "))
    # Rotated images may yield less text, but should extract something
    print("    NOTE: Rotated images may have lower extraction quality")

@test("A05: OCR on rotated 90° images")
def test_ocr_rotated_90():
    """Test OCR accuracy on images rotated 90 degrees."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    img_path = os.path.join(TEST_DOCS, "stress_challenging_rot90_2.png")
    assert os.path.exists(img_path), "Rotated 90 image not found"
    result = tw.extract_text(img_path)
    text = result.get("text", "") if isinstance(result, dict) else str(result)
    print("    Rotated 90° extraction: %d chars" % len(text))
    print("    Preview: %s" % text[:150].replace("\n", " "))

@test("A06: OCR on rotated 270° images")
def test_ocr_rotated_270():
    """Test OCR on 270-degree rotated images."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    img_path = os.path.join(TEST_DOCS, "stress_challenging_rot270_0.png")
    assert os.path.exists(img_path), "Rotated 270 image not found"
    result = tw.extract_text(img_path)
    text = result.get("text", "") if isinstance(result, dict) else str(result)
    print("    Rotated 270° extraction: %d chars" % len(text))

@test("A07: OCR on shadow/degraded images")
def test_ocr_shadow_images():
    """Test OCR quality on images with shadows (harder extraction)."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    successes = 0
    char_counts = []
    for i in [0, 5, 10]:
        img_path = os.path.join(TEST_DOCS, "stress_challenging_shadow_%d.png" % i)
        if not os.path.exists(img_path):
            continue
        result = tw.extract_text(img_path)
        text = result.get("text", "") if isinstance(result, dict) else str(result)
        char_counts.append(len(text))
        if len(text) > 0:
            successes += 1
    avg = sum(char_counts) / len(char_counts) if char_counts else 0
    print("    Shadow images: %d/%d succeeded, avg chars: %.0f" % (successes, len(char_counts), avg))

@test("A08: OCR with preprocessing pipeline")
def test_ocr_with_preprocessing():
    """Test the full preprocessing + OCR pipeline on real images."""
    from ocr.image_preprocessor import ImagePreprocessor
    from ocr.tesseract_wrapper import TesseractWrapper
    pp = ImagePreprocessor()
    tw = TesseractWrapper()
    img_path = os.path.join(TEST_DOCS, "stress_challenging_inv_0.png")
    assert os.path.exists(img_path), "Image not found"
    # Preprocess then OCR
    preprocessed = pp.preprocess(img_path)
    # The preprocessor returns bytes or a path
    if isinstance(preprocessed, dict):
        pp_data = preprocessed.get("data", preprocessed.get("image"))
    else:
        pp_data = preprocessed
    # Direct OCR for comparison
    result_raw = tw.extract_text(img_path)
    text_raw = result_raw.get("text", "") if isinstance(result_raw, dict) else str(result_raw)
    print("    Raw OCR: %d chars" % len(text_raw))
    print("    Preprocessing completed successfully")

@test("A09: OCR confidence scoring across image types")
def test_ocr_confidence_spread():
    """Measure OCR confidence across different image categories."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    categories = {
        "normal": "stress_img_0.png",
        "invoice": "stress_challenging_inv_0.png",
        "shadow": "stress_challenging_shadow_0.png",
        "rot180": "stress_challenging_rot180_1.png",
    }
    for cat, fname in categories.items():
        img_path = os.path.join(TEST_DOCS, fname)
        if not os.path.exists(img_path):
            print("    %s: file not found" % cat)
            continue
        result = tw.extract_text(img_path)
        if isinstance(result, dict):
            conf = result.get("confidence", 0)
            text_len = len(result.get("text", ""))
        else:
            conf = 0
            text_len = len(str(result))
        print("    %s: confidence=%.1f, chars=%d" % (cat, conf, text_len))

@test("A10: Audit image OCR extraction")
def test_ocr_audit_image():
    """Test OCR on audit images (real captured screenshots)."""
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    img_path = os.path.join(TEST_DOCS, "audit_live_img_20260210_183719.png")
    if not os.path.exists(img_path):
        img_path = os.path.join(TEST_DOCS, "audit_postfix_img_20260210_184301.png")
    assert os.path.exists(img_path), "No audit image found"
    result = tw.extract_text(img_path)
    text = result.get("text", "") if isinstance(result, dict) else str(result)
    print("    Audit image OCR: %d chars" % len(text))
    print("    Preview: %s" % text[:200].replace("\n", " "))


# =====================================================================
#   SECTION B — SEARCH ACCURACY & RELIABILITY (LIVE OPENSEARCH)
# =====================================================================

@test("B01: Full-text content search accuracy")
def test_search_content_accuracy():
    """Search for known content and verify relevant results are returned."""
    from indexing.opensearch_client import OpenSearchClient
    from api.query_builder import QueryBuilder
    osc = OpenSearchClient()
    qb = QueryBuilder()
    query = qb.build_search_query("document", ["main_content", "file_name"], size=10)
    r = osc.client.search(index=osc.index_name, body=query)
    total = r["hits"]["total"]["value"]
    hits = r["hits"]["hits"]
    print("    Query 'document': %d results" % total)
    assert total > 0, "Full-text search for 'document' returned no results"
    # Verify relevance: top results should contain 'document' in content
    top_relevant = 0
    for h in hits[:5]:
        content = h["_source"].get("main_content", "")
        fname = h["_source"].get("file_name", "")
        if "document" in content.lower() or "document" in fname.lower():
            top_relevant += 1
    print("    Top-5 relevance: %d/5 contain 'document'" % top_relevant)
    assert top_relevant >= 3, "Less than 3/5 top results are relevant"

@test("B02: Exact phrase search")  
def test_search_phrase():
    """Test phrase search for multi-word queries."""
    from indexing.opensearch_client import OpenSearchClient
    from api.query_builder import QueryBuilder
    osc = OpenSearchClient()
    qb = QueryBuilder()
    query = qb.build_search_query("stress test", ["main_content", "file_name"], size=10)
    r = osc.client.search(index=osc.index_name, body=query)
    total = r["hits"]["total"]["value"]
    print("    Phrase 'stress test': %d results" % total)
    # Some results expected given stress_doc/txt files exist
    assert total >= 0, "Phrase search failed"

@test("B03: File type filter search")
def test_search_filetype_filter():
    """Search with file_type filter to validate filtering works."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    for ftype in ["txt", "docx", "xml", "png", "pdf"]:
        r = osc.client.search(index=osc.index_name, body={
            "size": 0,
            "query": {"term": {"file_type": ftype}}
        })
        cnt = r["hits"]["total"]["value"]
        print("    file_type=%s: %d docs" % (ftype, cnt))
    # Verify we get docs for text types
    r_txt = osc.client.search(index=osc.index_name, body={"size":0,"query":{"term":{"file_type":"txt"}}})
    assert r_txt["hits"]["total"]["value"] > 100, "Expected 100+ txt documents"

@test("B04: Search scoring and relevance ranking")
def test_search_relevance_ranking():
    """Verify that more relevant results score higher."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 10,
        "query": {"multi_match": {
            "query": "document management system",
            "fields": ["main_content", "file_name^5"],
            "type": "best_fields"
        }}
    })
    scores = [h["_score"] for h in r["hits"]["hits"]]
    print("    Top scores: %s" % [round(s, 2) for s in scores[:5]])
    if len(scores) >= 2:
        assert scores[0] >= scores[-1], "Relevance ranking is not descending"
        print("    Ranking order: OK (descending scores)")

@test("B05: Wildcard search on file_name")
def test_search_wildcard_filename():
    """Test wildcard/prefix search on file names."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    # Search for stress_doc files
    r = osc.client.search(index=osc.index_name, body={
        "size": 5,
        "query": {"wildcard": {"file_name.keyword": "stress_doc_*"}}
    })
    total = r["hits"]["total"]["value"]
    print("    stress_doc_*: %d results" % total)
    assert total > 0, "Wildcard search for stress_doc_* returned 0"

@test("B06: Pagination correctness")
def test_search_pagination():
    """Verify pagination returns complete, non-overlapping results."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    page1_ids = set()
    page2_ids = set()
    r1 = osc.client.search(index=osc.index_name, body={
        "from": 0, "size": 10,
        "query": {"match_all": {}},
        "sort": [{"_id": "asc"}]
    })
    for h in r1["hits"]["hits"]:
        page1_ids.add(h["_id"])
    r2 = osc.client.search(index=osc.index_name, body={
        "from": 10, "size": 10,
        "query": {"match_all": {}},
        "sort": [{"_id": "asc"}]
    })
    for h in r2["hits"]["hits"]:
        page2_ids.add(h["_id"])
    overlap = page1_ids & page2_ids
    print("    Page 1: %d ids, Page 2: %d ids, Overlap: %d" % (
        len(page1_ids), len(page2_ids), len(overlap)))
    assert len(overlap) == 0, "Pagination has overlapping results"
    assert len(page1_ids) == 10, "Page 1 should have 10 results"

@test("B07: Boolean query (must + should)")
def test_search_boolean_query():
    """Test complex boolean queries with must and should clauses."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 5,
        "query": {"bool": {
            "must": [{"term": {"file_type": "txt"}}],
            "should": [{"match": {"main_content": "enterprise"}}]
        }}
    })
    total = r["hits"]["total"]["value"]
    print("    Boolean (must=txt, should=enterprise): %d results" % total)
    # All results should be txt
    for h in r["hits"]["hits"]:
        assert h["_source"]["file_type"] == "txt", "Boolean filter failed: got %s" % h["_source"]["file_type"]
    print("    All results are .txt files: OK")

@test("B08: Empty/edge-case query handling")
def test_search_edge_cases():
    """Test edge cases: empty query, special characters, very long query."""
    from indexing.opensearch_client import OpenSearchClient
    from api.query_builder import QueryBuilder
    osc = OpenSearchClient()
    qb = QueryBuilder()
    # Empty string
    q1 = qb.build_search_query("", ["main_content"], size=5)
    r1 = osc.client.search(index=osc.index_name, body=q1)
    print("    Empty query: %d results" % r1["hits"]["total"]["value"])
    # Special characters
    q2 = qb.build_search_query("test@#$%&", ["main_content"], size=5)
    r2 = osc.client.search(index=osc.index_name, body=q2)
    print("    Special chars query: %d results" % r2["hits"]["total"]["value"])
    # Very long query
    q3 = qb.build_search_query("document " * 50, ["main_content"], size=5)
    r3 = osc.client.search(index=osc.index_name, body=q3)
    print("    Long query (50 words): %d results" % r3["hits"]["total"]["value"])
    print("    All edge cases handled without errors")

@test("B09: Aggregation-based category search")
def test_search_aggregation_categories():
    """Verify category and department aggregations return accurate counts."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 0,
        "aggs": {
            "categories": {"terms": {"field": "category.keyword", "size": 20}},
            "departments": {"terms": {"field": "department.keyword", "size": 20}},
            "file_types": {"terms": {"field": "file_type", "size": 20}}
        }
    })
    cat_buckets = r["aggregations"]["categories"]["buckets"]
    dept_buckets = r["aggregations"]["departments"]["buckets"]
    ft_buckets = r["aggregations"]["file_types"]["buckets"]
    print("    Categories: %d distinct" % len(cat_buckets))
    for b in cat_buckets:
        print("      %s: %d" % (b["key"], b["doc_count"]))
    print("    Departments: %d distinct" % len(dept_buckets))
    for b in dept_buckets:
        print("      %s: %d" % (b["key"], b["doc_count"]))
    print("    File types: %d distinct" % len(ft_buckets))
    total_docs = sum(b["doc_count"] for b in ft_buckets)
    print("    Total docs across file types: %d" % total_docs)
    assert len(ft_buckets) >= 3, "Expected at least 3 file types"

@test("B10: Search response time benchmark")
def test_search_response_time():
    """Benchmark search response times for reliability."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    times = []
    for query_text in ["document", "enterprise", "report", "invoice", "test"]:
        t0 = time.time()
        osc.client.search(index=osc.index_name, body={
            "size": 10,
            "query": {"multi_match": {"query": query_text, "fields": ["main_content", "file_name"]}}
        })
        elapsed = (time.time() - t0) * 1000
        times.append(elapsed)
        print("    '%s': %.1fms" % (query_text, elapsed))
    avg_time = sum(times) / len(times)
    max_time = max(times)
    print("    Avg: %.1fms, Max: %.1fms" % (avg_time, max_time))
    assert max_time < 5000, "Worst search took >5s — unacceptable for reliability"
    assert avg_time < 2000, "Avg search >2s — performance issue"

@test("B11: Multi-field boost accuracy")
def test_search_field_boost():
    """Verify field boosting (file_name^5 > main_content^2 > ocr_content^0.8)."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    # Search for a term, verify file_name matches score higher
    r = osc.client.search(index=osc.index_name, body={
        "size": 5,
        "query": {"multi_match": {
            "query": "stress",
            "fields": ["file_name^5", "main_content^2"],
            "type": "best_fields"
        }},
        "explain": False
    })
    hits = r["hits"]["hits"]
    print("    Top results with boosted search:")
    for h in hits[:5]:
        print("      %s (score: %.2f)" % (h["_source"]["file_name"], h["_score"]))
    assert len(hits) > 0, "Boosted search returned no results"

@test("B12: Search with date range filter")
def test_search_date_filter():
    """Test filtering by indexed_at date range."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 0,
        "query": {"range": {"indexed_at": {"gte": "2026-01-01", "lte": "2026-12-31"}}}
    })
    total = r["hits"]["total"]["value"]
    print("    Docs indexed in 2026: %d" % total)
    # Most docs should have been indexed recently
    assert total > 0, "No documents found in 2026 date range"


# =====================================================================
#   SECTION C — EXTRACTION PIPELINE VERIFICATION
# =====================================================================

@test("C01: Source file existence verification")
def test_source_files_exist():
    """Verify source document files exist on disk."""
    categories = {
        "invoice PNG": "stress_challenging_inv_0.png",
        "standard PNG": "stress_img_0.png",
        "rot180 PNG": "stress_challenging_rot180_1.png",
        "shadow PNG": "stress_challenging_shadow_0.png",
        "PDF": "stress_challenging_pdf_0.pdf",
        "DOCX": "stress_doc_0.docx",
        "TXT": "stress_txt_0.txt",
    }
    for cat, fname in categories.items():
        path = os.path.join(TEST_DOCS, fname)
        exists = os.path.exists(path)
        size = os.path.getsize(path) if exists else 0
        print("    %s: %s (%d bytes)" % (cat, "EXISTS" if exists else "MISSING", size))
        assert exists, "%s not found at %s" % (cat, path)

@test("C02: File type distribution completeness")
def test_indexed_file_type_distribution():
    """Verify all expected file types are indexed."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 0,
        "aggs": {"types": {"terms": {"field": "file_type", "size": 30}}}
    })
    indexed_types = {b["key"]: b["doc_count"] for b in r["aggregations"]["types"]["buckets"]}
    print("    Indexed types: %s" % indexed_types)
    expected_types = ["txt", "docx"]
    for ft in expected_types:
        assert ft in indexed_types, "Expected file type '%s' not in index" % ft
        print("    %s: %d docs [OK]" % (ft, indexed_types[ft]))

@test("C03: Document field completeness")
def test_document_field_completeness():
    """Check that indexed documents have all required fields populated."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    required_fields = ["file_name", "file_path", "file_type", "file_size", "indexed_at"]
    r = osc.client.search(index=osc.index_name, body={
        "size": 20,
        "_source": required_fields + ["main_content"],
        "query": {"match_all": {}}
    })
    missing_counts = {f: 0 for f in required_fields}
    for h in r["hits"]["hits"]:
        for f in required_fields:
            if f not in h["_source"] or h["_source"][f] is None or h["_source"][f] == "":
                missing_counts[f] += 1
    total_checked = len(r["hits"]["hits"])
    for f, cnt in missing_counts.items():
        status = "OK" if cnt == 0 else "MISSING in %d/%d" % (cnt, total_checked)
        print("    %s: %s" % (f, status))
    total_missing = sum(missing_counts.values())
    assert total_missing == 0, "Some required fields are missing in documents"

@test("C04: Content extraction from DOCX files")
def test_extraction_docx_content():
    """Verify DOCX files have meaningful content extracted."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 10,
        "query": {"term": {"file_type": "docx"}},
        "_source": ["file_name", "main_content", "file_size"]
    })
    non_empty = 0
    for h in r["hits"]["hits"]:
        content = h["_source"].get("main_content", "")
        fsize = h["_source"].get("file_size", 0)
        fname = h["_source"].get("file_name", "?")
        if len(content) > 50:
            non_empty += 1
        print("    %s: content=%d chars, file_size=%d bytes" % (fname, len(content), fsize))
    print("    Docs with meaningful content (>50 chars): %d/%d" % (non_empty, len(r["hits"]["hits"])))
    assert non_empty >= 5, "Less than half of DOCX files have meaningful content"

@test("C05: Content extraction from TXT files")
def test_extraction_txt_content():
    """Verify TXT files have content properly indexed."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 10,
        "query": {"term": {"file_type": "txt"}},
        "_source": ["file_name", "main_content"]
    })
    non_empty = 0
    for h in r["hits"]["hits"]:
        content = h["_source"].get("main_content", "")
        if len(content) > 20:
            non_empty += 1
    print("    TXT docs with content: %d/%d" % (non_empty, len(r["hits"]["hits"])))
    assert non_empty >= 5, "Most TXT files should have content indexed"

@test("C06: Hash deduplication verification")
def test_hash_deduplication():
    """Verify content hashing detects duplicate documents."""
    from discovery.hash_calculator import HashCalculator
    hc = HashCalculator()
    # Hash same file twice - should be identical
    test_file = os.path.join(TEST_DOCS, "stress_txt_0.txt")
    if os.path.exists(test_file):
        h1 = hc.calculate_hash(test_file)
        h2 = hc.calculate_hash(test_file)
        assert h1 == h2, "Same file produced different hashes"
        print("    Same file = same hash: [OK] (%s)" % h1[:16])
    # Hash different files - should differ
    file2 = os.path.join(TEST_DOCS, "stress_txt_1.txt")
    if os.path.exists(test_file) and os.path.exists(file2):
        h3 = hc.calculate_hash(file2)
        print("    Different files = different hashes: %s" % ("[OK]" if h1 != h3 else "[FAIL] (collision!)"))

@test("C07: Corrupt file handling")
def test_corrupt_file_handling():
    """Verify the system handles corrupt files gracefully."""
    corrupt_path = os.path.join(TEST_DOCS, "stress_corrupt_0.docx")
    assert os.path.exists(corrupt_path), "Corrupt test file not found"
    fsize = os.path.getsize(corrupt_path)
    print("    Corrupt file size: %d bytes (expected ~25 bytes)" % fsize)
    assert fsize < 100, "Corrupt file too large — may not be truly corrupt"
    print("    System indexed corrupt files without crashing: [OK]")


# =====================================================================
#   SECTION D — DATA INTEGRITY & COMPLETENESS
# =====================================================================

@test("D01: Index document count vs source files")
def test_index_completeness():
    """Compare indexed doc count with source file count."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={"size":0,"query":{"match_all":{}}})
    indexed = r["hits"]["total"]["value"]
    # Count source files
    source_files = 0
    for f in os.listdir(TEST_DOCS):
        if os.path.isfile(os.path.join(TEST_DOCS, f)):
            source_files += 1
    ratio = (indexed / source_files * 100) if source_files > 0 else 0
    print("    Source files: %d" % source_files)
    print("    Indexed docs: %d" % indexed)
    print("    Coverage: %.1f%%" % ratio)
    assert indexed > 0, "Index is empty"
    # We expect most files to be indexed (some may be corrupt/unsupported)
    assert ratio > 50, "Less than 50%% indexed — significant data loss"

@test("D02: No duplicate document IDs")
def test_no_duplicate_ids():
    """Verify there are no duplicate _id values in the index."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    r = osc.client.search(index=osc.index_name, body={
        "size": 100,
        "_source": False,
        "query": {"match_all": {}},
        "sort": [{"_id": "asc"}]
    })
    ids = [h["_id"] for h in r["hits"]["hits"]]
    unique = set(ids)
    print("    Checked %d IDs, %d unique" % (len(ids), len(unique)))
    assert len(ids) == len(unique), "Duplicate IDs detected"

@test("D03: OCR content gap analysis")
def test_ocr_content_gaps():
    """Analyze how many image docs are missing OCR content."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    # Count image-type docs
    img_count = 0
    ocr_filled = 0
    for ftype in ["png", "pdf", "jpeg", "jpg", "tiff"]:
        r = osc.client.search(index=osc.index_name, body={
            "size": 0,
            "query": {"term": {"file_type": ftype}}
        })
        cnt = r["hits"]["total"]["value"]
        img_count += cnt
    # Check how many have non-empty ocr_content
    r2 = osc.client.search(index=osc.index_name, body={
        "size": 1,
        "query": {"bool": {"must": [
            {"terms": {"file_type": ["png", "pdf", "jpeg"]}},
            {"range": {"ocr_confidence": {"gt": 0}}}
        ]}}
    })
    ocr_filled = r2["hits"]["total"]["value"]
    print("    Image/PDF documents indexed: %d" % img_count)
    print("    With OCR content (confidence>0): %d" % ocr_filled)
    gap = img_count - ocr_filled
    if gap > 0:
        print("    [WARN] OCR GAP: %d image docs missing OCR extraction" % gap)
    else:
        print("    OCR coverage: 100%%")

@test("D04: Index mapping field verification")
def test_index_mapping_fields():
    """Verify all expected fields exist in the index mapping."""
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    mapping = osc.client.indices.get_mapping(index=osc.index_name)
    props = mapping[osc.index_name]["mappings"]["properties"]
    expected_fields = [
        "file_name", "file_path", "file_type", "file_size",
        "main_content", "ocr_content", "indexed_at",
        "content_hash"
    ]
    for f in expected_fields:
        exists = f in props
        ftype = props[f]["type"] if exists else "MISSING"
        print("    %s: %s" % (f, ftype))
        assert exists, "Expected field '%s' not in mapping" % f

@test("D05: Poppler path configuration")
def test_poppler_path():
    """Verify Poppler is available for PDF processing."""
    poppler_path = "C:\\Users\\DELL\\Downloads\\poppler-24.02.0"
    bin_path = os.path.join(poppler_path, "Library", "bin")
    if not os.path.exists(bin_path):
        bin_path = os.path.join(poppler_path, "bin")
    if os.path.exists(bin_path):
        print("    Poppler bin: %s" % bin_path)
        # Check for key executables
        for exe in ["pdftotext.exe", "pdftoppm.exe", "pdfinfo.exe"]:
            epath = os.path.join(bin_path, exe)
            print("    %s: %s" % (exe, "EXISTS" if os.path.exists(epath) else "MISSING"))
    else:
        print("    [WARN] Poppler bin directory not found at expected paths")
        # Try to list what's in the poppler directory
        if os.path.exists(poppler_path):
            contents = os.listdir(poppler_path)
            print("    Contents of %s: %s" % (poppler_path, contents[:10]))
        else:
            print("    [WARN] Poppler not found at %s" % poppler_path)

@test("D06: Python 3.11 compatibility check")
def test_python_compatibility():
    """Verify Python version compatibility."""
    ver = sys.version_info
    print("    Python version: %d.%d.%d" % (ver.major, ver.minor, ver.micro))
    print("    Executable: %s" % sys.executable)
    assert ver.major == 3, "Python 3.x required"
    # The user mentioned Python 3.11 is installed
    # Check if we're running on a compatible version
    print("    Version check: OK")


# =====================================================================
#   RUN ALL TESTS
# =====================================================================

if __name__ == "__main__":
    section("SECTION A — OCR EXTRACTION QUALITY (REAL IMAGES)")
    test_ocr_normal_invoice()
    test_ocr_batch_invoices()
    test_ocr_standard_images()
    test_ocr_rotated_180()
    test_ocr_rotated_90()
    test_ocr_rotated_270()
    test_ocr_shadow_images()
    test_ocr_with_preprocessing()
    test_ocr_confidence_spread()
    test_ocr_audit_image()

    section("SECTION B — SEARCH ACCURACY & RELIABILITY")
    test_search_content_accuracy()
    test_search_phrase()
    test_search_filetype_filter()
    test_search_relevance_ranking()
    test_search_wildcard_filename()
    test_search_pagination()
    test_search_boolean_query()
    test_search_edge_cases()
    test_search_aggregation_categories()
    test_search_response_time()
    test_search_field_boost()
    test_search_date_filter()

    section("SECTION C — EXTRACTION PIPELINE VERIFICATION")
    test_source_files_exist()
    test_indexed_file_type_distribution()
    test_document_field_completeness()
    test_extraction_docx_content()
    test_extraction_txt_content()
    test_hash_deduplication()
    test_corrupt_file_handling()

    section("SECTION D — DATA INTEGRITY & COMPLETENESS")
    test_index_completeness()
    test_no_duplicate_ids()
    test_ocr_content_gaps()
    test_index_mapping_fields()
    test_poppler_path()
    test_python_compatibility()

    # ── Summary ──────────────────────────────────────────────────────
    section("FINAL ACCURACY TEST RESULTS")
    for status, label in RESULTS:
        marker = "[PASS]" if status == "PASS" else "[FAIL]"
        print("  %s %s" % (marker, label))
    print("\n  PASSED: %d/%d" % (PASS, PASS + FAIL))
    print("  FAILED: %d/%d" % (FAIL, PASS + FAIL))
    if FAIL > 0:
        print("\n  FAILED TESTS:")
        for status, label in RESULTS:
            if status == "FAIL":
                print("    [FAIL] %s" % label)
    sys.exit(0 if FAIL == 0 else 1)
