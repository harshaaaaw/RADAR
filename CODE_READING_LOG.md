# RADAR full-codebase reading log

Strict word-to-word read of every source file. One entry per file, in read order.
Status: COMPLETE.

---

## 1. src/agents/__init__.py (7 lines)
Team docstring. Search/counts are injected callables; prod wiring lands with API step.

## 2. src/agents/router.py (49 lines)
`router_agent(query, history)`: file regex wins, then analytics hints, then short-with-history followup, else semantic. Adds document_type and department_category filters. Never raises.

## 3. src/agents/specialists.py (143 lines)
`_norm_text` across text/chunk_text/content/main_content. `retrieval_agent` masks PII, strips injections, normalizes scores and file names, reranks top_k. `analytics_agent` formats counts summary. `file_agent` assembles [Page N] full text capped 12000. `answer_agent` LLM context-only with citations, history last 4, context 9000. `verifier_agent` blocks on no sources, no citation names, or query terms absent from source blob.

## 4. src/agents/graph.py (98 lines)
`AgentGraph.run`: router, retrieval, analytics, optional file, answer, verifier, one query rewrite then retry, BLOCK below 0.50 confidence or no sources or failed verify. Full trace with latencies, tokens, cost.

## 5. src/agents/guardrails.py (28 lines)
`mask_pii` emails and 10-16 digit runs. `strip_doc_instructions` drops lines starting with ignore previous/system:/you must/disregard.

## 6. src/agents/ledger.py (72 lines)
`AnswerLedger` HMAC-SHA256 chain over prev hash plus payload. `append(tenant, kind, payload)`, `verify()` replays chain, `record_verdict` also files into reporting_manager audit trail without ever raising.

## 7. src/api/prod_wiring.py (81 lines)
`CONTENT_FIELDS` boosts file_name 15, reviewed_content 8, main/ocr 6, embedded 3. `source_to_chunk` picks first non-empty text key, defaults file_name/page/score. `build_prod_search_fn` multi_match best_fields size capped 20. `build_prod_counts_fn` terms agg on document_type.keyword plus total.

## 8. src/api/query_builder.py (537 lines)
`QueryBuilder`: slash commands uid/ext/tag/smart-id, exact phrase with slop 0, numeric with dot-comma variants on .keyword plus match_phrase, path queries on metadata fields only, accurate cross_fields 75 percent with phrase boost and extended_metadata, filters as terms/term, highlight marks on content fields. No fuzzy anywhere.

## 9. src/api/search_api.py (312 lines)
FastAPI app: per-IP rate limit 100 per 60s, optional CORS, bearer token with constant-time compare. GET /search with deep-pagination guard, /document/id, /status progress from extraction plus indexing, /metrics, POST /api/shutdown. Uvicorn main.

## 10. src/api/__init__.py (27 lines)
PEP 562 lazy loading so ask_api imports without opensearchpy.

## 11. src/nlp/llm_client.py (69 lines)
`call_llm`: key from config llm section or GROQ_API_KEY env, model openai/gpt-oss-120b default, temp 0.1, 1024 tokens max. Mock offline with token estimate at 0.0004 per 1K. Never raises; error path falls back to mock with zero cost.

## 12. src/nlp/text_corrector.py (526 lines)
`TextCorrector`: 6 stages dates, amounts, char fixes, phrase dictionary, common patterns, SpaCy NER. Rule-based always; SpaCy md then sm, graceful without. Singleton `get_text_corrector`.

## 13. src/indexing/chunker.py (117 lines)
`recursive_split` blank lines, breaks, sentences, spaces with overlap link. `chunk_document` sha1 doc-id prefix chunk ids, page-aware, carries all tag fields, idempotent re-ingest.

## 14. src/indexing/embeddings.py (57 lines)
Hash vectors 64 dims offline default; bge-large lazy with hash fallback. `knn_mapping` adds knn_vector field.

## 15. src/indexing/reranker.py (31 lines)
Token overlap plus half retrieval score, top_k, no floor by design, verifier decides blocks.

## 16. src/indexing/document_builder.py (306 lines)
Builds the OpenSearch doc: truncates main 500K, embedded 200K, OCR 200K with flags, sanitizes embedded_files to name/index/capped content, preserves tag fields, parent-child lineage from Redis parent_map, always sets embedded_content and ocr_content fields, build_ocr_update for partial OCR writes.

## 17. src/indexing/indexing_worker.py (681 lines)
Micro-batch loop with frozen batch size, timeout flush, shutdown flush, heartbeat. Bulk then complete queue batch, mark completed with timings, enqueue tagging, dedupe via completed file-id set. Transient retry with max attempts, permanent fail path, whole-batch requeue, audit event plus file-state upsert at every transition. File marked indexed not completed until tagging finishes.

## 18. src/indexing/opensearch_client.py (849 lines)
Adaptive batching, circuit breaker after 5 failures, 413 split-and-retry, backoff retries. Index with english_enhanced plus synonyms, edge n-grams, comma stripper, keyword subfields 8192. Express single index, painless OCR partial update with conflict retry, mapping updater for tag and reviewed_content fields.

## 19. src/discovery/__init__.py (25 lines)
PEP 562 lazy worker imports so triage loads without redis.

## 20. src/discovery/file_scanner.py (176 lines)
Differential scandir walk with mtime skip, fnmatch excludes plus Office lock skip, extension include/exclude, folder priority, no-symlink-follow, per-file metadata with sizes and times.

## 21. src/discovery/hash_calculator.py (104 lines)
SHA-256 buffered 64K, mmap above 100MB with standard fallback, files and bytes counters.

## 22. src/discovery/triage.py (135 lines)
Four tiers folder 0.95, filename, content regex first 3000 chars, unknown 0.50 fallback. Quality score with 0.60 degraded line. Never raises.

## 23. src/discovery/discovery_worker.py (491 lines)
Root bootstrap once via SETNX with reseed self-heal, folder queue walk, unchanged-file skip by path-size-mtime, sha256 hash, Bloom plus DB-confirmed dedupe, size routing, extraction enqueue, audit event plus state row per file, completion only when folder queue empty, Bloom persisted for resume.

## 24. src/extraction/tika_client.py (217 lines)
Pooled requests session, manual retries with backoff list, streamed PUT to /rmeta/text, 422 unsupported returns None, 5xx and timeouts retried, version and stats, context manager.

## 25. src/extraction/content_extractor.py (294 lines)
Main doc plus embedded docs from Tika rmeta list, metadata whitelist with mime and page count, normalization lowercase whitespace timestamps page numbers for content hash dedupe, OCR routing with Office skip and pdf/image/page-count fallbacks, Office internal XML parts filtered from embedded.

## 26. src/extraction/extraction_worker.py (947 lines)
Per-size Tika pool worker, GC every 100 files, 4GB self-kill, 85 percent pause. Tika extract, NLP correct when enabled, parent metadata to Redis, deep ZIP/EML/MSG extraction with zip-bomb caps and flattened injection, 65MB doc cap, accuracy analysis per file, batch indexing enqueue, parallel OCR enqueue with embedded deprioritized, audit at every stage.

## 27. src/extraction/accuracy_analyzer.py (1285 lines)
Tiered accuracy: OpenCV zone segmentation with coarse plus tight passes, signature rules, stamp circularity, whitespace validation grid, faded-text Otsu-vs-adaptive detection, YOLO ONNX or ultralytics refine, PaddleOCR raw-vs-processed coverage, DocTR ground truth, loss partition normalized to 100 with bboxes, per-format analyzers txt csv md json xml html docx xlsx pdf generic.

## 28. src/extraction/backfill_accuracy.py (158 lines)
CLI backfill: rows missing accuracy from audit.db, per-format text recovery with PyMuPDF for PDFs, analyze plus update_accuracy_metrics, success skip error counts.

## 29. src/ocr/tesseract_wrapper.py (220 lines)
Subprocess TSV word-level OCR, binary resolution config plus PATH plus known spots, PSM per attempt, prewarm, PaddleWrapper-identical interface.

## 30. src/ocr/paddle_wrapper.py (344 lines)
Windows-safe env pins single-thread, truststore SSL inject, lazy per-lang engines with modern PaddleX constructor plus legacy fallback, single-lang Windows CPU guard, three result parsers 3.x predict plus dict plus legacy boxes, best-confidence pick.

## 31. src/ocr/snippet_filter.py (209 lines)
Noise ink-ratio plus coverage gates, signature tiny-impact hard suppress, printed-font stroke uniformity check, OCR text-like hide, config policy hook, every suppression logged to SQLite.

## 32. src/ocr/visual_memory.py (371 lines)
ONNX MobileNetV3 via OpenCV DNN with torch fallback and 16x16 perceptual hash last resort, YOLOv8 layout regions, cosine match at 0.88 snippet and 0.90 global, hybrid text check rejects visual matches with conflicting text below 0.50.

## 33. src/ocr/image_preprocessor.py (198 lines)
Denoise plus CLAHE before grayscale, skew fix by Hough median over 0.5 degrees, Otsu binarize, 50MB skip and 6000px downscale guards, Pillow fallback.

## 34. src/ocr/image_preprocessor_advanced.py (1069 lines)
16-step pipeline: orientation, inversion, perspective dewarp with edge-touch guard, mode select light balanced aggressive extreme-restore from quality plus brightness contrast sharpness, shadows, borders with 8 percent crop cap, color background HSV ranges, faded repair, broken-text thicken by polarity.

## 35. src/ocr/ocr_worker.py (2321 lines)
Engine selectable tesseract default paddle fallback, Poppler inject with PyMuPDF fallback, text-rich PDF smart routing bypass, 7-day versioned page cache with stale recompute, 12-strategy image loop and 6-strategy page loop with confidence plus coverage scoring, OCR before complete plus Redis pending updates, visual snippets with artifact guards SVM classify reviewer roles, visual memory auto-accept, printed-font 2-of-3 vote, per-page metrics aggregation with verification bands, 4GB self-kill.

## 36. src/tagging/tagging_engine.py (1586 lines)
Hybrid rules plus taxonomy plus spaCy. Priority metadata explicit 0.99 derived 0.86 then model. Signals keyword 0.35 primary alias full 0.30 path 0.20 semantic 0.30 entity align 0.20 chunk 0.25 label overlap 0.15 feedback 0.20. Guards ambiguous tie gap, no-spacy cap, empty content hallucination block, cross-field consistency. 12 dimensions classification country 3-layer currency deal scan BU weighted sub-BU hierarchy. Sheet 3 constraint force with 0.75 cap and audit trail. Entity extraction NER plus noun chunks plus regex, garbage entity filter, path-free content-only text.

## 37. src/tagging/tagging_models.py (155 lines)
TaxonomyRow FieldConfidence TaggingRequest TaggingResult with 12 dimensions plus legacy sync plus enrichments plus provenance, to_document_update maps to OpenSearch fields, ReviewDecision.

## 38. src/tagging/taxonomy_manager.py (352 lines)
Excel workbook loader required sheets category department purpose plus defaults, thread-locked hot reload, alias map, builtin fallback taxonomy, feedback weights from SQLite, canonicalize plus validation helpers.

## 39. src/tagging/metadata_manager.py (989 lines)
Metadata-first tagging from Excel. Sheet 3 valid-values registry with exact partial token plus synonym fallback. Source priority config api ui cli with active descriptor. Join scoring smart_id 100 file_key 90 file_name 80 path 70 doc_id 60, single-row fallback, semantic overlap fallback at 3 tokens. Header promotion for messy sheets, extended metadata preserved, derived keyword tags.

## 40. src/tagging/tagging_worker.py (440 lines)
Claim batch tagging work, load doc from OpenSearch by doc_id hash file-id candidates, tag, update doc preserving smart_id, complete tagging, retry 3 then fail, full audit with confidence JSON plus all 12 dimensions, heartbeat.

## 41. src/tagging/backfill_tagging.py (89 lines)
Scroll all indexed docs search_after, enqueue each to tagging queue priority 5, infinite-loop guards on unchanged sort.

## 42. src/utils/__init__.py (12 lines)
Exports BloomFilter, version 1.0.0.

## 43. src/core/__init__.py (37 lines)
PEP 562 lazy config logging queue getters so monitors load without redis.

## 44. src/orchestrator/__init__.py (26 lines)
PEP 562 lazy MasterOrchestrator HealthMonitor ResourceMonitor CheckpointManager.

## 45. src/orchestrator/health_monitor.py (73 lines)
Tika per-port plus OpenSearch green-yellow plus paddle import checks, one retry with 2s wait on transient failure.

## 46. src/orchestrator/resource_monitor.py (105 lines)
CPU RAM disk via psutil, GB config minimums with 85-90 percent floors, ordering guard, LLM token plus cost counters fed by agent graph.

## 47. src/orchestrator/checkpoint_manager.py (107 lines)
Atomic temp-plus-rename checkpoints of queue stats plus uptime, latest load, retention cleanup.

## 48. src/core/logging_manager.py (278 lines)
Windows-safe rotating handlers surviving multi-process PermissionError, console plus application plus errors logs, per-component files with temp fallback, JSON optional, no-propagation dedupe, graceful shutdown.

## 49. src/core/constants.py (396 lines)
Hub of shared truth: QueueStatus SizeCategory WorkerPoolType ProcessingStage ErrorType HealthStatus WorkerStatus DuplicateType OCRStatus Priority enums, sha256 plus 64KB chunks, queue batch sizes, timeouts Tika 60 OpenSearch 30 OCR 600 heartbeat 90, retries 3 with backoff, checkpoint 5min keep 10, index enterprise_documents 5 shards plus english_enhanced, Bloom 5M at 1 percent, rates 30k discovery 180 extraction 7k indexing 600 OCR pages per hour, API pages 20 max 100, circuit breaker 5-60-3, all field names, table names, excluded binary extensions and system folders, HTTP codes, 100MB content cap.

## 50. src/utils/bloom_filter.py (492 lines)
MurmurHash3 double hashing, RLock everywhere, size and k formulas, add plus batch, contains plus in-operator, live FPR plus capacity plus stats, persistence as bitarray plus JSON sidecar with legacy pickle fallback warning, populate from Redis SSCAN or SQLite in 10k batches, create sized existing plus 1M.

## 51. src/core/config_manager.py (723 lines)
Typed dataclasses for every section. Config search project-local first. {app_root} interpolation with RADAR_APP_ROOT override. Secrets only from env OPENSEARCH_USER PASSWORD SMTP_USER PASSWORD ALERT_FROM TO API_TOKEN with type-aware coercion. Validation requires 9 sections, 1 plus Tika, 1 plus workers each. Defaults for redis nlp tagging tesseract OCR engine. ensure_directories builds tree. print_config_summary.

## 52. src/orchestrator/recovery_manager.py (330 lines)
Zombie scan O(N plus M): pre-collect queued plus processing IDs into sets, scan docsearch files keys, requeue pending-or-orphaned processing files to extraction as safe default with SizeCategory Priority coercion, legacy per-file method kept.

## 53. src/core/queue_manager.py (1961 lines)
SQLite WAL backend with thread-local connections, BEGIN IMMEDIATE atomic claims with 5min extraction-indexing plus 10min OCR-tagging stale reclaim, 11 tables with indexes, batch discovery insert, hash registries with duplicate counting, mark_completed failed stale-reset compatible with Redis signatures, full stats plus size rollups for dashboard, schema migrations adding missing columns, completed-items largest-files OCR-pending joins, discovery force-run plus complete flags, heartbeats, strict Redis-first singleton raising ConnectionError when Redis down, SQLite-to-Redis pending sync marking synced_to_redis, resettable singleton.

## 54. src/core/redis_queue_manager.py (2506 lines)
docsearch colon namespaced Redis backend. Pooled connections protocol 2 health-checked thread-local clients. Lua scripts for atomic root completion and OCR fallback counts. ZPOPMIN native with Redis-3 WATCH fallback. SADD atomic duplicate guard, INCR file IDs, pipelines everywhere. Discovery zset plus path map plus discovered counters. Extraction per-size zsets with ZPOPMIN claims and 30min processing hashes. Indexing FIFO list with MULTI EXEC LRANGE TRIM batch claims. OCR zset. Tagging list with sha1 fallback IDs. Root completion Lua skipping embedded children via parent map. One-pipeline stats snapshots, size stats, failure breakdown hash, counter bootstrap, zombie cleanup, missing-file reconcile with ghost counter and size drift repair, discovery flags with mtime-cache clear fix, metric self-heal, largest-files zset.

## 55. src/orchestrator/master_orchestrator.py (939 lines)
Spawns daemon mp processes per pool with sys.path fix. Full mode resets discovery plus clears Bloom files. Counter self-heal on drift. Discovery skip when complete, continuous rescan pushes root. Background startup recovery thread plus immediate stale reset. OCR stagger 8s. Main loop 30s or 10s continuous: worker respawn with 5-crashes-per-5min backoff, resource pause of discovery plus extraction on critical, SQLite-to-Redis migration attempt, 2min stale cleanup, checkpoints, work-complete log, dynamic reallocation moving idle extraction indexing OCR to tagging backlog capped 8 or small-backlog top-up to 4, memory guard 85 percent, graceful stop with checkpoint terminate grace kill reap, SIGINT SIGTERM handler.

## 56. src/core/reporting_manager.py (3506 lines)
_audit trail plus audit.db plus review snippets plus visual memory plus reporting. AuditEvent plus FileStateRow dataclasses. _ensure_schema creates 12 tables plus applied-patch introspection. Coverage plus histograms plus events plus accuracy plus tags into SQLite. Reports dir markdown csv plus 33-column and 23-column XLSX matrices with 7 accuracy sheets 8-sheet hybrid. Async export state matrix with readiness gates. Snippet reviews plus tag feedback plus page segmentation plus visual memory entries. Public module functions delegate to singleton.

## 57. src/main.py (1348 lines)
Click CLI: check validates Tika plus OpenSearch plus OCR, init creates dirs plus DB, start launches orchestrator in given mode, stop prefers API shutdown then psutil tree kill, status shows API progress or process plus queue snapshot, stats prints per-stage counts, reset clears 14 areas with verification, reset_stale requeues, validate checks packages, health_check service pings.

## 58. src/ui/review_tab.py (1639 lines)
Snippet Review portal. Type configs plus acceptance reasons plus status badges. Snippet cards with image plus impact plus mandatory accept reason plus typed verified content, auto-tag visual siblings at 0.90, indexes verified text into OpenSearch plus dynamic subtags. Waterfall chart plus page composition bars plus legacy bars. Sub-tabs activity log plus storage purge. Document selector groups embedded children under parents via Redis parent info.

## 59. src/ui/dashboard_state.py (295 lines)
Process-stable stats runtime with background fetch thread plus 2-worker executor. Intervals 5s queue 15s size, error backoff sleeps 1s to 20s. Last-known-good fallback plus 3s warmup, force_refresh, invalidate, clear, health diagnostics. st.cache_resource singleton.

## 60. src/ui/pdf_report.py (941 lines)
ReportLab A4 builders: single-doc report with metadata plus RADAR metrics plus snippet cards plus waterfall chart, system report with pipeline plus size plus taxonomy tables, answer transcript with verdict plus sources plus trace. Fresh styles plus colors each call for fork safety.

## 61. src/ui/ask_tab.py (74 lines)
_prod_search deferred import of OpenSearchClient plus build_prod_search_fn at first render, chunks to verdict markdown, trace tail, PDF download button, BLOCK path shows fail reasons instead of answer.

## 62. src/ui/dashboard.py (3616 lines)
Sidebar Search plus Ask plus Snippet Review plus Live Audit plus System Monitor plus Settings. Search tab multi_match over embedded_content main_content file_name tags with facets plus snippet fallback. Ask branch renders _render_ask_safe with no args. Cached queue plus size getters with Redis fallback, per-name singletons, parent-doc counters, review actions, live audit pre post orphan, monitor parent-only counts ETA parquet PDF, session reset, nav router, main.

## 63. tools (5 files)
clear_redis.py 57 lines deletes Bloom pkl plus flushdb localhost then 127.0.0.1. eval_answers.py 67 lines 8 golden questions recall floor 0.70 with live OpenSearch CLI. verify_metrics.py 24 lines polls 3 Redis counters 5 times. fix_stats.py 169 lines rescans HASH_COMPLETED rebuilds root counters plus size plus completed IDs plus bootstrap. validate_dashboard_numbers.py 390 lines 40 metric checks dashboard versus raw Redis with tolerance plus markdown report.

## 64. tests (6 files)
test_multi_agent_step1.py through step5.py 34 tests router plus guardrails plus retrieval plus rerank plus answer plus verifier plus graph plus ledger plus eval plus cost plus API plus PDF plus tenant plus injection plus PII, all passing. e2e_stress_full.py 93 live checks router through prod wiring plus 20-thread plus 50-query burst plus 1000-row rerank 0.01s plus 200-entry ledger verify.

## 65. config/config.yaml (529 lines)
Redis db1, spaCy md NLP on, tagging 2 workers hybrid with Excel metadata, source Testing data1, 4 Tika pools by size, OpenSearch enterprise_documents with field boosts, tesseract OCR with visual policy thresholds, orchestrator thresholds plus circuit breaker, API 8080 no auth, Bloom 10M at 0.001, sha256 file plus content dedup.

Status: COMPLETE. 65 entries, every src plus tools plus tests plus config file read word to word.

---
