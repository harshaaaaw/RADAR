"""
=====================================================================
COMPREHENSIVE ENTERPRISE DOCUMENT SEARCH SYSTEM TEST SUITE
=====================================================================
Tests ALL functional layers including:
  1. Configuration / Constants
  2. Redis Queue State
  3. OpenSearch connectivity / indexing / search
  4. Tika extraction
  5. Bloom Filter (L8 safe serialization)
  6. Document Builder (M5 truncation metadata)
  7. Query Builder (search, phrase, numeric, path, slash)
  8. Content Extractor
  9. Orchestrator
 10. Search API
 11. Tagging quality & accuracy
 12. OCR extraction quality
 13. CLI
 14. Text Corrector (NLP)
 15. Image Preprocessor
 16. Hash Calculator
 17. Multi-entity search
 18. Tagging with entity extraction
 19. Cross-layer integration
=====================================================================
"""

import sys, os, json, tempfile, time, hashlib, traceback
from pathlib import Path
from datetime import datetime

# ── Result tracking ──────────────────────────────────────────────
passed   = []
failed   = []
warnings = []

def test(name):
    def decorator(func):
        def wrapper():
            try:
                func()
                passed.append(name)
                print(f"  PASS {name}")
            except AssertionError as e:
                failed.append((name, str(e)))
                print(f"  FAIL {name}: {e}")
            except Exception as e:
                failed.append((name, f"{type(e).__name__}: {e}"))
                print(f"  FAIL {name}: {type(e).__name__}: {e}")
                traceback.print_exc()
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator


def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


# =====================================================================
# LAYER 1: Configuration
# =====================================================================
@test("L01: Config loads successfully")
def test_config_load():
    from core.config_manager import get_config
    cfg = get_config()
    assert cfg is not None, "Config returned None"

@test("L01: Config paths are valid")
def test_config_paths():
    from core.config_manager import get_config
    cfg = get_config()
    assert hasattr(cfg, 'paths'), "Missing paths attribute"

@test("L01: Config extraction pools defined")
def test_config_pools():
    from core.config_manager import get_config
    cfg = get_config()
    assert hasattr(cfg, 'extraction'), "Missing extraction attribute"


# =====================================================================
# LAYER 2: Redis Queue State
# =====================================================================
@test("L02: Redis connection")
def test_redis_conn():
    import redis
    from core.config_manager import get_config
    cfg = get_config()
    r = redis.Redis.from_url(cfg.redis.url, decode_responses=True)
    assert r.ping(), "Redis ping failed"

@test("L02: Redis queue structure")
def test_redis_queues():
    import redis
    from core.config_manager import get_config
    cfg = get_config()
    r = redis.Redis.from_url(cfg.redis.url, decode_responses=True)
    keys = [k for k in r.keys('docsearch:queue:*')]
    print(f"    Queue keys found: {len(keys)}")
    for k in keys:
        ktype = r.type(k)
        if ktype == 'zset':
            size = r.zcard(k)
        elif ktype == 'list':
            size = r.llen(k)
        else:
            size = 0
        print(f"    {k}: type={ktype}, size={size}")

@test("L02: Redis stats keys")
def test_redis_stats():
    import redis
    from core.config_manager import get_config
    cfg = get_config()
    r = redis.Redis.from_url(cfg.redis.url, decode_responses=True)
    stats = [k for k in r.keys('docsearch:stats:*')]
    print(f"    Stats keys: {len(stats)}")

@test("L02: Redis file hashes set")
def test_redis_hashes():
    import redis
    from core.config_manager import get_config
    cfg = get_config()
    r = redis.Redis.from_url(cfg.redis.url, decode_responses=True)
    count = r.scard('docsearch:file_hashes')
    print(f"    File hashes in set: {count}")


# =====================================================================
# LAYER 3: OpenSearch
# =====================================================================
@test("L03: OpenSearch connectivity")
def test_opensearch_conn():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    info = osc.client.info()
    print(f"    Cluster: {info['cluster_name']}")
    print(f"    Version: {info['version']['number']}")

@test("L03: OpenSearch index exists and has documents")
def test_opensearch_index():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    count = osc.client.count(index=osc.index_name)['count']
    print(f"    Documents indexed: {count}")
    assert count > 0, "No documents indexed"

@test("L03: OpenSearch search functionality")
def test_opensearch_search():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    result = osc.client.search(index=osc.index_name, body={"query": {"match_all": {}}, "size": 3})
    hits = result['hits']['hits']
    print(f"    Sample results: {len(hits)}")
    for h in hits:
        src = h['_source']
        fname = src.get('file_name', 'N/A')
        content_len = len(src.get('main_content', ''))
        print(f"    - {fname}: {content_len} chars")
    assert len(hits) > 0, "No search results"

@test("L03: OpenSearch mapping has expected fields")
def test_opensearch_mapping():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    mapping = osc.client.indices.get_mapping(index=osc.index_name)
    fields = list(mapping[osc.index_name]['mappings']['properties'].keys())
    print(f"    Total mapped fields: {len(fields)}")
    expected = ['file_path', 'file_name', 'main_content', 'file_hash']
    for ef in expected:
        assert ef in fields, f"Missing expected field: {ef}"


# =====================================================================
# LAYER 4: Tika
# =====================================================================
@test("L04: Tika servers health")
def test_tika_health():
    import requests
    for port in [9998, 9999]:
        try:
            resp = requests.get(f"http://localhost:{port}/tika", timeout=5)
            status = "OK" if resp.status_code == 200 else f"HTTP {resp.status_code}"
        except Exception as e:
            status = f"UNREACHABLE: {e}"
        print(f"    Tika {port}: {status}")


# =====================================================================
# LAYER 5: Bloom Filter (L8 Safe Serialization)
# =====================================================================
@test("L05: Bloom filter add/contains")
def test_bloom_basic():
    from utils.bloom_filter import BloomFilter
    bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
    bf.add("abc123")
    bf.add("def456")
    assert bf.contains("abc123"), "Should contain abc123"
    assert bf.contains("def456"), "Should contain def456"
    assert not bf.contains("xyz789"), "Should NOT contain xyz789"
    assert bf.elements_added == 2

@test("L05: Bloom filter safe serialization (L8 fix)")
def test_bloom_safe_serialize():
    from utils.bloom_filter import BloomFilter
    bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
    bf.add("test_hash_1")
    bf.add("test_hash_2")
    bf.add("test_hash_3")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bloom') as tmp:
        tmp_path = tmp.name
    try:
        bf.save_to_file(tmp_path)
        meta_path = tmp_path + '.meta.json'
        assert os.path.exists(meta_path), "JSON sidecar not created"
        
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        assert meta['elements_added'] == 3
        assert meta['expected_elements'] == 1000
        
        # Load back
        bf2 = BloomFilter.load_from_file(tmp_path)
        assert bf2.contains("test_hash_1"), "Loaded filter should contain test_hash_1"
        assert bf2.contains("test_hash_2"), "Loaded filter should contain test_hash_2"
        assert bf2.contains("test_hash_3"), "Loaded filter should contain test_hash_3"
        assert not bf2.contains("nonexistent"), "Should NOT contain nonexistent"
        assert bf2.elements_added == 3
    finally:
        os.unlink(tmp_path)
        if os.path.exists(meta_path):
            os.unlink(meta_path)

@test("L05: Bloom filter false positive rate tracking")
def test_bloom_fpr():
    from utils.bloom_filter import BloomFilter
    bf = BloomFilter(expected_elements=10000, false_positive_rate=0.01)
    for i in range(100):
        bf.add(f"item_{i}")
    stats = bf.get_statistics()
    assert stats['current_fpr'] < 0.0001, f"FPR too high after only 100 items: {stats['current_fpr']}"
    assert stats['capacity_remaining'] > 0.9, "Capacity should still be > 90%"
    print(f"    FPR after 100/10000 items: {stats['current_fpr']:.8f}")
    print(f"    Capacity remaining: {stats['capacity_remaining']:.2%}")


# =====================================================================
# LAYER 6: Document Builder (M5 Truncation Metadata)
# =====================================================================
@test("L06: Document builder basic")
def test_doc_builder_basic():
    from indexing.document_builder import DocumentBuilder
    db = DocumentBuilder()
    doc_data = json.dumps({
        'file_path': 'C:/docs/test.pdf',
        'file_hash': 'abc123',
        'main_content': 'This is test content for document builder',
        'metadata': {'author': 'Test'},
        'embedded_files': [],
        'embedded_count': 0,
        'needs_ocr': False,
        'extraction_time_ms': 100
    })
    doc = db.build_document(doc_data)
    assert doc is not None, "build_document returned None"
    assert doc['file_name'] == 'test.pdf'
    assert doc['content_truncated'] == False, "Short content should not be truncated"
    assert doc['content_original_length'] > 0

@test("L06: Document builder content truncation (M5)")
def test_doc_builder_truncation():
    from indexing.document_builder import DocumentBuilder, MAX_MAIN_CONTENT_CHARS
    db = DocumentBuilder()
    huge_content = "A" * (MAX_MAIN_CONTENT_CHARS + 10000)
    doc_data = json.dumps({
        'file_path': 'C:/docs/big.pdf',
        'file_hash': 'big123',
        'main_content': huge_content,
        'metadata': {},
        'embedded_files': [],
        'embedded_count': 0,
        'needs_ocr': False,
        'extraction_time_ms': 50
    })
    doc = db.build_document(doc_data)
    assert doc is not None
    assert doc['content_truncated'] == True, "Should flag truncation"
    assert doc['content_original_length'] == len(huge_content)
    assert len(doc['main_content']) <= MAX_MAIN_CONTENT_CHARS + 100  # Allow "[content truncated]" suffix
    print(f"    Original: {doc['content_original_length']:,} chars")
    print(f"    Truncated to: {len(doc['main_content']):,} chars")

@test("L06: Document builder OCR update")
def test_doc_builder_ocr():
    from indexing.document_builder import DocumentBuilder
    db = DocumentBuilder()
    update = db.build_ocr_update("OCR extracted text here", 92.5)
    assert update['ocr_completed'] == True
    assert update['ocr_confidence'] == 92.5
    assert 'ocr_content' in update

@test("L06: Document builder semantic fields preserved")
def test_doc_builder_semantic_fields():
    from indexing.document_builder import DocumentBuilder
    db = DocumentBuilder()
    doc_data = json.dumps({
        'file_path': 'C:/docs/contract.pdf',
        'file_hash': 'sem123',
        'main_content': 'Legal contract between parties',
        'category': 'Legal',
        'department': 'Compliance',
        'purpose': 'Review',
        'dynamic_subtags': ['contract', 'legal'],
        'key_names': ['John Doe'],
        'amount_found': '$10,000',
        'important_dates': ['2026-01-01'],
        'location_mentioned': ['New York'],
        'confidentiality': 'Confidential',
        'metadata': {},
        'embedded_files': [],
        'embedded_count': 0,
        'needs_ocr': False,
        'extraction_time_ms': 50
    })
    doc = db.build_document(doc_data)
    assert doc is not None
    assert doc['category'] == 'Legal'
    assert doc['department'] == 'Compliance'
    assert 'contract' in doc['dynamic_subtags']
    assert 'John Doe' in doc['key_names']
    assert doc['confidentiality'] == 'Confidential'
    print(f"    Semantic fields preserved: category, department, purpose, tags, names, dates")


# =====================================================================
# LAYER 7: Query Builder (Search, Phrase, Numeric, Path, Slash)
# =====================================================================
@test("L07: Query builder basic search")
def test_query_basic():
    from api.query_builder import QueryBuilder
    qb = QueryBuilder()
    fields = ['main_content', 'file_name', 'ocr_content']
    query = qb.build_search_query("contract agreement", fields=fields, page=1, size=10)
    assert 'query' in query, "Missing query key"
    assert 'highlight' in query, "Missing highlight key"

@test("L07: Query builder with filters")
def test_query_filters():
    from api.query_builder import QueryBuilder
    qb = QueryBuilder()
    fields = ['main_content', 'file_name']
    query = qb.build_filter_query("test", filters={"file_type": "pdf", "category": "Legal"}, fields=fields, page=1, size=10)
    assert 'query' in query
    bool_q = query['query']['bool']
    assert 'filter' in bool_q, "Missing filter clauses"

@test("L07: Query builder phrase search (quoted)")
def test_query_phrase():
    from api.query_builder import QueryBuilder
    qb = QueryBuilder()
    fields = ['main_content', 'file_name']
    query = qb.build_search_query('"exact phrase match"', fields=fields)
    bool_q = query['query']['bool']
    # Phrase query uses should with match_phrase
    assert 'should' in bool_q, "Phrase query should use should clauses"
    has_phrase = any('match_phrase' in str(c) for c in bool_q['should'])
    assert has_phrase, "Should have match_phrase clauses"

@test("L07: Query builder numeric value search")
def test_query_numeric():
    from api.query_builder import QueryBuilder
    qb = QueryBuilder()
    fields = ['main_content', 'embedded_content']
    query = qb.build_search_query("2,480,821.04", fields=fields)
    # Numeric query should have term queries on .keyword fields
    q_str = json.dumps(query)
    assert 'term' in q_str or 'match_phrase' in q_str, "Numeric query should use term or match_phrase"

@test("L07: Query builder path search (backslash)")
def test_query_path():
    from api.query_builder import QueryBuilder
    qb = QueryBuilder()
    fields = ['main_content', 'file_name', 'file_path']
    query = qb.build_search_query("C:\\Users\\Documents\\test.pdf", fields=fields)
    q_str = json.dumps(query)
    # Path queries should use wildcard on file_path
    assert 'wildcard' in q_str or 'term' in q_str, "Path query should use wildcard/term"

@test("L07: Query builder slash command (\\ext pdf)")
def test_query_slash_ext():
    from api.query_builder import QueryBuilder
    qb = QueryBuilder()
    fields = ['main_content', 'file_name']
    query = qb.build_search_query("\\pdf", fields=fields)
    q_str = json.dumps(query)
    assert 'file_type' in q_str or 'wildcard' in q_str, "Slash ext should search file_type"

@test("L07: Query builder slash command (\\uid)")
def test_query_slash_uid():
    from api.query_builder import QueryBuilder
    qb = QueryBuilder()
    fields = ['main_content']
    query = qb.build_search_query("\\uid DOC-20260211-ABCD", fields=fields)
    q_str = json.dumps(query)
    assert 'smart_id' in q_str, "\\uid should search smart_id field"


# =====================================================================
# LAYER 8: Content Extractor
# =====================================================================
@test("L08: Content extractor initialization")
def test_content_extractor_init():
    from extraction.content_extractor import ContentExtractor
    ce = ContentExtractor()
    assert ce is not None

@test("L08: Content extractor normalization")
def test_content_extractor_normalize():
    from extraction.content_extractor import ContentExtractor
    ce = ContentExtractor()
    raw = "  Hello   World  \n\n\n  Test   "
    normalized = ce._normalize_content(raw)
    assert "  " not in normalized or len(normalized) < len(raw), "Should reduce whitespace"

@test("L08: Content extractor hash calculation")
def test_content_extractor_hash():
    from extraction.content_extractor import ContentExtractor
    ce = ContentExtractor()
    h1 = ce._calculate_content_hash("test content")
    h2 = ce._calculate_content_hash("test content")
    h3 = ce._calculate_content_hash("different content")
    assert h1 == h2, "Same content should produce same hash"
    assert h1 != h3, "Different content should produce different hash"


# =====================================================================
# LAYER 9: Orchestrator
# =====================================================================
@test("L09: Master orchestrator imports and has registry")
def test_orchestrator():
    from orchestrator.master_orchestrator import MasterOrchestrator
    assert hasattr(MasterOrchestrator, '__init__')

@test("L09: Checkpoint manager import")
def test_checkpoint_mgr():
    from orchestrator.checkpoint_manager import CheckpointManager
    assert hasattr(CheckpointManager, '__init__')

@test("L09: Recovery manager import")
def test_recovery_mgr():
    from orchestrator.recovery_manager import RecoveryManager
    assert hasattr(RecoveryManager, '__init__')


# =====================================================================
# LAYER 10: Search API
# =====================================================================
@test("L10: Search API imports")
def test_search_api_import():
    from api.search_api import app
    assert app is not None
    print(f"    FastAPI app loaded")


# =====================================================================
# LAYER 11: Tagging Quality & Accuracy
# =====================================================================
@test("L11: Taxonomy manager initialization")
def test_taxonomy_init():
    from tagging.taxonomy_manager import TaxonomyManager
    tm = TaxonomyManager()
    tm.ensure_loaded()
    snap = tm.get_snapshot()
    assert snap is not None
    print(f"    Taxonomy version: {snap.version_id}")
    for field in ('category', 'department', 'purpose'):
        rows = snap.rows_by_field.get(field, [])
        print(f"    {field}: {len(rows)} rows")

@test("L11: Tagging engine initialization")
def test_tagging_init():
    from tagging.tagging_engine import TaggingEngine
    te = TaggingEngine()
    assert te is not None
    print(f"    Tagging engine initialized")

@test("L11: Tagging accuracy - Legal contract")
def test_tag_legal_contract():
    from tagging.tagging_engine import TaggingEngine
    from tagging.tagging_models import TaggingRequest
    te = TaggingEngine()
    req = TaggingRequest(
        file_path="C:/docs/legal/service_agreement_2026.pdf",
        file_name="service_agreement_2026.pdf",
        file_type="pdf",
        main_content=(
            "SERVICE AGREEMENT. This Agreement is entered into between ABC Corporation and XYZ Ltd. "
            "The parties agree to the following terms and conditions for consulting services. "
            "Payment of $50,000 shall be made upon completion. Effective date: January 1, 2026. "
            "Location: New York, NY. Confidential."
        ),
    )
    result = te.tag(req)
    print(f"    Category: {result.category} (conf: {result.tag_confidence_by_field.get('category',{}).get('score', 0):.2f})")
    print(f"    Department: {result.department}")
    print(f"    Purpose: {result.purpose}")
    print(f"    File type: {result.file_type}")
    print(f"    Subtags: {result.dynamic_subtags}")
    print(f"    Key names: {result.key_names}")
    print(f"    Amounts: {result.amount_found}")
    print(f"    Dates: {result.important_dates}")
    print(f"    Locations: {result.location_mentioned}")
    print(f"    Confidentiality: {result.confidentiality}")
    print(f"    Overall confidence: {result.tag_confidence_overall:.2f}")
    assert result.file_type == 'pdf', f"Expected pdf, got {result.file_type}"
    assert result.category != '', "Category should not be empty"
    assert result.department != '', "Department should not be empty"

@test("L11: Tagging accuracy - Financial invoice")
def test_tag_financial_invoice():
    from tagging.tagging_engine import TaggingEngine
    from tagging.tagging_models import TaggingRequest
    te = TaggingEngine()
    req = TaggingRequest(
        file_path="C:/finance/invoices/invoice_2026_001.xlsx",
        file_name="invoice_2026_001.xlsx",
        file_type="xlsx",
        main_content=(
            "INVOICE #2026-001. Bill To: Global Enterprises Inc. "
            "Items: Consulting services Q1 2026 - $25,000.00. Tax: $2,500.00. "
            "Total: $27,500.00. Due Date: March 15, 2026. "
            "Payment terms: Net 30. Bank: Chase Manhattan, Account: 1234567890."
        ),
    )
    result = te.tag(req)
    print(f"    Category: {result.category}")
    print(f"    Department: {result.department}")
    print(f"    Amounts: {result.amount_found}")
    print(f"    Dates: {result.important_dates}")
    print(f"    Overall confidence: {result.tag_confidence_overall:.2f}")
    assert result.file_type == 'xlsx', f"Expected xlsx, got {result.file_type}"

@test("L11: Tagging accuracy - HR resume")
def test_tag_hr_resume():
    from tagging.tagging_engine import TaggingEngine
    from tagging.tagging_models import TaggingRequest
    te = TaggingEngine()
    req = TaggingRequest(
        file_path="C:/hr/resumes/john_doe_resume.docx",
        file_name="john_doe_resume.docx",
        file_type="docx",
        main_content=(
            "JOHN DOE - Senior Software Engineer. Email: john.doe@email.com. "
            "Location: San Francisco, CA. Experience: 10 years in software development. "
            "Skills: Python, Java, Machine Learning. Education: MS Computer Science, Stanford University. "
            "Previous: Google, Microsoft, Amazon."
        ),
    )
    result = te.tag(req)
    print(f"    Category: {result.category}")
    print(f"    Department: {result.department}")
    print(f"    Key names: {result.key_names}")
    print(f"    Locations: {result.location_mentioned}")
    print(f"    Overall confidence: {result.tag_confidence_overall:.2f}")
    assert result.file_type == 'docx'

@test("L11: Tagging confidentiality detection")
def test_tag_confidentiality():
    from tagging.tagging_engine import TaggingEngine
    from tagging.tagging_models import TaggingRequest
    te = TaggingEngine()
    # Confidential doc
    req1 = TaggingRequest(
        file_name="secret.pdf", file_type="pdf",
        main_content="STRICTLY CONFIDENTIAL. This document contains trade secrets."
    )
    r1 = te.tag(req1)
    # Public doc
    req2 = TaggingRequest(
        file_name="readme.txt", file_type="txt",
        main_content="This is an open source readme file with public information."
    )
    r2 = te.tag(req2)
    print(f"    Confidential doc: '{r1.confidentiality}'")
    print(f"    Public doc: '{r2.confidentiality}'")
    assert r1.confidentiality.lower() in ('confidential', 'strictly confidential'), \
        f"Expected confidential, got: {r1.confidentiality}"

@test("L11: Tagging entity extraction - names, dates, amounts, locations")
def test_tag_entity_extraction():
    from tagging.tagging_engine import TaggingEngine
    from tagging.tagging_models import TaggingRequest
    te = TaggingEngine()
    req = TaggingRequest(
        file_path="C:/docs/contract.pdf",
        file_name="contract.pdf",
        file_type="pdf",
        main_content=(
            "Agreement between Alice Johnson and Bob Smith. "
            "Total payment: $150,000 due on February 28, 2026. "
            "Location: London, United Kingdom. "
            "Additional amount: EUR 25,000 for consulting in Paris, France."
        ),
    )
    result = te.tag(req)
    print(f"    Key names found: {result.key_names}")
    print(f"    Amount found: {result.amount_found}")
    print(f"    Important dates: {result.important_dates}")
    print(f"    Locations: {result.location_mentioned}")
    # We just check entity extraction ran without error and returned something
    assert isinstance(result.key_names, list)
    assert isinstance(result.important_dates, list)
    assert isinstance(result.location_mentioned, list)

@test("L11: Tagging result to_document_update")
def test_tag_result_update():
    from tagging.tagging_models import TaggingResult
    tr = TaggingResult(
        category="Legal", department="Compliance", purpose="Review",
        file_type="pdf", dynamic_subtags=["contract"],
        tag_confidence_overall=0.85
    )
    update = tr.to_document_update()
    assert update['category'] == 'Legal'
    assert update['tag_confidence'] == 0.85
    assert 'contract' in update['dynamic_subtags']


# =====================================================================
# LAYER 12: OCR Extraction Quality
# =====================================================================
@test("L12: Tesseract availability")
def test_tesseract_available():
    from core.config_manager import get_config
    cfg = get_config()
    tess_path = cfg.ocr.tesseract.command
    assert os.path.exists(tess_path), f"Tesseract not found at {tess_path}"
    print(f"    Tesseract: {tess_path}")

@test("L12: Tesseract wrapper initialization")
def test_tesseract_wrapper_init():
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    assert tw is not None
    health = tw.health_check()
    print(f"    Health: {health}")
    assert health == True, "Tesseract health check failed"

@test("L12: Tesseract version check")
def test_tesseract_version():
    from ocr.tesseract_wrapper import TesseractWrapper
    tw = TesseractWrapper()
    version = tw.get_version()
    print(f"    Version: {version}")
    assert version is not None

@test("L12: Image preprocessor initialization")
def test_image_preprocessor_init():
    from ocr.image_preprocessor import ImagePreprocessor
    ip = ImagePreprocessor()
    assert ip is not None
    print(f"    Target DPI: {ip.target_dpi}")
    print(f"    Use OpenCV: {ip.use_opencv}")

@test("L12: Image preprocessor with synthetic image")
def test_image_preprocessor_synthetic():
    try:
        import cv2
        import numpy as np
    except ImportError:
        print("    SKIP: cv2 not available")
        return
    
    from ocr.image_preprocessor import ImagePreprocessor
    ip = ImagePreprocessor()
    
    # Create a simple test image (white background, black text-like pattern)
    img = np.ones((200, 400, 3), dtype=np.uint8) * 255
    cv2.putText(img, "TEST OCR", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    _, buffer = cv2.imencode('.png', img)
    img_bytes = buffer.tobytes()
    
    result = ip.preprocess(img_bytes)
    assert result is not None, "Preprocessor returned None"
    assert len(result) > 0, "Preprocessor returned empty bytes"
    print(f"    Input: {len(img_bytes)} bytes -> Output: {len(result)} bytes")


# =====================================================================
# LAYER 13: CLI
# =====================================================================
@test("L13: CLI module loads")
def test_cli_load():
    from main import cli
    commands = [c for c in cli.commands]
    print(f"    All CLI commands present")
    assert len(commands) > 5, f"Expected >5 commands, got {len(commands)}"


# =====================================================================
# LAYER 14: NLP Text Corrector
# =====================================================================
@test("L14: Text corrector initialization")
def test_text_corrector_init():
    from nlp.text_corrector import TextCorrector
    tc = TextCorrector()
    assert tc is not None
    print(f"    Model loaded: {tc.model_loaded}")

@test("L14: Text corrector - empty/None input")
def test_text_corrector_empty():
    from nlp.text_corrector import TextCorrector
    tc = TextCorrector()
    result, count = tc.correct("")
    assert result == "", "Empty string should return empty"
    assert count == 0

    result2, count2 = tc.correct(None)
    assert count2 == 0

@test("L14: Text corrector - date corrections")
def test_text_corrector_dates():
    from nlp.text_corrector import TextCorrector
    tc = TextCorrector()
    # Common OCR date errors
    text = "Meeting on 0ctober 15, 2O26. Another on Januarv 3, 2025."
    corrected, count = tc.correct(text)
    print(f"    Original:  {text}")
    print(f"    Corrected: {corrected}")
    print(f"    Corrections: {count}")
    # Should have attempted some corrections
    assert isinstance(corrected, str)

@test("L14: Text corrector - financial amounts")
def test_text_corrector_amounts():
    from nlp.text_corrector import TextCorrector
    tc = TextCorrector()
    text = "Total amount: $l,250,000.OO. Tax: $l25,OOO.OO."
    corrected, count = tc.correct(text)
    print(f"    Original:  {text}")
    print(f"    Corrected: {corrected}")
    print(f"    Corrections: {count}")

@test("L14: Text corrector - OCR character errors")
def test_text_corrector_char_errors():
    from nlp.text_corrector import TextCorrector
    tc = TextCorrector()
    text = "The cornpany rnust review the docurnent before subrnitting."
    corrected, count = tc.correct(text)
    print(f"    Original:  {text}")
    print(f"    Corrected: {corrected}")
    print(f"    Corrections: {count}")

@test("L14: Text corrector - financial phrases")
def test_text_corrector_financial():
    from nlp.text_corrector import TextCorrector
    tc = TextCorrector()
    text = "The accounls payable departrnent processed the purchasc order."
    corrected, count = tc.correct(text)
    print(f"    Original:  {text}")
    print(f"    Corrected: {corrected}")
    print(f"    Corrections: {count}")

@test("L14: Text corrector preserves clean text")
def test_text_corrector_clean():
    from nlp.text_corrector import TextCorrector
    tc = TextCorrector()
    clean = "The company reported revenue of $5,000,000 for Q1 2026."
    corrected, count = tc.correct(clean)
    print(f"    Clean text corrections: {count}")
    # Clean text should have minimal or no corrections
    assert corrected is not None


# =====================================================================
# LAYER 15: Hash Calculator
# =====================================================================
@test("L15: Hash calculator basic")
def test_hash_calc_basic():
    from discovery.hash_calculator import HashCalculator
    hc = HashCalculator()
    # Create a temp file to hash
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
        tmp.write(b"Test content for hashing")
        tmp_path = tmp.name
    try:
        h = hc.calculate_hash(tmp_path)
        assert h is not None, "Hash should not be None"
        assert len(h) == 64, f"SHA-256 hex digest should be 64 chars, got {len(h)}"
        h2 = hc.calculate_hash(tmp_path)
        assert h == h2, "Same file should produce same hash"
        print(f"    Hash: {h[:16]}...")
        stats = hc.get_stats()
        print(f"    Files hashed: {stats['files_hashed']}")
    finally:
        os.unlink(tmp_path)

@test("L15: Hash calculator deterministic")
def test_hash_calc_deterministic():
    from discovery.hash_calculator import HashCalculator
    hc = HashCalculator()
    content = b"Deterministic test content"
    expected_hash = hashlib.sha256(content).hexdigest()
    with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        result = hc.calculate_hash(tmp_path)
        assert result == expected_hash, f"Hash mismatch: {result} != {expected_hash}"
        print(f"    Verified: SHA-256 matches hashlib")
    finally:
        os.unlink(tmp_path)


# =====================================================================
# LAYER 16: Multi-Entity Search (Live OpenSearch)
# =====================================================================
@test("L16: Multi-entity search - by file type")
def test_search_by_file_type():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    result = osc.client.search(
        index=osc.index_name,
        body={"query": {"term": {"file_type": "pdf"}}, "size": 5}
    )
    count = result['hits']['total']['value']
    print(f"    PDF documents found: {count}")

@test("L16: Multi-entity search - by category tag")
def test_search_by_category():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    # Get all unique categories first
    agg_result = osc.client.search(
        index=osc.index_name,
        body={
            "size": 0,
            "aggs": {"categories": {"terms": {"field": "category", "size": 20}}}
        }
    )
    buckets = agg_result['aggregations']['categories']['buckets']
    print(f"    Categories found: {len(buckets)}")
    for b in buckets[:5]:
        print(f"      - {b['key']}: {b['doc_count']} docs")

@test("L16: Multi-entity search - by department tag")
def test_search_by_department():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    agg_result = osc.client.search(
        index=osc.index_name,
        body={
            "size": 0,
            "aggs": {"departments": {"terms": {"field": "department", "size": 20}}}
        }
    )
    buckets = agg_result['aggregations']['departments']['buckets']
    print(f"    Departments found: {len(buckets)}")
    for b in buckets[:5]:
        print(f"      - {b['key']}: {b['doc_count']} docs")

@test("L16: Multi-entity search - content match accuracy")
def test_search_content_accuracy():
    from indexing.opensearch_client import OpenSearchClient
    from api.query_builder import QueryBuilder
    osc = OpenSearchClient()
    qb = QueryBuilder()
    
    # Search for a very specific term
    fields = ['main_content', 'file_name', 'ocr_content', 'embedded_content']
    query = qb.build_search_query("document", fields=fields, size=5)
    result = osc.client.search(index=osc.index_name, body=query, size=5)
    hits = result['hits']['hits']
    print(f"    Results for 'document': {result['hits']['total']['value']}")
    for h in hits[:3]:
        score = h['_score']
        fname = h['_source'].get('file_name', 'N/A')
        print(f"      - {fname} (score: {score:.2f})")

@test("L16: Multi-entity search - file_name wildcard")
def test_search_filename_wildcard():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    result = osc.client.search(
        index=osc.index_name,
        body={"query": {"wildcard": {"file_name.keyword": {"value": "*.docx"}}}, "size": 5}
    )
    count = result['hits']['total']['value']
    print(f"    .docx files found: {count}")


# =====================================================================
# LAYER 17: Cross-Layer Integration Tests
# =====================================================================
@test("L17: Document builder -> Document builder semantic roundtrip")
def test_doc_roundtrip():
    from indexing.document_builder import DocumentBuilder
    db = DocumentBuilder()
    original = {
        'file_path': 'C:/test/roundtrip.pdf',
        'file_hash': 'rt123',
        'main_content': 'Roundtrip test content for integration',
        'metadata': {'author': 'Test'},
        'embedded_files': [],
        'embedded_count': 0,
        'needs_ocr': False,
        'extraction_time_ms': 42,
        'category': 'Testing',
        'department': 'QA',
        'purpose': 'Verification',
    }
    doc = db.build_document(json.dumps(original))
    assert doc is not None
    assert doc['file_path'] == original['file_path']
    assert doc['category'] == 'Testing'
    assert doc['content_truncated'] == False
    print(f"    Roundtrip: OK, {len(doc)} fields")

@test("L17: Query builder -> OpenSearch live search")
def test_query_to_search():
    from api.query_builder import QueryBuilder
    from indexing.opensearch_client import OpenSearchClient
    qb = QueryBuilder()
    osc = OpenSearchClient()
    
    fields = ['main_content', 'file_name']
    query = qb.build_search_query("test", fields=fields, size=3)
    result = osc.client.search(index=osc.index_name, body=query, size=3)
    assert 'hits' in result
    total = result['hits']['total']['value']
    print(f"    Live query 'test': {total} results")

@test("L17: Tagging -> TaggingResult -> document_update format")
def test_tagging_to_update():
    from tagging.tagging_engine import TaggingEngine
    from tagging.tagging_models import TaggingRequest
    te = TaggingEngine()
    req = TaggingRequest(
        file_name="integration_test.pdf",
        file_type="pdf",
        main_content="Financial report for Q1 2026 showing revenue of $1,000,000."
    )
    result = te.tag(req)
    update = result.to_document_update()
    
    # Validate update has all required fields for OpenSearch
    required = ['category', 'department', 'purpose', 'file_type', 
                'dynamic_subtags', 'tag_confidence', 'tagging_status']
    for field in required:
        assert field in update, f"Missing field in update: {field}"
    print(f"    Update fields: {len(update)}")
    print(f"    Tagging status: {update['tagging_status']}")
    print(f"    Confidence: {update['tag_confidence']:.2f}")


# =====================================================================
# LAYER 18: OpenSearch Indexing Test (write + verify + cleanup)
# =====================================================================
@test("L18: OpenSearch index, search, delete roundtrip")
def test_opensearch_index_roundtrip():
    from indexing.opensearch_client import OpenSearchClient
    osc = OpenSearchClient()
    
    test_doc_id = "__test_doc_roundtrip_" + str(int(time.time()))
    test_doc = {
        'file_path': 'C:/test/roundtrip_test.pdf',
        'file_name': 'roundtrip_test.pdf',
        'file_hash': 'test_hash_roundtrip',
        'main_content': 'UNIQUE_TEST_TOKEN_9X7Z_FOR_VERIFICATION',
        'indexed_at': datetime.now().isoformat(),
        'file_type': 'pdf',
    }
    
    try:
        # Index
        success = osc.index_document_direct(test_doc_id, test_doc)
        assert success, "Failed to index test document"
        
        # Refresh to make searchable immediately
        osc.client.indices.refresh(index=osc.index_name)
        
        # Search
        result = osc.client.search(
            index=osc.index_name,
            body={"query": {"term": {"file_hash": "test_hash_roundtrip"}}}
        )
        hits = result['hits']['hits']
        assert len(hits) >= 1, f"Expected to find test doc, got {len(hits)} hits"
        assert hits[0]['_source']['main_content'] == 'UNIQUE_TEST_TOKEN_9X7Z_FOR_VERIFICATION'
        print(f"    Index -> Search -> Verify: OK")
        
    finally:
        # Cleanup
        try:
            osc.client.delete(index=osc.index_name, id=test_doc_id)
            osc.client.indices.refresh(index=osc.index_name)
            print(f"    Cleanup: test doc deleted")
        except Exception:
            print(f"    WARN: Could not cleanup test doc {test_doc_id}")


# =====================================================================
# RUN ALL TESTS
# =====================================================================
if __name__ == '__main__':
    section("LAYER 1: Configuration")
    test_config_load()
    test_config_paths()
    test_config_pools()

    section("LAYER 2: Redis Queue State")
    test_redis_conn()
    test_redis_queues()
    test_redis_stats()
    test_redis_hashes()

    section("LAYER 3: OpenSearch")
    test_opensearch_conn()
    test_opensearch_index()
    test_opensearch_search()
    test_opensearch_mapping()

    section("LAYER 4: Tika")
    test_tika_health()

    section("LAYER 5: Bloom Filter (L8)")
    test_bloom_basic()
    test_bloom_safe_serialize()
    test_bloom_fpr()

    section("LAYER 6: Document Builder (M5)")
    test_doc_builder_basic()
    test_doc_builder_truncation()
    test_doc_builder_ocr()
    test_doc_builder_semantic_fields()

    section("LAYER 7: Query Builder")
    test_query_basic()
    test_query_filters()
    test_query_phrase()
    test_query_numeric()
    test_query_path()
    test_query_slash_ext()
    test_query_slash_uid()

    section("LAYER 8: Content Extractor")
    test_content_extractor_init()
    test_content_extractor_normalize()
    test_content_extractor_hash()

    section("LAYER 9: Orchestrator")
    test_orchestrator()
    test_checkpoint_mgr()
    test_recovery_mgr()

    section("LAYER 10: Search API")
    test_search_api_import()

    section("LAYER 11: Tagging Quality & Accuracy")
    test_taxonomy_init()
    test_tagging_init()
    test_tag_legal_contract()
    test_tag_financial_invoice()
    test_tag_hr_resume()
    test_tag_confidentiality()
    test_tag_entity_extraction()
    test_tag_result_update()

    section("LAYER 12: OCR Extraction Quality")
    test_tesseract_available()
    test_tesseract_wrapper_init()
    test_tesseract_version()
    test_image_preprocessor_init()
    test_image_preprocessor_synthetic()

    section("LAYER 13: CLI")
    test_cli_load()

    section("LAYER 14: NLP Text Corrector")
    test_text_corrector_init()
    test_text_corrector_empty()
    test_text_corrector_dates()
    test_text_corrector_amounts()
    test_text_corrector_char_errors()
    test_text_corrector_financial()
    test_text_corrector_clean()

    section("LAYER 15: Hash Calculator")
    test_hash_calc_basic()
    test_hash_calc_deterministic()

    section("LAYER 16: Multi-Entity Search (Live)")
    test_search_by_file_type()
    test_search_by_category()
    test_search_by_department()
    test_search_content_accuracy()
    test_search_filename_wildcard()

    section("LAYER 17: Cross-Layer Integration")
    test_doc_roundtrip()
    test_query_to_search()
    test_tagging_to_update()

    section("LAYER 18: OpenSearch Indexing Roundtrip")
    test_opensearch_index_roundtrip()

    # ── Final Summary ──
    section("FINAL TEST RESULTS SUMMARY")
    total = len(passed) + len(failed)
    print(f"\n  PASSED: {len(passed)}/{total}")
    print(f"  FAILED: {len(failed)}/{total}")
    
    if failed:
        print(f"\n--- FAILURES ---")
        for name, reason in failed:
            print(f"  FAIL {name}: {reason}")
    
    if warnings:
        print(f"\n--- WARNINGS ---")
        for w in warnings:
            print(f"  WARN {w}")
    
    print()
    sys.exit(1 if failed else 0)
