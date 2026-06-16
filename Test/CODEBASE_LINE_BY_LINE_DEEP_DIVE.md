# Codebase Structural Line-by-Line Index

This file gives a line-referenced walkthrough of every Python file in the repository.

## Coverage

- Total Python files: 111
- Exclusions: .venv/, __pycache__/

## Deep Runtime Walkthrough (Core System)

This section explains the core runtime path with exact file/line anchors so you can connect intent to implementation quickly.

### 1) Bootstrap and process orchestration

- `src/main.py` L27-L33 defines the Click CLI group and command registration point.
- `src/main.py` L37-L133 (`check`) performs dependency health checks:
  - Tika endpoint checks across configured instances.
  - OpenSearch health endpoint checks.
  - Tesseract availability check.
- `src/main.py` L138-L236 (`init`) creates required directories and initializes system state:
  - Loads configuration via `get_config_manager`.
  - Initializes logging.
  - Initializes queue backend and verifies operational prerequisites.
- `src/main.py` L242-L279 (`start`) is the operational entrypoint:
  - Bootstraps logging early.
  - Instantiates `MasterOrchestrator`.
  - Starts system mode (`full`, `resume`, etc.) with worker processes.

- `src/orchestrator/master_orchestrator.py` L30-L504 controls lifecycle:
  - L51-L108: `start` initializes and starts all stage worker pools.
  - L125-L245: explicit spawn methods for discovery/extraction/indexing/OCR workers.
  - L299-L354: monitoring loop.
  - L356-L367: worker liveness checks.
  - L369-L449: respawn logic by worker id pattern.
  - L464-L499: coordinated shutdown.

### 2) Configuration and constants backbone

- `src/core/config_manager.py` L16-L251 defines all typed config dataclasses (paths, extraction pools, indexing, OCR, Redis, API, logging, alerting).
- `src/core/config_manager.py` L254-L565 (`ConfigurationManager`) is the source of truth for:
  - config file discovery/loading (`_find_config_file`, `_load_config`)
  - env overrides (`_load_environment_variables`)
  - invariants (`_validate_config`)
  - object materialization (`_create_config_objects`)
- `src/core/constants.py` L19-L393 centralizes statuses, stage enums, operational constants, timeouts, and alert categories used across modules.

### 3) Queue backend model (SQLite and Redis)

- `src/core/queue_manager.py` L30-L1521 implements SQLite-backed queue semantics:
  - discovery insertions and dedupe checks.
  - stage transition queues (extraction/indexing/ocr).
  - claim/complete/fail semantics per stage.
  - worker heartbeat writes and reads.
  - aggregate stats for dashboard/API.
- `src/core/queue_manager.py` L1530-L1681 provides backend selection and migration helpers:
  - singleton accessor (`get_queue_manager`)
  - redis usage checks/switch attempts
  - sqlite->redis synchronization helper.

- `src/core/redis_queue_manager.py` L31-L1918 implements high-throughput Redis queue semantics:
  - hash/set/list/zset-backed state model for stage queues.
  - claim and processing-key ownership tracking.
  - completion/failure accounting counters.
  - stale-processing recovery and reconciliation.
  - queue-size/statistics endpoints used by UI/API.
- `src/core/redis_queue_manager.py` L1926-L1948 provides singleton manager lifecycle.

### 4) Discovery -> extraction handoff

- `src/discovery/file_scanner.py` L35-L99 recursively scans configured roots with include/exclude filters.
- `src/discovery/hash_calculator.py` L29-L58 computes stable hashes for duplicate detection.
- `src/utils/bloom_filter.py` L20-L377 provides probabilistic duplicate prefiltering with persistence support.
- `src/discovery/discovery_worker.py` L90-L198 main loop:
  - scans files.
  - checks bloom + queue backend existence.
  - batches discovered files.
  - routes by size category.
- `src/discovery/discovery_worker.py` L200-L238 pushes discovered items into extraction queue with priority metadata.
- `src/discovery/discovery_worker.py` L271-L311 finalization marks discovery complete and logs summary.

### 5) Extraction and normalization

- `src/extraction/tika_client.py` L64-L164 performs HTTP extraction with retries/timeouts.
- `src/extraction/content_extractor.py` L23-L81 normalizes Tika output into canonical structure:
  - extracted text
  - metadata normalization
  - content hash
  - OCR eligibility decision.
- `src/extraction/extraction_worker.py` L95-L178 pulls extraction work, applies extraction pipeline, and emits indexing/OCR payloads.
- `src/extraction/extraction_worker.py` L180-L263 handles single-file extraction flow.
- `src/extraction/extraction_worker.py` L274-L306 builds indexable document payloads.
- `src/extraction/extraction_worker.py` L413-L537 handles embedded-content extraction and pipeline reinjection.

### 6) Indexing path and OpenSearch integration

- `src/indexing/document_builder.py` L86-L203 builds canonical OpenSearch documents (including embedded parent linkage).
- `src/indexing/indexing_worker.py` L60-L160 controls claim/accumulate/flush loop.
- `src/indexing/indexing_worker.py` L162-L339 performs batch indexing:
  - direct vs bulk indexing path.
  - queue completion/failure accounting.
  - retry/requeue behavior.
- `src/indexing/opensearch_client.py` L117-L314 ensures index mappings/settings.
- `src/indexing/opensearch_client.py` L429-L626 handles adaptive bulk indexing with error and circuit-breaker behavior.
- `src/indexing/opensearch_client.py` L349-L427 updates OCR fields into existing indexed docs.

### 7) OCR pipeline

- `src/ocr/ocr_worker.py` L144-L233 controls OCR worker main loop.
- `src/ocr/ocr_worker.py` L235-L341 orchestrates per-file OCR processing with validation.
- `src/ocr/ocr_worker.py` L343-L462 covers image OCR strategy path.
- `src/ocr/ocr_worker.py` L521-L652 covers PDF OCR path.
- `src/ocr/ocr_worker.py` L663-L699 flushes pending OCR updates into OpenSearch.
- `src/ocr/tesseract_wrapper.py` L110-L204 wraps Tesseract execution + confidence extraction.
- `src/ocr/image_preprocessor.py` and `src/ocr/image_preprocessor_advanced.py` provide baseline and advanced preprocessing (deskew, denoise, CLAHE, gamma, shadow cleanup, border removal, orientation fixes).

### 8) Query layer and observability surface

- `src/api/query_builder.py` L51-L313 builds accurate OpenSearch DSL variants:
  - phrase vs numeric vs generalized accurate query paths.
  - structured filter composition.
- `src/api/search_api.py` L73-L132 handles API search endpoint and response wrapping.
- `src/api/search_api.py` L158-L206 exposes queue/system metrics to operators.
- `src/ui/dashboard.py` L701-L2084 is the operations cockpit:
  - cached stats fetch and fallback logic.
  - queue and throughput visualization.
  - failure analysis views.
  - operator search panel with OCR-aware query variants.

### 9) Supporting resilience modules

- `src/orchestrator/checkpoint_manager.py` handles checkpoint save/load boundaries for restart safety.
- `src/orchestrator/recovery_manager.py` handles stale processing and resume recovery operations.
- `src/orchestrator/health_monitor.py` and `src/orchestrator/resource_monitor.py` provide health/resource observation hooks.
- `src/tools/fix_stats.py`, `src/tools/verify_metrics.py`, and `src/tools/clear_redis.py` provide repair/verification utilities for production operations.

## Production Source (src/)

### `src/api/__init__.py` (6 lines)
- Module intent: API - Search API and dashboard
- L3-L4: import section wires external dependencies and local modules.
- L6-L6: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/api/query_builder.py` (313 lines)
- Module intent: Query Builder - Constructs OpenSearch query DSL
- L7-L11: import section wires external dependencies and local modules.
- L13-L13: module constants/config defaults are declared.
- Walkthrough:
  - L16-L313: class `QueryBuilder` defines state + behavior (7 methods).
  - L33-L44: method `__init__` executes its unit of logic (key calls: get, get_config).
  - L46-L49: method `_is_numeric_query` executes its unit of logic (key calls: bool, match, strip).
  - L51-L121: method `build_search_query` executes its unit of logic (key calls: _build_accurate_query, _build_numeric_query, _build_phrase_query, _is_numeric_query, endswith, startswith).
  - L123-L146: method `_build_phrase_query` executes its unit of logic (key calls: append, get).
  - L148-L189: method `_build_numeric_query` executes its unit of logic (key calls: append, get).
  - L191-L253: method `_build_accurate_query` executes its unit of logic (key calls: any, append, get, len, startswith, warning).
  - L255-L313: method `build_filter_query` executes its unit of logic (key calls: append, get, isinstance, items).

### `src/api/search_api.py` (216 lines)
- Module intent: Search API - FastAPI REST endpoints
- L5-L15: import section wires external dependencies and local modules.
- L17-L31: module constants/config defaults are declared.
- Walkthrough:
  - L44-L59: function `verify_token` contains callable workflow logic (key calls: HTTPException, Header, compare_digest, getenv, replace).
  - L63-L69: function `root` contains callable workflow logic (key calls: get).
  - L73-L132: function `search` contains callable workflow logic (key calls: Depends, HTTPException, Query, build_search_query, error, get).
  - L136-L154: function `get_document` contains callable workflow logic (key calls: Depends, HTTPException, error, get).
  - L158-L190: function `get_status` contains callable workflow logic (key calls: HTTPException, error, get, get_queue_stats, round, str).
  - L194-L206: function `get_metrics` contains callable workflow logic (key calls: Depends, HTTPException, error, get, get_queue_stats, get_stats).

### `src/core/__init__.py` (19 lines)
- Module intent: Enterprise Document Search System - Core Module
- L8-L11: import section wires external dependencies and local modules.
- L6-L19: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/core/config_manager.py` (597 lines)
- Module intent: Enterprise Document Search System - Configuration Manager
- L6-L12: import section wires external dependencies and local modules.
- L569-L569: module constants/config defaults are declared.
- Walkthrough:
  - L16-L26: class `PathConfig` defines state + behavior (0 methods).
  - L30-L35: class `TikaInstance` defines state + behavior (0 methods).
  - L39-L45: class `TikaConfig` defines state + behavior (0 methods).
  - L49-L54: class `WorkerPool` defines state + behavior (0 methods).
  - L58-L70: class `DiscoveryConfig` defines state + behavior (0 methods).
  - L74-L80: class `ExtractionConfig` defines state + behavior (0 methods).
  - L84-L108: class `OpenSearchConfig` defines state + behavior (0 methods).
  - L112-L116: class `IndexingConfig` defines state + behavior (0 methods).
  - L120-L127: class `TesseractConfig` defines state + behavior (0 methods).
  - L131-L144: class `OCRConfig` defines state + behavior (0 methods).
  - L148-L159: class `OrchestratorConfig` defines state + behavior (0 methods).
  - L163-L167: class `NLPConfig` defines state + behavior (0 methods).
  - L171-L175: class `RedisConfig` defines state + behavior (0 methods).
  - L179-L186: class `LoggingConfig` defines state + behavior (0 methods).
  - L190-L201: class `EmailConfig` defines state + behavior (0 methods).
  - L205-L212: class `AlertingConfig` defines state + behavior (0 methods).
  - L216-L228: class `APIConfig` defines state + behavior (0 methods).
  - L232-L251: class `SystemConfig` defines state + behavior (0 methods).
  - L254-L565: class `ConfigurationManager` defines state + behavior (10 methods).
  - L260-L277: method `__init__` executes its unit of logic (key calls: Path, _create_config_objects, _find_config_file, _load_config, _load_environment_variables, _validate_config).
  - L279-L293: method `_find_config_file` executes its unit of logic (key calls: FileNotFoundError, Path, exists, join).
  - L295-L301: method `_load_config` executes its unit of logic (key calls: FileNotFoundError, exists, open, safe_load).
  - L303-L348: method `_load_environment_variables` executes its unit of logic (key calls: getenv, split, strip).
  - L350-L376: method `_validate_config` executes its unit of logic (key calls: ValueError, len).
  - L378-L501: method `_create_config_objects` executes its unit of logic (key calls: APIConfig, AlertingConfig, DiscoveryConfig, EmailConfig, ExtractionConfig, IndexingConfig).
  - L503-L507: method `get_config` executes its unit of logic (key calls: RuntimeError).
  - L509-L513: method `get_section` executes its unit of logic (key calls: KeyError).
  - L515-L535: method `ensure_directories` executes its unit of logic (key calls: Path, RuntimeError, append, mkdir).
  - L537-L565: method `print_config_summary` executes its unit of logic (key calls: RuntimeError, join, print).
  - L572-L587: function `get_config_manager` contains callable workflow logic (key calls: ConfigurationManager).
  - L590-L597: function `get_config` contains callable workflow logic (key calls: get_config, get_config_manager).

### `src/core/constants.py` (393 lines)
- Module intent: Enterprise Document Search System - Constants
- L6-L7: import section wires external dependencies and local modules.
- L12-L393: module constants/config defaults are declared.
- Walkthrough:
  - L19-L26: class `QueueStatus` defines state + behavior (0 methods).
  - L31-L36: class `SizeCategory` defines state + behavior (0 methods).
  - L46-L51: class `WorkerPoolType` defines state + behavior (0 methods).
  - L56-L62: class `ProcessingStage` defines state + behavior (0 methods).
  - L67-L82: class `ErrorType` defines state + behavior (0 methods).
  - L87-L92: class `HealthStatus` defines state + behavior (0 methods).
  - L97-L104: class `WorkerStatus` defines state + behavior (0 methods).
  - L109-L113: class `DuplicateType` defines state + behavior (0 methods).
  - L118-L124: class `OCRStatus` defines state + behavior (0 methods).
  - L129-L136: class `Priority` defines state + behavior (0 methods).
  - L299-L303: class `OperationalMode` defines state + behavior (0 methods).
  - L308-L312: class `AlertType` defines state + behavior (0 methods).

### `src/core/logging_manager.py` (277 lines)
- Module intent: Enterprise Document Search System - Logging Manager
- L6-L15: import section wires external dependencies and local modules.
- Walkthrough:
  - L18-L40: class `SafeRotatingFileHandler` defines state + behavior (1 methods).
  - L26-L40: method `doRollover` executes its unit of logic (key calls: doRollover, print, super).
  - L43-L259: class `LoggerManager` defines state + behavior (10 methods).
  - L53-L117: method `initialize` executes its unit of logic (key calls: Formatter, Path, SafeRotatingFileHandler, StreamHandler, _create_json_formatter, addHandler).
  - L120-L132: method `_create_json_formatter` executes its unit of logic (key calls: Formatter, JSONFormatter, get_config, warning).
  - L135-L204: method `get_logger` executes its unit of logic (key calls: Formatter, Path, SafeRotatingFileHandler, addHandler, getLogger, get_config).
  - L207-L209: method `get_discovery_logger` executes its unit of logic (key calls: get_logger).
  - L212-L214: method `get_extraction_logger` executes its unit of logic (key calls: get_logger).
  - L217-L219: method `get_indexing_logger` executes its unit of logic (key calls: get_logger).
  - L222-L224: method `get_ocr_logger` executes its unit of logic (key calls: get_logger).
  - L227-L229: method `get_orchestrator_logger` executes its unit of logic (key calls: get_logger).
  - L232-L234: method `get_api_logger` executes its unit of logic (key calls: get_logger).
  - L237-L259: method `shutdown` executes its unit of logic (key calls: clear, close, flush, getLogger, info, removeHandler).
  - L262-L264: function `setup_logging` contains callable workflow logic (key calls: initialize).
  - L267-L277: function `get_logger` contains callable workflow logic (key calls: get_logger).

### `src/core/queue_manager.py` (1681 lines)
- Module intent: Enterprise Document Search System - Queue Manager
- L6-L24: import section wires external dependencies and local modules.
- L22-L1527: module constants/config defaults are declared.
- Walkthrough:
  - L30-L1521: class `QueueManager` defines state + behavior (42 methods).
  - L36-L57: method `__init__` executes its unit of logic (key calls: Path, RLock, _initialize_database, get_config, info, local).
  - L59-L96: method `reset_database` executes its unit of logic (key calls: _get_connection, _initialize_database, cursor, error, execute, info).
  - L99-L139: method `_get_connection` executes its unit of logic (key calls: close, connect, error, execute, hasattr, sleep).
  - L141-L341: method `_initialize_database` executes its unit of logic (key calls: _apply_schema_migrations, _get_connection, commit, cursor, error, execute).
  - L347-L385: method `add_discovered_file` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, now, timestamp).
  - L387-L428: method `add_discovered_files_batch` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, get, now).
  - L430-L448: method `check_file_hash_exists` executes its unit of logic (key calls: _get_connection, cursor, execute, fetchone).
  - L454-L476: method `add_to_extraction_queue` executes its unit of logic (key calls: _get_connection, commit, cursor, execute).
  - L478-L546: method `claim_extraction_work` executes its unit of logic (key calls: _get_connection, commit, cursor, dict, error, execute).
  - L548-L571: method `complete_extraction` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, now, timestamp).
  - L577-L593: method `add_to_indexing_queue` executes its unit of logic (key calls: _get_connection, commit, cursor, execute).
  - L595-L645: method `claim_indexing_work` executes its unit of logic (key calls: _get_connection, commit, cursor, dict, error, execute).
  - L647-L661: method `complete_indexing_batch` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, join, len).
  - L663-L697: method `requeue_indexing_items` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, insert, join).
  - L699-L720: method `fail_indexing_items` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, join, len).
  - L726-L748: method `add_to_ocr_queue` executes its unit of logic (key calls: _get_connection, commit, cursor, execute).
  - L750-L800: method `claim_ocr_work` executes its unit of logic (key calls: _get_connection, commit, cursor, dict, error, execute).
  - L802-L828: method `complete_ocr` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, now, timestamp).
  - L834-L868: method `register_file_hash` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, now, timestamp).
  - L870-L913: method `register_content_hash` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, fetchone, now).
  - L919-L946: method `mark_completed` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, now, timestamp).
  - L948-L975: method `mark_file_completed` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, fetchone, now).
  - L977-L1007: method `reset_stale_processing` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, info, now).
  - L1009-L1033: method `mark_failed` executes its unit of logic (key calls: _get_connection, commit, cursor, execute, now, timestamp).
  - L1035-L1052: method `mark_file_failed` executes its unit of logic (key calls: mark_failed).
  - L1058-L1146: method `get_queue_statistics` executes its unit of logic (key calls: _get_connection, cursor, dict, execute, fetchall, fetchone).
  - L1148-L1249: method `get_size_statistics` executes its unit of logic (key calls: _get_connection, cursor, execute, fetchone).
  - L1251-L1261: method `get_file_info` executes its unit of logic (key calls: _get_connection, cursor, dict, execute, fetchone).
  - L1263-L1302: method `_apply_schema_migrations` executes its unit of logic (key calls: commit, cursor, error, execute, fetchall, info).
  - L1304-L1347: method `get_queue_stats` executes its unit of logic (key calls: _get_connection, cursor, execute, fetchall).
  - L1349-L1362: method `get_failed_files` executes its unit of logic (key calls: _get_connection, cursor, dict, execute, fetchall).
  - L1364-L1380: method `get_largest_completed_files` executes its unit of logic (key calls: _get_connection, cursor, dict, execute, fetchall).
  - L1382-L1396: method `get_ocr_pending_files` executes its unit of logic (key calls: _get_connection, cursor, dict, execute, fetchall).
  - L1398-L1408: method `is_file_processed` executes its unit of logic (key calls: _get_connection, cursor, execute, fetchone).
  - L1410-L1413: method `reset_discovery_completion_flag` executes its unit of logic (key calls: info).
  - L1415-L1443: method `is_discovery_complete` executes its unit of logic (key calls: _get_connection, cursor, execute, fetchone).
  - L1445-L1475: method `check_file_exists` executes its unit of logic (key calls: _get_connection, abs, cursor, error, execute, fetchone).
  - L1477-L1481: method `mark_discovery_complete` executes its unit of logic (key calls: info).
  - L1483-L1494: method `update_worker_heartbeat` executes its unit of logic (key calls: _get_connection, commit, cursor, error, execute, now).
  - L1496-L1505: method `get_worker_heartbeats` executes its unit of logic (key calls: _get_connection, cursor, error, execute, fetchall).
  - L1507-L1515: method `remove_worker_heartbeat` executes its unit of logic (key calls: _get_connection, commit, cursor, error, execute).
  - L1517-L1521: method `close` executes its unit of logic (key calls: close, hasattr).
  - L1530-L1560: function `get_queue_manager` contains callable workflow logic (key calls: ConnectionError, RedisQueueManager, error, info, ping).
  - L1563-L1566: function `is_using_redis` contains callable workflow logic (key calls: none).
  - L1569-L1600: function `try_switch_to_redis` contains callable workflow logic (key calls: RedisQueueManager, debug, info, isinstance, ping, sync_sqlite_to_redis).
  - L1603-L1666: function `sync_sqlite_to_redis` contains callable workflow logic (key calls: Priority, SizeCategory, _get_connection, add_to_extraction_queue, commit, cursor).
  - L1669-L1681: function `reset_queue_manager` contains callable workflow logic (key calls: close).

### `src/core/redis_queue_manager.py` (1948 lines)
- Module intent: Enterprise Document Search System - Redis Queue Manager
- L7-L25: import section wires external dependencies and local modules.
- L28-L1923: module constants/config defaults are declared.
- Walkthrough:
  - L31-L1918: class `RedisQueueManager` defines state + behavior (60 methods).
  - L90-L129: method `__init__` executes its unit of logic (key calls: RLock, _register_scripts, from_url, get_config, getattr, info).
  - L131-L156: method `_register_scripts` executes its unit of logic (key calls: register_script).
  - L159-L163: method `client` executes its unit of logic (key calls: Redis, hasattr).
  - L165-L171: method `_get_extraction_processing_keys` executes its unit of logic (key calls: append, range).
  - L173-L178: method `_get_indexing_processing_keys` executes its unit of logic (key calls: append, range).
  - L180-L185: method `_get_ocr_processing_keys` executes its unit of logic (key calls: append, range).
  - L187-L200: method `reset_database` executes its unit of logic (key calls: delete, error, info, keys).
  - L202-L204: method `_generate_file_id` executes its unit of logic (key calls: incr).
  - L206-L240: method `_zpopmin_compat` executes its unit of logic (key calls: _zpopmin_compat, error, execute, multi, pipeline, sleep).
  - L246-L283: method `check_file_exists` executes its unit of logic (key calls: abs, decode, error, float, get, hget).
  - L285-L343: method `add_discovered_file` executes its unit of logic (key calls: _generate_file_id, error, execute, hmset, hset, incr).
  - L345-L406: method `add_discovered_files_batch` executes its unit of logic (key calls: _generate_file_id, error, execute, get, hmset, hset).
  - L408-L423: method `check_file_hash_exists` executes its unit of logic (key calls: error, hget, loads).
  - L429-L462: method `add_to_extraction_queue` executes its unit of logic (key calls: dumps, error, now, str, timestamp, zadd).
  - L464-L513: method `claim_extraction_work` executes its unit of logic (key calls: _zpopmin_compat, append, dumps, error, expire, hset).
  - L515-L552: method `complete_extraction` executes its unit of logic (key calls: debug, error, execute, hdel, hget, hset).
  - L554-L576: method `get_extraction_queue_size` executes its unit of logic (key calls: error, zcard).
  - L582-L604: method `add_to_indexing_queue` executes its unit of logic (key calls: dumps, error, lpush, now, timestamp).
  - L606-L649: method `claim_indexing_work` executes its unit of logic (key calls: append, error, execute, expire, hset, loads).
  - L651-L677: method `complete_indexing` executes its unit of logic (key calls: error, execute, hdel, hset, now, pipeline).
  - L683-L709: method `add_to_ocr_queue` executes its unit of logic (key calls: dumps, error, now, timestamp, zadd).
  - L711-L744: method `claim_ocr_work` executes its unit of logic (key calls: _zpopmin_compat, append, dumps, error, expire, hset).
  - L746-L778: method `complete_ocr` executes its unit of logic (key calls: error, hdel, hmset, incr, now, range).
  - L780-L795: method `complete_indexing_batch` executes its unit of logic (key calls: error, hdel, range, str).
  - L797-L824: method `requeue_indexing_items` executes its unit of logic (key calls: _get_indexing_processing_keys, dumps, error, get, hdel, hget).
  - L826-L859: method `fail_indexing_items` executes its unit of logic (key calls: _get_indexing_processing_keys, error, get, hdel, hget, info).
  - L861-L921: method `reset_stale_processing` executes its unit of logic (key calls: delete, error, get, hgetall, hvals, info).
  - L927-L1032: method `mark_file_completed` executes its unit of logic (key calls: dumps, error, execute, get, hexists, hgetall).
  - L1034-L1064: method `mark_file_failed` executes its unit of logic (key calls: dumps, error, execute, hasattr, hincrby, hset).
  - L1069-L1086: method `_get_worker_keys` executes its unit of logic (key calls: get, list, scan_iter, time).
  - L1088-L1104: method `_count_processing_items` executes its unit of logic (key calls: _get_worker_keys, execute, hlen, isinstance, pipeline, sum).
  - L1106-L1134: method `_get_extraction_processing_stats` executes its unit of logic (key calls: _get_worker_keys, error, execute, get, hvals, isinstance).
  - L1136-L1238: method `get_queue_stats` executes its unit of logic (key calls: _count_processing_items, _get_cached_ocr_count, _get_extraction_processing_stats, enumerate, error, execute).
  - L1240-L1320: method `get_queue_statistics` executes its unit of logic (key calls: _get_failure_breakdown, get, get_completed_files_stats, get_queue_stats, int, safe_int).
  - L1322-L1353: method `_get_failure_breakdown` executes its unit of logic (key calls: error, execute, get, hgetall, hscan, hset).
  - L1355-L1429: method `get_size_statistics` executes its unit of logic (key calls: error, get, hlen, int, llen, max).
  - L1431-L1479: method `initialize_completed_counters` executes its unit of logic (key calls: error, get, hscan, info, items, loads).
  - L1481-L1503: method `get_failed_files` executes its unit of logic (key calls: append, error, hscan, items, loads, min).
  - L1505-L1514: method `get_file_info` executes its unit of logic (key calls: error, hgetall, items).
  - L1516-L1518: method `get_completed_items` executes its unit of logic (key calls: none).
  - L1524-L1526: method `push_folder` executes its unit of logic (key calls: rpush).
  - L1528-L1530: method `pop_folder` executes its unit of logic (key calls: lpop).
  - L1532-L1534: method `get_folder_mtime` executes its unit of logic (key calls: hget).
  - L1536-L1538: method `set_folder_mtime` executes its unit of logic (key calls: hset).
  - L1540-L1577: method `get_largest_completed_files` executes its unit of logic (key calls: append, error, get, hget, hscan, items).
  - L1579-L1594: method `get_ocr_pending_files` executes its unit of logic (key calls: append, error, loads, zrange).
  - L1596-L1605: method `reset_database` executes its unit of logic (key calls: delete, error, info, keys).
  - L1607-L1651: method `get_completed_files_stats` executes its unit of logic (key calls: error, get, hlen, int).
  - L1654-L1659: method `_get_cached_ocr_count` executes its unit of logic (key calls: get, int).
  - L1662-L1668: method `get_file_hash_by_id` executes its unit of logic (key calls: error, hget).
  - L1676-L1682: method `mark_discovery_complete` executes its unit of logic (key calls: error, info, set).
  - L1684-L1690: method `is_discovery_complete` executes its unit of logic (key calls: error, exists).
  - L1692-L1698: method `reset_discovery_completion_flag` executes its unit of logic (key calls: delete, error, info).
  - L1700-L1702: method `is_file_processed` executes its unit of logic (key calls: sismember).
  - L1704-L1736: method `validate_metrics` executes its unit of logic (key calls: abs, error, get, get_queue_stats, int, scard).
  - L1738-L1743: method `remove_worker_heartbeat` executes its unit of logic (key calls: error, hdel).
  - L1745-L1750: method `update_worker_heartbeat` executes its unit of logic (key calls: error, hset, now, timestamp).
  - L1752-L1764: method `get_worker_heartbeats` executes its unit of logic (key calls: decode, error, float, hgetall, isinstance, items).
  - L1766-L1771: method `close` executes its unit of logic (key calls: debug, disconnect).
  - L1773-L1918: method `reconcile_missing_files` executes its unit of logic (key calls: decode, error, get, hexists, hlen, hscan).
  - L1926-L1935: function `get_redis_queue_manager` contains callable workflow logic (key calls: RedisQueueManager).
  - L1938-L1948: function `reset_redis_queue_manager` contains callable workflow logic (key calls: close, warning).

### `src/discovery/__init__.py` (7 lines)
- Module intent: Discovery stage - File scanning and hashing
- L3-L5: import section wires external dependencies and local modules.
- L7-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/discovery/discovery_worker.py` (354 lines)
- Module intent: Discovery Worker - Orchestrates file scanning, hashing, and queue insertion
- L5-L19: import section wires external dependencies and local modules.
- L21-L21: module constants/config defaults are declared.
- Walkthrough:
  - L24-L354: class `DiscoveryWorker` defines state + behavior (12 methods).
  - L27-L61: method `__init__` executes its unit of logic (key calls: FileScanner, HashCalculator, Path, _initialize_bloom_filter, get_config, get_queue_manager).
  - L63-L88: method `_initialize_bloom_filter` executes its unit of logic (key calls: BloomFilter, exists, info, load_from_file, populate_from_database, str).
  - L90-L198: method `run` executes its unit of logic (key calls: Thread, _log_final_stats, _log_progress, _process_batch, _save_bloom_filter, add).
  - L200-L238: method `_process_batch` executes its unit of logic (key calls: Priority, _categorize_file_size, add_discovered_file, add_to_extraction_queue, error).
  - L240-L251: method `_categorize_file_size` executes its unit of logic (key calls: none).
  - L253-L269: method `_log_progress` executes its unit of logic (key calls: info, time).
  - L271-L311: method `_log_final_stats` executes its unit of logic (key calls: get_stats, getattr, info, len, llen, mark_discovery_complete).
  - L313-L316: method `_signal_handler` executes its unit of logic (key calls: info, stop).
  - L318-L325: method `_save_bloom_filter` executes its unit of logic (key calls: error, info, save_to_file, str).
  - L327-L331: method `stop` executes its unit of logic (key calls: _save_bloom_filter, info).
  - L333-L345: method `get_stats` executes its unit of logic (key calls: time).
  - L347-L354: method `_heartbeat_loop` executes its unit of logic (key calls: sleep, update_worker_heartbeat).

### `src/discovery/file_scanner.py` (174 lines)
- Module intent: File Scanner - Recursive directory traversal with filtering
- L5-L12: import section wires external dependencies and local modules.
- L14-L14: module constants/config defaults are declared.
- Walkthrough:
  - L17-L174: class `FileScanner` defines state + behavior (8 methods).
  - L20-L33: method `__init__` executes its unit of logic (key calls: get_config).
  - L35-L99: method `scan_folder` executes its unit of logic (key calls: Path, _get_file_metadata, _should_exclude, _should_process_file, abs, append).
  - L101-L103: method `_walk_directory` executes its unit of logic (key calls: none).
  - L105-L114: method `_should_exclude` executes its unit of logic (key calls: fnmatch).
  - L116-L132: method `_should_process_file` executes its unit of logic (key calls: lower, splitext).
  - L134-L152: method `_get_file_metadata` executes its unit of logic (key calls: _calculate_priority, lower, splitext, stat).
  - L154-L166: method `_calculate_priority` executes its unit of logic (key calls: get, lower).
  - L168-L174: method `get_stats` executes its unit of logic (key calls: none).

### `src/discovery/hash_calculator.py` (104 lines)
- Module intent: Hash Calculator - Efficient file hashing with memory mapping
- L5-L10: import section wires external dependencies and local modules.
- L12-L12: module constants/config defaults are declared.
- Walkthrough:
  - L15-L104: class `HashCalculator` defines state + behavior (5 methods).
  - L24-L27: method `__init__` executes its unit of logic (key calls: none).
  - L29-L58: method `calculate_hash` executes its unit of logic (key calls: Path, _hash_standard, _hash_with_mmap, stat, warning).
  - L60-L76: method `_hash_standard` executes its unit of logic (key calls: hexdigest, open, read, sha256, update, warning).
  - L78-L96: method `_hash_with_mmap` executes its unit of logic (key calls: _hash_standard, fileno, hexdigest, len, mmap, open).
  - L98-L104: method `get_stats` executes its unit of logic (key calls: none).

### `src/extraction/__init__.py` (7 lines)
- Module intent: Extraction stage - Tika integration and content extraction
- L3-L5: import section wires external dependencies and local modules.
- L7-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/extraction/content_extractor.py` (235 lines)
- Module intent: Content Extractor - Parses Tika responses and normalizes content
- L5-L10: import section wires external dependencies and local modules.
- L12-L12: module constants/config defaults are declared.
- Walkthrough:
  - L15-L235: class `ContentExtractor` defines state + behavior (8 methods).
  - L18-L21: method `__init__` executes its unit of logic (key calls: get_config).
  - L23-L81: method `process_tika_response` executes its unit of logic (key calls: _calculate_content_hash, _extract_embedded, _extract_metadata, _extract_text_content, _normalize_content, _should_run_ocr).
  - L83-L94: method `_extract_text_content` executes its unit of logic (key calls: get, isinstance, join, str, strip).
  - L96-L144: method `_extract_metadata` executes its unit of logic (key calls: get, int, isinstance, lower, replace, split).
  - L146-L172: method `_normalize_content` executes its unit of logic (key calls: get, lower, strip, sub).
  - L174-L179: method `_calculate_content_hash` executes its unit of logic (key calls: encode, hexdigest, sha256).
  - L181-L211: method `_should_run_ocr` executes its unit of logic (key calls: any, get, len, lower, startswith, strip).
  - L213-L235: method `_extract_embedded` executes its unit of logic (key calls: _extract_metadata, _extract_text_content, get).

### `src/extraction/extraction_worker.py` (545 lines)
- Module intent: Extraction Worker - Pulls from extraction queue and processes with Tika
- L6-L27: import section wires external dependencies and local modules.
- L36-L36: module constants/config defaults are declared.
- Walkthrough:
  - L39-L545: class `ExtractionWorker` defines state + behavior (13 methods).
  - L42-L93: method `__init__` executes its unit of logic (key calls: ContentExtractor, TikaClient, ValueError, debug, get_config, get_queue_manager).
  - L95-L178: method `run` executes its unit of logic (key calls: Process, Thread, _log_final_stats, _log_progress, _process_file, claim_extraction_work).
  - L180-L263: method `_process_file` executes its unit of logic (key calls: Priority, _build_document, _extract_embedded_content, _get_file_hash, _handle_failure, add_to_indexing_queue).
  - L265-L272: method `_get_file_hash` executes its unit of logic (key calls: get, get_file_info, warning).
  - L274-L306: method `_build_document` executes its unit of logic (key calls: correct, debug, get, isoformat, now, warning).
  - L308-L331: method `_handle_failure` executes its unit of logic (key calls: complete_extraction, debug, mark_file_failed).
  - L333-L365: method `_log_progress` executes its unit of logic (key calls: get_extraction_queue_size, info, time, warning).
  - L367-L390: method `_log_final_stats` executes its unit of logic (key calls: get_stats, info, time).
  - L392-L395: method `stop` executes its unit of logic (key calls: info).
  - L397-L411: method `get_stats` executes its unit of logic (key calls: time).
  - L413-L467: method `_extract_embedded_content` executes its unit of logic (key calls: Path, ZipFile, _inject_file, copyfileobj, debug, endswith).
  - L469-L537: method `_inject_file` executes its unit of logic (key calls: add_discovered_file, add_to_extraction_queue, getattr, hexdigest, hset, info).
  - L538-L545: method `_heartbeat_loop` executes its unit of logic (key calls: sleep, update_worker_heartbeat).

### `src/extraction/tika_client.py` (217 lines)
- Module intent: Tika Client - HTTP client for Apache Tika with connection pooling and retry logic
- L5-L13: import section wires external dependencies and local modules.
- L15-L15: module constants/config defaults are declared.
- Walkthrough:
  - L18-L217: class `TikaClient` defines state + behavior (10 methods).
  - L21-L38: method `__init__` executes its unit of logic (key calls: _create_session, get_config).
  - L40-L62: method `_create_session` executes its unit of logic (key calls: HTTPAdapter, Retry, Session, mount).
  - L64-L164: method `extract` executes its unit of logic (key calls: debug, error, getsize, int, isinstance, json).
  - L166-L172: method `health_check` executes its unit of logic (key calls: get).
  - L174-L182: method `get_version` executes its unit of logic (key calls: get, strip).
  - L184-L196: method `get_stats` executes its unit of logic (key calls: int).
  - L198-L201: method `close` executes its unit of logic (key calls: close).
  - L203-L205: method `__enter__` executes its unit of logic (key calls: none).
  - L207-L210: method `__exit__` executes its unit of logic (key calls: close).
  - L212-L217: method `__del__` executes its unit of logic (key calls: close).

### `src/indexing/__init__.py` (7 lines)
- Module intent: Indexing stage - OpenSearch integration and bulk indexing
- L3-L5: import section wires external dependencies and local modules.
- L7-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/indexing/document_builder.py` (224 lines)
- Module intent: Document Builder - Constructs OpenSearch documents from extraction data
- L5-L12: import section wires external dependencies and local modules.
- L14-L21: module constants/config defaults are declared.
- Walkthrough:
  - L24-L224: class `DocumentBuilder` defines state + behavior (6 methods).
  - L27-L41: method `__init__` executes its unit of logic (key calls: get_config, getattr).
  - L43-L55: method `_get_redis` executes its unit of logic (key calls: Redis, get_config, getattr).
  - L57-L68: method `_lookup_parent_hash` executes its unit of logic (key calls: _get_redis, hget).
  - L70-L84: method `_truncate_content` executes its unit of logic (key calls: len, rfind, warning).
  - L86-L203: method `build_document` executes its unit of logic (key calls: Path, _lookup_parent_hash, _truncate_content, append, error, get).
  - L205-L224: method `build_ocr_update` executes its unit of logic (key calls: _truncate_content, isoformat, now).

### `src/indexing/indexing_worker.py` (425 lines)
- Module intent: Indexing Worker - Pulls from indexing queue and bulk indexes to OpenSearch
- L5-L16: import section wires external dependencies and local modules.
- L18-L18: module constants/config defaults are declared.
- Walkthrough:
  - L21-L425: class `IndexingWorker` defines state + behavior (8 methods).
  - L24-L58: method `__init__` executes its unit of logic (key calls: DocumentBuilder, OpenSearchClient, RuntimeError, ensure_index, get_config, get_queue_manager).
  - L60-L160: method `run` executes its unit of logic (key calls: Thread, _log_final_stats, _log_progress, _process_batch, claim_indexing_work, debug).
  - L162-L339: method `_process_batch` executes its unit of logic (key calls: append, build_document, bulk_index, complete_indexing_batch, error, fail_indexing_items).
  - L341-L374: method `_log_progress` executes its unit of logic (key calls: get, get_queue_stats, get_stats, info, time, warning).
  - L376-L395: method `_log_final_stats` executes its unit of logic (key calls: get_stats, info, time).
  - L397-L401: method `stop` executes its unit of logic (key calls: close, info).
  - L403-L411: method `_heartbeat_loop` executes its unit of logic (key calls: sleep, update_worker_heartbeat).
  - L413-L425: method `get_stats` executes its unit of logic (key calls: time).

### `src/indexing/opensearch_client.py` (712 lines)
- Module intent: OpenSearch Client - Bulk indexing with adaptive batching and circuit breaker
- L5-L11: import section wires external dependencies and local modules.
- L13-L13: module constants/config defaults are declared.
- Walkthrough:
  - L16-L712: class `OpenSearchClient` defines state + behavior (14 methods).
  - L19-L49: method `__init__` executes its unit of logic (key calls: _create_client, get_config).
  - L51-L79: method `_create_client` executes its unit of logic (key calls: OpenSearch, append, int, split).
  - L81-L115: method `wait_for_availability` executes its unit of logic (key calls: ConnectionError, error, health, info, max, min).
  - L117-L314: method `ensure_index` executes its unit of logic (key calls: create, error, exists, get, info, lower).
  - L316-L347: method `index_document_direct` executes its unit of logic (key calls: debug, error, get, index, warning).
  - L349-L427: method `update_document_ocr` executes its unit of logic (key calls: debug, error, get, range, sleep, update).
  - L429-L626: method `bulk_index` executes its unit of logic (key calls: _adapt_batch_size, _open_circuit, _reduce_batch_size_on_failure, append, bulk, bulk_index).
  - L628-L648: method `_adapt_batch_size` executes its unit of logic (key calls: debug, max, min).
  - L650-L659: method `_reduce_batch_size_on_failure` executes its unit of logic (key calls: debug, max).
  - L661-L665: method `_open_circuit` executes its unit of logic (key calls: error, time).
  - L667-L678: method `update_document` executes its unit of logic (key calls: error, update).
  - L680-L689: method `set_refresh_interval` executes its unit of logic (key calls: info, put_settings, warning).
  - L691-L697: method `health_check` executes its unit of logic (key calls: health).
  - L699-L712: method `get_stats` executes its unit of logic (key calls: int).

### `src/main.py` (902 lines)
- Module intent: Enterprise Document Search System - Main Entry Point
- L7-L22: import section wires external dependencies and local modules.
- Walkthrough:
  - L27-L33: function `cli` contains callable workflow logic (key calls: group, version_option).
  - L37-L133: function `check` contains callable workflow logic (key calls: command, echo, get, get_config, json, print_exc).
  - L138-L236: function `init` contains callable workflow logic (key calls: command, echo, ensure_directories, exit, get, get_config).
  - L242-L279: function `start` contains callable workflow logic (key calls: Choice, MasterOrchestrator, command, echo, error, exit).
  - L283-L306: function `stop` contains callable workflow logic (key calls: command, echo, get_config, post, secho).
  - L310-L358: function `status` contains callable workflow logic (key calls: command, echo, get, get_config, json, now).
  - L362-L432: function `stats` contains callable workflow logic (key calls: command, echo, get, get_queue_manager, get_queue_statistics, items).
  - L437-L688: function `reset` contains callable workflow logic (key calls: OpenSearch, Path, RedisQueueManager, append, collect, command).
  - L693-L732: function `reset_stale` contains callable workflow logic (key calls: command, echo, get_queue_manager, option, print_exc, reset_stale_processing).
  - L736-L804: function `validate` contains callable workflow logic (key calls: Path, __import__, append, command, echo, exists).
  - L811-L898: function `health_check` contains callable workflow logic (key calls: command, echo, get, get_config, json, print_exc).

### `src/nlp/__init__.py` (7 lines)
- Module intent: NLP Module - Text correction and enhancement for OCR content
- L5-L5: import section wires external dependencies and local modules.
- L7-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/nlp/text_corrector.py` (531 lines)
- Module intent: NLP Text Corrector - SpaCy-based text correction for OCR and extracted content
- L6-L12: import section wires external dependencies and local modules.
- L14-L509: module constants/config defaults are declared.
- Walkthrough:
  - L17-L505: class `TextCorrector` defines state + behavior (12 methods).
  - L29-L47: method `__init__` executes its unit of logic (key calls: _build_financial_phrases, _build_financial_vocab, _build_ocr_char_fixes, _load_model, info).
  - L49-L86: method `_load_model` executes its unit of logic (key calls: debug, info, load, warning).
  - L88-L107: method `_build_financial_vocab` executes its unit of logic (key calls: none).
  - L109-L182: method `_build_financial_phrases` executes its unit of logic (key calls: none).
  - L184-L209: method `_build_ocr_char_fixes` executes its unit of logic (key calls: none).
  - L211-L259: method `correct` executes its unit of logic (key calls: _apply_dictionary, _apply_spacy_corrections, _fix_amounts, _fix_character_errors, _fix_common_patterns, _fix_dates_years).
  - L261-L308: method `_fix_dates_years` executes its unit of logic (key calls: findall, len, sub).
  - L310-L336: method `_fix_amounts` executes its unit of logic (key calls: findall, len, sub).
  - L338-L361: method `_fix_character_errors` executes its unit of logic (key calls: count, findall, items, len, replace, sub).
  - L363-L379: method `_apply_dictionary` executes its unit of logic (key calls: compile, escape, findall, items, len, lower).
  - L381-L447: method `_fix_common_patterns` executes its unit of logic (key calls: count, items, replace).
  - L449-L505: method `_apply_spacy_corrections` executes its unit of logic (key calls: items, len, lower, nlp, replace, sub).
  - L512-L531: function `get_text_corrector` contains callable workflow logic (key calls: TextCorrector, get_config, getattr).

### `src/ocr/__init__.py` (7 lines)
- Module intent: OCR stage - Tesseract integration for scanned documents
- L3-L5: import section wires external dependencies and local modules.
- L7-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/ocr/image_preprocessor.py` (198 lines)
- Module intent: Image Preprocessor - OpenCV-based image preprocessing for better OCR
- L5-L12: import section wires external dependencies and local modules.
- L14-L14: module constants/config defaults are declared.
- Walkthrough:
  - L17-L198: class `ImagePreprocessor` defines state + behavior (5 methods).
  - L20-L26: method `__init__` executes its unit of logic (key calls: get, get_config).
  - L28-L55: method `preprocess` executes its unit of logic (key calls: _preprocess_opencv, _preprocess_pillow, error, len, warning).
  - L57-L125: method `_preprocess_opencv` executes its unit of logic (key calls: _correct_skew, apply, createCLAHE, cvtColor, error, fastNlMeansDenoising).
  - L127-L174: method `_correct_skew` executes its unit of logic (key calls: Canny, HoughLines, abs, append, cvtColor, degrees).
  - L176-L198: method `_preprocess_pillow` executes its unit of logic (key calls: BytesIO, Contrast, convert, enhance, error, get).

### `src/ocr/image_preprocessor_advanced.py` (1041 lines)
- Module intent: Image Preprocessor - Advanced OpenCV-based preprocessing for better OCR
- L6-L16: import section wires external dependencies and local modules.
- L18-L18: module constants/config defaults are declared.
- Walkthrough:
  - L21-L26: class `EnhancementLevel` defines state + behavior (0 methods).
  - L30-L44: class `PreprocessingConfig` defines state + behavior (0 methods).
  - L47-L1041: class `ImagePreprocessor` defines state + behavior (32 methods).
  - L63-L81: method `__init__` executes its unit of logic (key calls: _check_opencv_contrib, get, get_config, info, warning).
  - L83-L90: method `_check_opencv_contrib` executes its unit of logic (key calls: createFastBilateralSolverFilter, zeros).
  - L92-L119: method `preprocess` executes its unit of logic (key calls: _preprocess_opencv_advanced, _preprocess_pillow, error, len, warning).
  - L121-L137: method `resize_image` executes its unit of logic (key calls: frombuffer, imdecode, imencode, int, resize, tobytes).
  - L139-L159: method `rotate_image` executes its unit of logic (key calls: frombuffer, imdecode, imencode, rotate, tobytes, warning).
  - L161-L186: method `apply_binarization` executes its unit of logic (key calls: adaptiveThreshold, cvtColor, frombuffer, imdecode, imencode, len).
  - L188-L201: method `apply_clahe_only` executes its unit of logic (key calls: _apply_clahe, frombuffer, imdecode, imencode, tobytes, warning).
  - L203-L319: method `_preprocess_opencv_advanced` executes its unit of logic (key calls: _adjust_config_dynamic, _analyze_image, _apply_brightness, _apply_clahe, _apply_denoise, _apply_gamma).
  - L321-L336: method `_analyze_image` executes its unit of logic (key calls: Laplacian, cvtColor, float, len, mean, std).
  - L338-L373: method `_select_mode` executes its unit of logic (key calls: none).
  - L375-L426: method `_get_config_for_mode` executes its unit of logic (key calls: PreprocessingConfig, _get_config_for_mode, upper, warning).
  - L428-L465: method `_adjust_config_dynamic` executes its unit of logic (key calls: max, min).
  - L467-L473: method `_select_gamma` executes its unit of logic (key calls: none).
  - L475-L481: method `_apply_denoise` executes its unit of logic (key calls: bilateralFilter, warning).
  - L483-L492: method `_apply_brightness` executes its unit of logic (key calls: astype, clip, cvtColor, warning).
  - L494-L509: method `_apply_clahe` executes its unit of logic (key calls: apply, createCLAHE, cvtColor, len, merge, split).
  - L511-L519: method `_apply_sharpen` executes its unit of logic (key calls: GaussianBlur, addWeighted, astype, clip, warning).
  - L521-L530: method `_apply_gamma` executes its unit of logic (key calls: LUT, arange, astype, max, warning).
  - L532-L558: method `_detect_faded_regions` executes its unit of logic (key calls: Laplacian, calcHist, cvtColor, debug, flatten, len).
  - L560-L582: method `_detect_colored_regions` executes its unit of logic (key calls: cvtColor, debug, len, sum, warning).
  - L584-L650: method `_remove_color_background` executes its unit of logic (key calls: apply, array, bitwise_or, copy, count_nonzero, createCLAHE).
  - L652-L684: method `remove_color_background_aggressive` executes its unit of logic (key calls: apply, bitwise_not, count_nonzero, createCLAHE, cvtColor, frombuffer).
  - L686-L716: method `invert_and_enhance` executes its unit of logic (key calls: apply, bitwise_not, createCLAHE, cvtColor, fastNlMeansDenoising, frombuffer).
  - L718-L753: method `_enhance_faded_text` executes its unit of logic (key calls: adaptiveThreshold, apply, bilateralFilter, copy, createCLAHE, cvtColor).
  - L755-L792: method `_correct_skew` executes its unit of logic (key calls: Canny, HoughLines, abs, append, cvtColor, degrees).
  - L794-L813: method `_preprocess_pillow` executes its unit of logic (key calls: BytesIO, Contrast, convert, enhance, error, get).
  - L815-L858: method `_correct_orientation` executes its unit of logic (key calls: cvtColor, image_to_osd, info, int, len, rotate).
  - L860-L879: method `_handle_inverted_text` executes its unit of logic (key calls: bitwise_not, cvtColor, debug, len, mean, warning).
  - L881-L952: method `_correct_perspective` executes its unit of logic (key calls: Canny, GaussianBlur, approxPolyDP, arcLength, argmax, argmin).
  - L954-L978: method `_remove_shadows` executes its unit of logic (key calls: absdiff, append, dilate, len, medianBlur, merge).
  - L980-L1010: method `_remove_borders` executes its unit of logic (key calls: boundingRect, copy, cvtColor, findContours, len, max).
  - L1012-L1041: method `_repair_broken_text` executes its unit of logic (key calls: cvtColor, debug, dilate, erode, len, mean).

### `src/ocr/ocr_worker.py` (816 lines)
- Module intent: OCR Worker - Processes images/scanned documents with Tesseract
- L6-L27: import section wires external dependencies and local modules.
- L43-L43: module constants/config defaults are declared.
- Walkthrough:
  - L46-L816: class `OCRWorker` defines state + behavior (16 methods).
  - L49-L126: method `__init__` executes its unit of logic (key calls: DocumentBuilder, ImagePreprocessor, OpenSearchClient, TesseractWrapper, _check_poppler_tools, get).
  - L128-L142: method `_check_poppler_tools` executes its unit of logic (key calls: all, info, warning, which).
  - L144-L233: method `run` executes its unit of logic (key calls: Process, Thread, _flush_updates, _log_final_stats, _log_progress, _process_file).
  - L235-L341: method `_process_file` executes its unit of logic (key calls: Path, _get_file_hash, _handle_failure, _process_image_file, _process_pdf_file, complete_ocr).
  - L343-L462: method `_process_image_file` executes its unit of logic (key calls: NamedTemporaryFile, Path, _run_ocr_attempt, _validate_ocr_result, apply_binarization, apply_clahe_only).
  - L464-L501: method `_validate_ocr_result` executes its unit of logic (key calls: len, replace, strip, sub).
  - L503-L519: method `_run_ocr_attempt` executes its unit of logic (key calls: NamedTemporaryFile, exists, extract_text, preprocess, unlink, write).
  - L521-L652: method `_process_pdf_file` executes its unit of logic (key calls: NamedTemporaryFile, Path, append, close, convert_from_path, enumerate).
  - L654-L661: method `_get_file_hash` executes its unit of logic (key calls: get, get_file_info, warning).
  - L663-L699: method `_flush_updates` executes its unit of logic (key calls: debug, error, get, info, len, str).
  - L701-L723: method `_handle_failure` executes its unit of logic (key calls: complete_ocr, debug, mark_file_failed).
  - L725-L760: method `_log_progress` executes its unit of logic (key calls: get, get_queue_stats, info, time, warning).
  - L762-L785: method `_log_final_stats` executes its unit of logic (key calls: get_stats, info, time).
  - L787-L791: method `stop` executes its unit of logic (key calls: info).
  - L793-L800: method `_heartbeat_loop` executes its unit of logic (key calls: sleep, update_worker_heartbeat).
  - L802-L816: method `get_stats` executes its unit of logic (key calls: time).

### `src/ocr/tesseract_wrapper.py` (286 lines)
- Module intent: Tesseract Wrapper - Integration with Tesseract OCR engine
- L5-L13: import section wires external dependencies and local modules.
- L22-L22: module constants/config defaults are declared.
- Walkthrough:
  - L25-L286: class `TesseractWrapper` defines state + behavior (10 methods).
  - L28-L49: method `__init__` executes its unit of logic (key calls: _get_engine_mode, _get_psm_mode, _verify_tesseract, get_config, info, join).
  - L51-L74: method `_verify_tesseract` executes its unit of logic (key calls: FileNotFoundError, Path, error, exists, info, run).
  - L76-L87: method `_get_engine_mode` executes its unit of logic (key calls: get, upper).
  - L89-L108: method `_get_psm_mode` executes its unit of logic (key calls: get, upper).
  - L110-L204: method `extract_text` executes its unit of logic (key calls: NamedTemporaryFile, _calculate_confidence, _read_error_snippet, error, exists, lower).
  - L206-L214: method `_read_error_snippet` executes its unit of logic (key calls: exists, open, read).
  - L216-L245: method `_calculate_confidence` executes its unit of logic (key calls: append, exists, float, len, open, readlines).
  - L247-L258: method `health_check` executes its unit of logic (key calls: run).
  - L260-L275: method `get_version` executes its unit of logic (key calls: run, split, strip).
  - L277-L286: method `get_stats` executes its unit of logic (key calls: none).

### `src/orchestrator/__init__.py` (8 lines)
- Module intent: Orchestration - Master coordinator and monitoring
- L3-L6: import section wires external dependencies and local modules.
- L8-L8: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/orchestrator/checkpoint_manager.py` (93 lines)
- Module intent: Checkpoint Manager - State persistence for resume capability
- L5-L13: import section wires external dependencies and local modules.
- L15-L15: module constants/config defaults are declared.
- Walkthrough:
  - L18-L93: class `CheckpointManager` defines state + behavior (4 methods).
  - L21-L28: method `__init__` executes its unit of logic (key calls: Path, get_config, get_queue_manager, mkdir).
  - L30-L57: method `create_checkpoint` executes its unit of logic (key calls: _cleanup_old_checkpoints, dump, error, get_queue_stats, info, isoformat).
  - L59-L78: method `load_checkpoint` executes its unit of logic (key calls: error, glob, info, load, open, sorted).
  - L80-L93: method `_cleanup_old_checkpoints` executes its unit of logic (key calls: debug, glob, len, sorted, unlink, warning).

### `src/orchestrator/health_monitor.py` (66 lines)
- Module intent: Health Monitor - Service health checking
- L5-L9: import section wires external dependencies and local modules.
- L11-L11: module constants/config defaults are declared.
- Walkthrough:
  - L14-L66: class `HealthMonitor` defines state + behavior (5 methods).
  - L17-L18: method `__init__` executes its unit of logic (key calls: get_config).
  - L20-L26: method `check_all_services` executes its unit of logic (key calls: check_opensearch, check_tesseract, check_tika).
  - L28-L41: method `check_tika` executes its unit of logic (key calls: get).
  - L43-L55: method `check_opensearch` executes its unit of logic (key calls: get, json).
  - L57-L66: method `check_tesseract` executes its unit of logic (key calls: run).

### `src/orchestrator/master_orchestrator.py` (504 lines)
- Module intent: Master Orchestrator - Main coordinator for all workers
- L5-L25: import section wires external dependencies and local modules.
- L27-L27: module constants/config defaults are declared.
- Walkthrough:
  - L30-L504: class `MasterOrchestrator` defines state + behavior (17 methods).
  - L33-L49: method `__init__` executes its unit of logic (key calls: CheckpointManager, HealthMonitor, ResourceMonitor, get_config, get_queue_manager, signal).
  - L51-L108: method `start` executes its unit of logic (key calls: RecoveryManager, _clear_bloom_filter_files, _main_loop, _spawn_discovery_workers, _spawn_extraction_workers, _spawn_indexing_workers).
  - L110-L123: method `_clear_bloom_filter_files` executes its unit of logic (key calls: Path, exists, glob, info, len, str).
  - L125-L147: method `_spawn_discovery_workers` executes its unit of logic (key calls: Process, info, is_discovery_complete, range, start).
  - L149-L207: method `_spawn_extraction_workers` executes its unit of logic (key calls: Process, info, range, start).
  - L209-L226: method `_spawn_indexing_workers` executes its unit of logic (key calls: Process, info, range, start).
  - L228-L245: method `_spawn_ocr_workers` executes its unit of logic (key calls: Process, info, range, start).
  - L248-L258: method `_run_discovery_worker` executes its unit of logic (key calls: DiscoveryWorker, Path, insert, run, str).
  - L261-L271: method `_run_extraction_worker` executes its unit of logic (key calls: ExtractionWorker, Path, insert, run, str).
  - L274-L284: method `_run_indexing_worker` executes its unit of logic (key calls: IndexingWorker, Path, insert, run, str).
  - L287-L297: method `_run_ocr_worker` executes its unit of logic (key calls: OCRWorker, Path, insert, run, str).
  - L299-L354: method `_main_loop` executes its unit of logic (key calls: _check_workers, _is_work_complete, any, check_resources, create_checkpoint, error).
  - L356-L367: method `_check_workers` executes its unit of logic (key calls: _respawn_worker, is_alive, items, list, warning).
  - L369-L449: method `_respawn_worker` executes its unit of logic (key calls: Process, error, info, int, split, start).
  - L451-L462: method `_is_work_complete` executes its unit of logic (key calls: get).
  - L464-L499: method `stop` executes its unit of logic (key calls: create_checkpoint, info, is_alive, items, kill, sleep).
  - L501-L504: method `_signal_handler` executes its unit of logic (key calls: info).

### `src/orchestrator/recovery_manager.py` (231 lines)
- Module intent: Recovery Manager - Handles rescuing of 'zombie' tasks that are lost from queues
- L5-L13: import section wires external dependencies and local modules.
- L15-L15: module constants/config defaults are declared.
- Walkthrough:
  - L17-L231: class `RecoveryManager` defines state + behavior (6 methods).
  - L24-L28: method `__init__` executes its unit of logic (key calls: Lock, get_config, get_queue_manager).
  - L30-L80: method `recover_all` executes its unit of logic (key calls: _check_and_recover_file, error, info, scan, split, time).
  - L82-L107: method `_check_and_recover_file` executes its unit of logic (key calls: _is_in_any_queue, _is_in_processing_set, _requeue_file, debug, get, hgetall).
  - L109-L159: method `_is_in_any_queue` executes its unit of logic (key calls: get, loads, str, zrank, zscan).
  - L161-L183: method `_is_in_processing_set` executes its unit of logic (key calls: _get_extraction_processing_keys, _get_indexing_processing_keys, _get_ocr_processing_keys, hexists).
  - L185-L231: method `_requeue_file` executes its unit of logic (key calls: Priority, SizeCategory, add_to_extraction_queue, error, get, info).

### `src/orchestrator/resource_monitor.py` (65 lines)
- Module intent: Resource Monitor - System resource monitoring
- L5-L9: import section wires external dependencies and local modules.
- L11-L11: module constants/config defaults are declared.
- Walkthrough:
  - L14-L65: class `ResourceMonitor` defines state + behavior (2 methods).
  - L17-L19: method `__init__` executes its unit of logic (key calls: get_config).
  - L21-L65: method `check_resources` executes its unit of logic (key calls: cpu_percent, disk_usage, virtual_memory, warning).

### `src/orchestrator.py` (915 lines)
- Module intent: Enterprise Document Search System - Master Orchestrator
- L7-L24: import section wires external dependencies and local modules.
- L26-L26: module constants/config defaults are declared.
- Walkthrough:
  - L29-L904: class `MasterOrchestrator` defines state + behavior (29 methods).
  - L32-L77: method `__init__` executes its unit of logic (key calls: get_config, get_queue_manager, getattr, info, signal).
  - L79-L139: method `start` executes its unit of logic (key calls: _count_total_pending, _initialize_databases, _load_checkpoint, _monitoring_loop, _restore_from_checkpoint, _shutdown).
  - L141-L197: method `_verify_services` executes its unit of logic (key calls: error, get, info, json, run, split).
  - L199-L208: method `_initialize_databases` executes its unit of logic (key calls: error, get_queue_statistics, info).
  - L210-L217: method `_next_tika_port` executes its unit of logic (key calls: get, getattr, len).
  - L219-L231: method `_make_extraction_assignment` executes its unit of logic (key calls: SizeCategory, isinstance, warning).
  - L233-L248: method `_start_extraction_worker_process` executes its unit of logic (key calls: Process, start).
  - L250-L281: method `_choose_extraction_assignment` executes its unit of logic (key calls: _make_extraction_assignment, _next_tika_port, error, get, get_queue_statistics, isinstance).
  - L283-L304: method `_start_all_workers` executes its unit of logic (key calls: _start_discovery_workers, _start_extraction_workers, _start_indexing_workers, _start_ocr_workers, info, len).
  - L306-L320: method `_start_discovery_workers` executes its unit of logic (key calls: Process, info, range, sleep, start).
  - L322-L341: method `_start_extraction_workers` executes its unit of logic (key calls: _make_extraction_assignment, _start_extraction_worker_process, info, len, range, sleep).
  - L343-L357: method `_start_indexing_workers` executes its unit of logic (key calls: Process, info, range, sleep, start).
  - L359-L375: method `_start_ocr_workers` executes its unit of logic (key calls: Process, info, range, sleep, start).
  - L378-L382: method `_run_discovery_worker` executes its unit of logic (key calls: DiscoveryWorker, run).
  - L385-L389: method `_run_extraction_worker` executes its unit of logic (key calls: ExtractionWorker, run).
  - L392-L396: method `_run_indexing_worker` executes its unit of logic (key calls: IndexingWorker, run).
  - L399-L403: method `_run_ocr_worker` executes its unit of logic (key calls: OCRWorker, run).
  - L405-L438: method `_monitoring_loop` executes its unit of logic (key calls: _check_system_resources, _check_worker_health, _log_statistics, _save_checkpoint, error, info).
  - L440-L632: method `_check_worker_health` executes its unit of logic (key calls: Process, _choose_extraction_assignment, _start_extraction_worker_process, append, children, debug).
  - L634-L666: method `_check_system_resources` executes its unit of logic (key calls: _throttle_for_memory, cpu_percent, disk_usage, virtual_memory, warning).
  - L668-L727: method `_throttle_for_memory` executes its unit of logic (key calls: collect, info, is_alive, items, join, kill).
  - L729-L752: method `_log_statistics` executes its unit of logic (key calls: error, get, get_queue_statistics, info, time).
  - L754-L785: method `_save_checkpoint` executes its unit of logic (key calls: Path, dump, error, get_queue_statistics, glob, info).
  - L787-L804: method `_load_checkpoint` executes its unit of logic (key calls: Path, error, exists, glob, load, open).
  - L806-L819: method `_prompt_resume` executes its unit of logic (key calls: get, input, lower, print, strip).
  - L820-L857: method `_restore_from_checkpoint` executes its unit of logic (key calls: error, get, info, isinstance, reset_stale_processing, values).
  - L859-L861: method `_restore_from_checkpoint` executes its unit of logic (key calls: info).
  - L867-L870: method `_signal_handler` executes its unit of logic (key calls: info).
  - L872-L904: method `_shutdown` executes its unit of logic (key calls: _save_checkpoint, info, is_alive, items, join, kill).
  - L907-L911: function `main` contains callable workflow logic (key calls: MasterOrchestrator, exit, start).

### `src/tools/clear_redis.py` (33 lines)
- L2-L3: import section wires external dependencies and local modules.
- Walkthrough:
  - L5-L30: function `clear_redis` contains callable workflow logic (key calls: Redis, exit, flushdb, ping, print).

### `src/tools/fix_stats.py` (153 lines)
- L2-L17: import section wires external dependencies and local modules.
- L11-L12: module constants/config defaults are declared.
- Walkthrough:
  - L19-L150: function `fix_statistics` contains callable workflow logic (key calls: add, delete, error, execute, get, get_redis_queue_manager).

### `src/tools/verify_metrics.py` (25 lines)
- L2-L4: import section wires external dependencies and local modules.
- Walkthrough:
  - L6-L22: function `verify` contains callable workflow logic (key calls: Redis, get, print, range, sleep, strftime).

### `src/ui/dashboard.py` (2095 lines)
- Module intent: Streamlit-based monitoring dashboard for the Enterprise Document Search System.
- L9-L51: import section wires external dependencies and local modules.
- L34-L285: module constants/config defaults are declared.
- Walkthrough:
  - L78-L83: function `_save_last_known_good` contains callable workflow logic (key calls: isinstance, len).
  - L86-L89: function `_get_last_known_good` contains callable workflow logic (key calls: get).
  - L92-L162: function `_background_stats_fetcher` contains callable workflow logic (key calls: _save_last_known_good, get_queue_manager, get_queue_statistics, get_size_statistics, is_set, isinstance).
  - L165-L172: function `_ensure_bg_fetcher` contains callable workflow logic (key calls: Thread, start).
  - L175-L186: function `with_timeout` contains callable workflow logic (key calls: result, submit, wraps).
  - L189-L206: function `invalidate_all_caches` contains callable workflow logic (key calls: clear).
  - L209-L239: function `_clear_all_caches_fully` contains callable workflow logic (key calls: clear).
  - L242-L280: function `_force_refresh_from_redis` contains callable workflow logic (key calls: _is_real_data, get_queue_manager, get_queue_statistics, get_size_statistics, result, submit).
  - L287-L292: function `_ensure_session_defaults` contains callable workflow logic (key calls: none).
  - L295-L297: function `_is_real_data` contains callable workflow logic (key calls: bool, isinstance, len).
  - L300-L348: function `get_cached_queue_stats` contains callable workflow logic (key calls: _ensure_bg_fetcher, _ensure_session_defaults, _get_last_known_good, _is_real_data, _save_last_known_good, _try_direct_queue_fetch).
  - L351-L371: function `_try_direct_queue_fetch` contains callable workflow logic (key calls: _is_real_data, _save_last_known_good, get_queue_manager, get_queue_statistics, result, submit).
  - L374-L422: function `get_cached_size_stats` contains callable workflow logic (key calls: _ensure_bg_fetcher, _ensure_session_defaults, _get_last_known_good, _is_real_data, _save_last_known_good, _try_direct_size_fetch).
  - L425-L444: function `_try_direct_size_fetch` contains callable workflow logic (key calls: _is_real_data, _save_last_known_good, get_queue_manager, get_size_statistics, result, submit).
  - L448-L454: function `get_cached_failed_files` contains callable workflow logic (key calls: cache_data, get_failed_files, get_queue_manager).
  - L458-L464: function `get_cached_ocr_pending` contains callable workflow logic (key calls: cache_data, get_ocr_pending_files, get_queue_manager).
  - L468-L474: function `get_cached_largest_files` contains callable workflow logic (key calls: cache_data, get_largest_completed_files, get_queue_manager).
  - L477-L485: function `open_file_with_default_app` contains callable workflow logic (key calls: Exception, run, startfile).
  - L488-L494: function `format_number` contains callable workflow logic (key calls: isinstance, str).
  - L497-L518: function `format_size` contains callable workflow logic (key calls: none).
  - L521-L525: function `calculate_progress_percentage` contains callable workflow logic (key calls: min).
  - L528-L546: function `seconds_to_human` contains callable workflow logic (key calls: append, divmod, floor, int, join, max).
  - L549-L635: function `extract_summary` contains callable workflow logic (key calls: get, int, safe_int).
  - L638-L662: function `render_pipeline_stage` contains callable workflow logic (key calls: calculate_progress_percentage, caption, columns, container, format_number, get).
  - L665-L677: function `render_failure_chart` contains callable workflow logic (key calls: DataFrame, bar_chart, get, items, set_index, sorted).
  - L680-L698: function `render_extraction_detail` contains callable workflow logic (key calls: DataFrame, append, dataframe, get, info, items).
  - L701-L788: function `render_dashboard` contains callable workflow logic (key calls: OpenSearchClient, error, get_config, get_queue_manager, markdown, radio).
  - L791-L983: function `render_sidebar` contains callable workflow logic (key calls: caption, extract_summary, format_size, get, get_cached_queue_stats, get_cached_size_stats).
  - L986-L1025: function `render_search_tab` contains callable workflow logic (key calls: button, caption, columns, error, info, len).
  - L1028-L1068: function `extract_snippet_manually` contains callable workflow logic (key calls: compile, escape, find, group, len, lower).
  - L1071-L1126: function `_generate_ocr_variants` contains callable workflow logic (key calls: add, len, list, lower, replace, set).
  - L1129-L1448: function `perform_search` contains callable workflow logic (key calls: Exception, _generate_ocr_variants, any, append, bool, endswith).
  - L1451-L1540: function `render_search_results` contains callable workflow logic (key calls: button, columns, container, enumerate, error, get).
  - L1543-L1627: function `render_recent_documents` contains callable workflow logic (key calls: append, button, caption, columns, container, enumerate).
  - L1630-L2084: function `render_monitoring_tab` contains callable workflow logic (key calls: DataFrame, Path, _clear_all_caches_fully, _force_refresh_from_redis, append, button).
  - L2090-L2091: function `main` contains callable workflow logic (key calls: render_dashboard).

### `src/utils/__init__.py` (12 lines)
- Module intent: Enterprise Document Search System - Utilities Module
- L8-L8: import section wires external dependencies and local modules.
- L6-L12: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `src/utils/bloom_filter.py` (462 lines)
- Module intent: Enterprise Document Search System - Bloom Filter
- L7-L14: import section wires external dependencies and local modules.
- L17-L17: module constants/config defaults are declared.
- Walkthrough:
  - L20-L377: class `BloomFilter` defines state + behavior (15 methods).
  - L32-L67: method `__init__` executes its unit of logic (key calls: RLock, _calculate_hash_count, _calculate_size, bitarray, info, setall).
  - L70-L88: method `_calculate_size` executes its unit of logic (key calls: int, log).
  - L91-L109: method `_calculate_hash_count` executes its unit of logic (key calls: int, log).
  - L111-L133: method `_get_hash_positions` executes its unit of logic (key calls: append, hash, range).
  - L135-L148: method `add` executes its unit of logic (key calls: _get_hash_positions).
  - L150-L164: method `add_batch` executes its unit of logic (key calls: _get_hash_positions).
  - L166-L181: method `contains` executes its unit of logic (key calls: _get_hash_positions, all).
  - L183-L185: method `__contains__` executes its unit of logic (key calls: contains).
  - L187-L190: method `__len__` executes its unit of logic (key calls: none).
  - L192-L218: method `current_fpr` executes its unit of logic (key calls: exp).
  - L220-L232: method `capacity_remaining` executes its unit of logic (key calls: none).
  - L234-L254: method `get_statistics` executes its unit of logic (key calls: capacity_remaining, count, current_fpr).
  - L256-L278: method `save_to_file` executes its unit of logic (key calls: dump, info, open).
  - L281-L311: method `load_from_file` executes its unit of logic (key calls: cls, info, load, open).
  - L313-L377: method `populate_from_database` executes its unit of logic (key calls: _get_connection, add_batch, append, cursor, execute, hasattr).
  - L380-L462: function `create_bloom_filter_from_database` contains callable workflow logic (key calls: BloomFilter, _get_connection, add_batch, append, cursor, execute).

## Operational Scripts (scripts/)

### `scripts/analyze_backlog.py` (117 lines)
- Module intent: Analyze backlog and estimate ETAs per pipeline stage.
- L5-L8: import section wires external dependencies and local modules.
- L10-L16: module constants/config defaults are declared.
- Walkthrough:
  - L18-L27: function `read_config` contains callable workflow logic (key calls: get, int, isinstance, read_text, safe_load).
  - L30-L41: function `seconds_to_human` contains callable workflow logic (key calls: append, divmod, int, join).
  - L44-L114: function `analyze` contains callable workflow logic (key calls: close, connect, cursor, execute, exists, fetchone).

### `scripts/check_stats.py` (42 lines)
- L1-L8: import section wires external dependencies and local modules.
- L10-L37: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `scripts/inspect_completed.py` (41 lines)
- L1-L2: import section wires external dependencies and local modules.
- L4-L18: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `scripts/migrate_counters.py` (118 lines)
- Module intent: Migration Script - Populate counters from existing data
- L13-L21: import section wires external dependencies and local modules.
- L17-L17: module constants/config defaults are declared.
- Walkthrough:
  - L24-L114: function `migrate_counters` contains callable workflow logic (key calls: execute, get, get_queue_manager, hget, hlen, input).

### `scripts/reindex_with_enhanced_analyzers.py` (140 lines)
- Module intent: Reindex with Enhanced Analyzers - Recreates the OpenSearch index with improved search analyzers.
- L18-L28: import section wires external dependencies and local modules.
- L23-L30: module constants/config defaults are declared.
- Walkthrough:
  - L33-L136: function `main` contains callable workflow logic (key calls: ArgumentParser, OpenSearchClient, add_argument, count, delete, ensure_index).

### `scripts/reset_state.py` (160 lines)
- Module intent: Reset State Script - Clear all pipeline data for clean re-indexing
- L6-L16: import section wires external dependencies and local modules.
- L18-L18: module constants/config defaults are declared.
- Walkthrough:
  - L21-L24: function `confirm_action` contains callable workflow logic (key calls: input, lower, strip).
  - L27-L40: function `delete_directory` contains callable workflow logic (key calls: error, exists, info, mkdir, rmtree).
  - L43-L56: function `delete_queue_db` contains callable workflow logic (key calls: Path, error, exists, info, unlink).
  - L59-L79: function `delete_opensearch_index` contains callable workflow logic (key calls: delete, error, info, warning).
  - L82-L156: function `main` contains callable workflow logic (key calls: ArgumentParser, Path, add_argument, confirm_action, delete_directory, delete_opensearch_index).

### `scripts/test_all_fixes.py` (651 lines)
- Module intent: Comprehensive Test Script for DocumentSearch System Fixes
- L10-L16: import section wires external dependencies and local modules.
- L19-L25: module constants/config defaults are declared.
- Walkthrough:
  - L28-L47: function `log_test` contains callable workflow logic (key calls: append, print).
  - L50-L54: function `print_header` contains callable workflow logic (key calls: print).
  - L60-L105: function `test_queue_backend_selection` contains callable workflow logic (key calls: callable, get_queue_manager, getattr, hasattr, is_using_redis, isinstance).
  - L111-L162: function `test_sqlite_transaction_handling` contains callable workflow logic (key calls: NamedTemporaryFile, Path, QueueManager, _get_connection, close, cursor).
  - L168-L211: function `test_worker_respawn_logic` contains callable workflow logic (key calls: getsource, hasattr, log_test, print_header, str).
  - L217-L244: function `test_extraction_status_updates` contains callable workflow logic (key calls: getsource, log_test, print_header, str).
  - L250-L280: function `test_batch_accumulation_timeout` contains callable workflow logic (key calls: getsource, log_test, lower, print_header, str).
  - L286-L321: function `test_ocr_opensearch_update` contains callable workflow logic (key calls: getsource, hasattr, log_test, print_header, str).
  - L327-L366: function `test_redis_sqlite_sync` contains callable workflow logic (key calls: getsource, keys, list, log_test, lower, print_header).
  - L372-L398: function `test_import_all_modules` contains callable workflow logic (key calls: __import__, log_test, print_header, str).
  - L404-L434: function `test_queue_operations` contains callable workflow logic (key calls: get_extraction_queue_size, get_queue_manager, get_queue_stats, isinstance, log_test, print_header).
  - L440-L500: function `test_bloom_filter_thread_safety` contains callable workflow logic (key calls: BloomFilter, Thread, add, append, getsource, join).
  - L506-L532: function `test_circuit_breaker_health_check` contains callable workflow logic (key calls: getsource, log_test, lower, print_header, str).
  - L538-L564: function `test_dashboard_cache_invalidation` contains callable workflow logic (key calls: getsource, log_test, print_header, replace, str).
  - L570-L596: function `test_ocr_confidence_threshold` contains callable workflow logic (key calls: getsource, log_test, lower, print_header, str).
  - L602-L647: function `main` contains callable workflow logic (key calls: print, test_batch_accumulation_timeout, test_bloom_filter_thread_safety, test_circuit_breaker_health_check, test_dashboard_cache_invalidation, test_extraction_status_updates).

### `scripts/test_fixes.py` (311 lines)
- Module intent: Test Script - Validates fixes for stats accuracy, checkpoint resume, NLP, and dashboard metrics
- L15-L26: import section wires external dependencies and local modules.
- L21-L21: module constants/config defaults are declared.
- Walkthrough:
  - L29-L33: function `print_header` contains callable workflow logic (key calls: print).
  - L36-L42: function `print_result` contains callable workflow logic (key calls: print, split).
  - L45-L125: function `test_stats_accuracy` contains callable workflow logic (key calls: get, get_queue_manager, get_queue_statistics, get_size_statistics, int, print).
  - L128-L165: function `test_checkpoint_resume` contains callable workflow logic (key calls: Path, exists, get_config, get_queue_manager, glob, hlen).
  - L168-L219: function `test_nlp_layer` contains callable workflow logic (key calls: correct, get_config, get_text_corrector, print, print_header, print_result).
  - L222-L273: function `test_dashboard_metrics` contains callable workflow logic (key calls: all, dumps, get, get_queue_manager, get_queue_statistics, get_size_statistics).
  - L276-L307: function `run_all_tests` contains callable workflow logic (key calls: items, len, now, print, print_header, strftime).

### `scripts/test_search.py` (222 lines)
- Module intent: Search System Test Script
- L7-L14: import section wires external dependencies and local modules.
- L11-L11: module constants/config defaults are declared.
- Walkthrough:
  - L17-L218: function `test_search` contains callable workflow logic (key calls: OpenSearchClient, enumerate, len, print, search).

### `scripts/test_system.py` (180 lines)
- Module intent: Comprehensive System Test Script
- L7-L15: import section wires external dependencies and local modules.
- L11-L11: module constants/config defaults are declared.
- Walkthrough:
  - L18-L176: function `run_tests` contains callable workflow logic (key calls: OpenSearchClient, count, exists, get, get_queue_manager, get_queue_statistics).

## Test Suite (tests/)

### `tests/test_full_pipeline.py` (811 lines)
- Module intent: Full Pipeline Integration Tests
- L6-L19: import section wires external dependencies and local modules.
- L43-L43: module constants/config defaults are declared.
- Walkthrough:
  - L22-L40: class `TestResults` defines state + behavior (3 methods).
  - L24-L26: method `__init__` executes its unit of logic (key calls: time).
  - L28-L34: method `add` executes its unit of logic (key calls: isoformat, now).
  - L36-L40: method `summary` executes its unit of logic (key calls: len, sum, time, values).
  - L49-L118: function `test_queue_system` contains callable workflow logic (key calls: add, add_discovered_file, commit, execute, get_queue_manager, get_queue_stats).
  - L124-L179: function `test_preprocessing` contains callable workflow logic (key calls: ImagePreprocessor, add, create_test_image, len, preprocess, print).
  - L182-L219: function `create_test_image` contains callable workflow logic (key calls: astype, clip, imencode, normal, ones, putText).
  - L225-L291: function `test_nlp_correction` contains callable workflow logic (key calls: TextCorrector, add, append, correct, len, lower).
  - L297-L347: function `test_extraction` contains callable workflow logic (key calls: add, get_config, len, print, print_exc, put).
  - L353-L445: function `test_indexing` contains callable workflow logic (key calls: OpenSearch, add, count, delete, exists, get).
  - L451-L571: function `test_search_accuracy` contains callable workflow logic (key calls: OpenSearch, QueryBuilder, add, append, build_search_query, count).
  - L577-L682: function `test_faded_document_ocr` contains callable workflow logic (key calls: ImagePreprocessor, NamedTemporaryFile, TesseractWrapper, TextCorrector, add, any).
  - L685-L703: function `create_extremely_faded_image` contains callable workflow logic (key calls: imencode, ones, putText, tobytes).
  - L706-L722: function `create_very_low_contrast_image` contains callable workflow logic (key calls: imencode, ones, putText, tobytes).
  - L725-L745: function `create_noisy_faded_image` contains callable workflow logic (key calls: astype, clip, imencode, normal, ones, putText).
  - L748-L764: function `create_washed_out_image` contains callable workflow logic (key calls: imencode, ones, putText, tobytes).
  - L770-L807: function `main` contains callable workflow logic (key calls: items, now, print, strftime, summary, test_extraction).

### `tests/test_search_accuracy.py` (504 lines)
- Module intent: Search Accuracy Test Suite for Enterprise Document Search System
- L14-L28: import section wires external dependencies and local modules.
- L24-L24: module constants/config defaults are declared.
- Walkthrough:
  - L32-L38: class `SearchResult` defines state + behavior (0 methods).
  - L42-L49: class `TestCase` defines state + behavior (0 methods).
  - L52-L472: class `SearchAccuracyTester` defines state + behavior (9 methods).
  - L55-L59: method `__init__` executes its unit of logic (key calls: initialize_client).
  - L61-L75: method `initialize_client` executes its unit of logic (key calls: OpenSearchClient, count, exit, print).
  - L77-L180: method `execute_search` executes its unit of logic (key calls: SearchResult, append, bool, get, search, str).
  - L182-L206: method `run_test_case` executes its unit of logic (key calls: execute_search).
  - L208-L232: method `get_sample_documents` executes its unit of logic (key calls: append, get, print, search).
  - L234-L284: method `generate_dynamic_tests` executes its unit of logic (key calls: TestCase, append, enumerate, findall, get, get_sample_documents).
  - L286-L375: method `get_standard_tests` executes its unit of logic (key calls: TestCase).
  - L377-L447: method `run_all_tests` executes its unit of logic (key calls: append, generate_dynamic_tests, get_standard_tests, isoformat, len, max).
  - L449-L472: method `test_search_from_dashboard` executes its unit of logic (key calls: execute_search).
  - L475-L500: function `main` contains callable workflow logic (key calls: SearchAccuracyTester, dump, dumps, join, len, open).

## Top-Level Utility Scripts

### `accuracy_test.py` (101 lines)
- L1-L3: import section wires external dependencies and local modules.
- L7-L35: module constants/config defaults are declared.
- Walkthrough:
  - L37-L91: function `run_test` contains callable workflow logic (key calls: endswith, get, json, print).

### `backfill_extraction_counts.py` (32 lines)
- L2-L2: import section wires external dependencies and local modules.
- L4-L10: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `bench_processing_keys.py` (65 lines)
- Module intent: Quick benchmark for the optimized processing key lookup.
- L2-L2: import section wires external dependencies and local modules.
- L3-L63: module constants/config defaults are declared.
- Walkthrough:
  - L16-L23: function `get_worker_keys_cached` contains callable workflow logic (key calls: get, list, scan_iter, time).

### `check_all_dbs.py` (23 lines)
- L2-L2: import section wires external dependencies and local modules.
- Walkthrough:
  - L4-L20: function `check_dbs` contains callable workflow logic (key calls: Redis, dbsize, keys, len, print, range).

### `check_completed.py` (27 lines)
- L1-L3: import section wires external dependencies and local modules.
- L5-L11: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_completed_fields.py` (15 lines)
- L1-L3: import section wires external dependencies and local modules.
- L5-L8: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_db_tables.py` (16 lines)
- L1-L1: import section wires external dependencies and local modules.
- L3-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_extraction_status.py` (19 lines)
- L1-L4: import section wires external dependencies and local modules.
- L6-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_file_types.py` (54 lines)
- L2-L6: import section wires external dependencies and local modules.
- Walkthrough:
  - L8-L51: function `check_types` contains callable workflow logic (key calls: Counter, Redis, get, hgetall, items, keys).

### `check_keys.py` (34 lines)
- L1-L3: import section wires external dependencies and local modules.
- L5-L18: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_live_status.py` (48 lines)
- L1-L4: import section wires external dependencies and local modules.
- L6-L38: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_ocr_config.py` (37 lines)
- Module intent: Check OCR configuration parameters.
- L2-L4: import section wires external dependencies and local modules.
- L6-L28: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_queue.py` (41 lines)
- L1-L2: import section wires external dependencies and local modules.
- This module is primarily declarative (imports/constants only).

### `check_queue_issue.py` (72 lines)
- L1-L44: import section wires external dependencies and local modules.
- L6-L45: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_redis.py` (22 lines)
- L1-L4: import section wires external dependencies and local modules.
- L7-L10: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_redis2.py` (20 lines)
- L1-L3: import section wires external dependencies and local modules.
- L5-L17: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_redis3.py` (15 lines)
- L1-L3: import section wires external dependencies and local modules.
- L5-L8: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_redis4.py` (13 lines)
- L1-L3: import section wires external dependencies and local modules.
- L5-L9: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_redis_queues.py` (73 lines)
- L1-L5: import section wires external dependencies and local modules.
- L12-L61: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `check_sqlite_queue.py` (76 lines)
- L1-L39: import section wires external dependencies and local modules.
- L4-L46: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `comprehensive_accuracy_test.py` (129 lines)
- L2-L5: import section wires external dependencies and local modules.
- L7-L7: module constants/config defaults are declared.
- Walkthrough:
  - L9-L16: function `search` contains callable workflow logic (key calls: get, json, print).
  - L18-L25: function `verify_hit` contains callable workflow logic (key calls: get).
  - L27-L126: function `run_test` contains callable workflow logic (key calls: exit, get, len, print, range, search).

### `debug_indexing.py` (87 lines)
- L2-L18: import section wires external dependencies and local modules.
- L13-L13: module constants/config defaults are declared.
- Walkthrough:
  - L20-L84: function `debug_indexing` contains callable workflow logic (key calls: DocumentBuilder, OpenSearchClient, build_document, bulk_index, claim_indexing_work, dumps).

### `debug_ocr_pipeline.py` (54 lines)
- L2-L16: import section wires external dependencies and local modules.
- L8-L8: module constants/config defaults are declared.
- Walkthrough:
  - L18-L45: function `test_smart_ocr` contains callable workflow logic (key calls: OCRWorker, _process_image_file, exists, print, print_exc).

### `debug_queue_item.py` (37 lines)
- L2-L5: import section wires external dependencies and local modules.
- Walkthrough:
  - L7-L32: function `inspect_queue_item` contains callable workflow logic (key calls: Redis, keys, loads, print, zrange).

### `debug_queue_sizes.py` (22 lines)
- L2-L5: import section wires external dependencies and local modules.
- Walkthrough:
  - L7-L19: function `debug_queues` contains callable workflow logic (key calls: RedisQueueManager, print, zcard).

### `debug_redis_keys.py` (64 lines)
- L2-L5: import section wires external dependencies and local modules.
- L16-L56: module constants/config defaults are declared.
- Walkthrough:
  - L18-L19: function `scan_keys` contains callable workflow logic (key calls: keys, sorted).

### `debug_redis_processing.py` (47 lines)
- L2-L3: import section wires external dependencies and local modules.
- Walkthrough:
  - L5-L44: function `debug_processing_keys` contains callable workflow logic (key calls: Redis, extend, hlen, len, print, scan).

### `debug_stats.py` (21 lines)
- L1-L4: import section wires external dependencies and local modules.
- L6-L20: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `debug_stuck_items.py` (33 lines)
- L2-L7: import section wires external dependencies and local modules.
- Walkthrough:
  - L9-L29: function `debug_stuck_items` contains callable workflow logic (key calls: Redis, hgetall, items, len, print, scan_iter).

### `debug_zombies.py` (42 lines)
- L2-L6: import section wires external dependencies and local modules.
- Walkthrough:
  - L8-L39: function `debug_zombies` contains callable workflow logic (key calls: Counter, Redis, hget, items, print, scan).

### `deep_dive_tests.py` (733 lines)
- Module intent: Deep-Dive Accuracy Tests for DocumentSearch System
- L11-L15: import section wires external dependencies and local modules.
- L18-L27: module constants/config defaults are declared.
- Walkthrough:
  - L30-L39: function `report` contains callable workflow logic (key calls: append, print, split).
  - L42-L45: function `section` contains callable workflow logic (key calls: print).
  - L51-L84: function `test_system_health` contains callable workflow logic (key calls: count, hlen, info, ping, report, section).
  - L90-L201: function `test_ocr_accuracy` contains callable workflow logic (key calls: append, basename, count, enumerate, get, hgetall).
  - L207-L270: function `_search` contains callable workflow logic (key calls: endswith, search, startswith, strip).
  - L273-L327: function `test_search_accuracy` contains callable workflow logic (key calls: _search, any, get, join, len, replace).
  - L333-L418: function `test_excel_search` contains callable workflow logic (key calls: _search, any, count, get, isdigit, len).
  - L424-L527: function `test_image_searchability` contains callable workflow logic (key calls: _search, get, join, len, report, search).
  - L533-L579: function `test_docx_search` contains callable workflow logic (key calls: _search, get, join, len, report, search).
  - L585-L627: function `test_embedded_files` contains callable workflow logic (key calls: count, get, len, report, search, section).
  - L633-L650: function `test_search_performance` contains callable workflow logic (key calls: _search, report, section, time).
  - L656-L680: function `test_failure_analysis` contains callable workflow logic (key calls: get, hgetall, items, join, loads, report).
  - L686-L729: function `main` contains callable workflow logic (key calls: dirname, dump, format_exc, join, open, print).

### `dump_keys.py` (18 lines)
- L2-L2: import section wires external dependencies and local modules.
- Walkthrough:
  - L4-L15: function `dump_keys` contains callable workflow logic (key calls: Redis, append, len, open, print, scan_iter).

### `fix_redis_state.py` (33 lines)
- L2-L2: import section wires external dependencies and local modules.
- L4-L7: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `force_clear_processing.py` (24 lines)
- L2-L2: import section wires external dependencies and local modules.
- Walkthrough:
  - L4-L21: function `force_clear` contains callable workflow logic (key calls: Redis, append, delete, len, print, scan_iter).

### `generate_test_data.py` (434 lines)
- Module intent: Test Data Generator for Enterprise Document Search System
- L7-L12: import section wires external dependencies and local modules.
- L45-L93: module constants/config defaults are declared.
- Walkthrough:
  - L96-L99: function `generate_random_text` contains callable workflow logic (key calls: join, len, min, sample).
  - L102-L106: function `generate_filename` contains callable workflow logic (key calls: now, randint, replace, strftime, timedelta).
  - L109-L114: function `create_text_file` contains callable workflow logic (key calls: open, write).
  - L117-L125: function `create_markdown_file` contains callable workflow logic (key calls: now, open, strftime, write).
  - L128-L150: function `create_html_file` contains callable workflow logic (key calls: chr, now, open, replace, strftime, write).
  - L153-L171: function `create_json_file` contains callable workflow logic (key calls: choice, dump, generate_random_text, isoformat, now, open).
  - L174-L194: function `create_xml_file` contains callable workflow logic (key calls: now, open, strftime, write).
  - L197-L215: function `create_csv_file` contains callable workflow logic (key calls: choice, now, open, randint, range, strftime).
  - L218-L232: function `create_docx_file` contains callable workflow logic (key calls: Document, add_heading, add_paragraph, now, save, str).
  - L235-L262: function `create_xlsx_file` contains callable workflow logic (key calls: Workbook, append, choice, randint, range, save).
  - L265-L304: function `create_pdf_file` contains callable workflow logic (key calls: Canvas, drawString, len, now, save, setFont).
  - L307-L411: function `generate_test_data` contains callable workflow logic (key calls: Path, absolute, append, choice, extend, generate_filename).

### `generate_test_dataset.py` (179 lines)
- L1-L12: import section wires external dependencies and local modules.
- L14-L15: module constants/config defaults are declared.
- Walkthrough:
  - L17-L20: function `setup` contains callable workflow logic (key calls: mkdir, print).
  - L22-L27: function `generate_random_text` contains callable workflow logic (key calls: append, capitalize, choices, join, randint, range).
  - L29-L39: function `generate_base_images` contains callable workflow logic (key calls: Draw, append, new, print, randint, range).
  - L41-L47: function `generate_text_files` contains callable workflow logic (key calls: generate_random_text, open, print, randint, range, write).
  - L49-L64: function `generate_docx_files` contains callable workflow logic (key calls: Document, Inches, add_heading, add_paragraph, add_picture, choice).
  - L66-L73: function `generate_image_files` contains callable workflow logic (key calls: Draw, new, print, randint, range, save).
  - L75-L86: function `generate_zips` contains callable workflow logic (key calls: ZipFile, exists, print, range, write, writestr).
  - L88-L95: function `generate_large_files` contains callable workflow logic (key calls: open, print, range, write).
  - L97-L102: function `generate_corrupt_files` contains callable workflow logic (key calls: open, print, range, write).
  - L104-L123: function `main` contains callable workflow logic (key calls: generate_base_images, generate_challenging_files, generate_corrupt_files, generate_docx_files, generate_image_files, generate_large_files).
  - L125-L175: function `generate_challenging_files` contains callable workflow logic (key calls: Draw, astype, choice, clip, imwrite, int).

### `get_all_stats.py` (13 lines)
- L1-L4: import section wires external dependencies and local modules.
- L6-L8: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `init_ocr_counter.py` (23 lines)
- L2-L2: import section wires external dependencies and local modules.
- This module is primarily declarative (imports/constants only).

### `investigate_failures.py` (86 lines)
- Module intent: Investigate failed files - get breakdown and random samples
- L2-L26: import section wires external dependencies and local modules.
- L7-L71: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `monitor_stress_test.py` (89 lines)
- L1-L8: import section wires external dependencies and local modules.
- Walkthrough:
  - L10-L86: function `monitor` contains callable workflow logic (key calls: RedisQueueManager, get, get_queue_statistics, int, print, sleep).

### `ocr_accuracy_tests.py` (598 lines)
- Module intent: OCR Accuracy Deep-Dive Tests
- L14-L18: import section wires external dependencies and local modules.
- L21-L28: module constants/config defaults are declared.
- Walkthrough:
  - L31-L38: function `report` contains callable workflow logic (key calls: append, print, split, upper).
  - L41-L44: function `section` contains callable workflow logic (key calls: print).
  - L47-L85: function `search_ocr` contains callable workflow logic (key calls: search).
  - L91-L118: function `test_ocr_pipeline_status` contains callable workflow logic (key calls: count, report, section, zcard).
  - L124-L176: function `test_ocr_confidence` contains callable workflow logic (key calls: count, items, join, report, search, section).
  - L182-L242: function `test_search_known_ocr_text` contains callable workflow logic (key calls: add, any, append, get, len, report).
  - L248-L331: function `test_image_type_accuracy` contains callable workflow logic (key calls: count, items, len, report, search, section).
  - L337-L388: function `test_ocr_failure_patterns` contains callable workflow logic (key calls: append, basename, get, hgetall, items, join).
  - L394-L448: function `test_content_search_from_ocr` contains callable workflow logic (key calls: append, get, items, len, report, search).
  - L454-L522: function `test_ocr_text_quality` contains callable workflow logic (key calls: append, get, isalnum, len, max, min).
  - L528-L547: function `test_ocr_search_performance` contains callable workflow logic (key calls: report, search_ocr, section, time).
  - L553-L594: function `main` contains callable workflow logic (key calls: dirname, dump, fn, format_exc, join, open).

### `ocr_content_probe.py` (51 lines)
- Module intent: Probe OCR'd documents to find ones with real text for accuracy testing.
- L3-L3: import section wires external dependencies and local modules.
- L4-L42: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `quick_validate.py` (111 lines)
- Module intent: Quick dashboard sync validation - Redis raw vs get_queue_statistics() output
- L2-L44: import section wires external dependencies and local modules.
- L5-L97: module constants/config defaults are declared.
- Walkthrough:
  - L48-L50: function `si` contains callable workflow logic (key calls: int).

### `test_checkpoint_resume.py` (157 lines)
- Module intent: Test script to verify checkpoint and resume functionality with Redis persistence
- L5-L15: import section wires external dependencies and local modules.
- Walkthrough:
  - L21-L147: function `test_checkpoint_resume` contains callable workflow logic (key calls: CheckpointManager, Path, add_discovered_file, config_get, create_checkpoint, exists).

### `test_components.py` (421 lines)
- Module intent: Test Script - Verify all components are working
- L6-L7: import section wires external dependencies and local modules.
- Walkthrough:
  - L12-L52: function `test_redis_connection` contains callable workflow logic (key calls: delete, from_url, get, ping, print, set).
  - L55-L105: function `test_redis_queue_manager` contains callable workflow logic (key calls: RedisQueueManager, add_discovered_file, delete, get_queue_stats, print, print_exc).
  - L108-L159: function `test_nlp_corrector` contains callable workflow logic (key calls: TextCorrector, correct, lower, print, print_exc).
  - L162-L213: function `test_image_preprocessor` contains callable workflow logic (key calls: ImagePreprocessor, frombuffer, imdecode, imencode, len, preprocess).
  - L216-L269: function `test_query_builder` contains callable workflow logic (key calls: QueryBuilder, build_search_query, lower, print, print_exc, str).
  - L272-L313: function `test_opensearch_connection` contains callable workflow logic (key calls: OpenSearch, count, exists, info, ping, print).
  - L316-L378: function `test_search_accuracy` contains callable workflow logic (key calls: OpenSearch, QueryBuilder, build_search_query, count, exists, ping).
  - L381-L417: function `main` contains callable workflow logic (key calls: items, len, print, sum, test_image_preprocessor, test_nlp_corrector).

### `test_deep_extraction.py` (58 lines)
- L1-L6: import section wires external dependencies and local modules.
- L10-L15: module constants/config defaults are declared.
- Walkthrough:
  - L17-L55: function `extract_embedded_images` contains callable workflow logic (key calls: Path, ZipFile, copyfileobj, endswith, error, exists).

### `test_metrics_sync.py` (112 lines)
- Module intent: Comprehensive Dashboard Metrics Sync Test
- L7-L11: import section wires external dependencies and local modules.
- Walkthrough:
  - L13-L109: function `test_metrics_sync` contains callable workflow logic (key calls: extract_summary, format_number, format_size, get, get_queue_manager, get_queue_statistics).

### `test_redis.py` (72 lines)
- Module intent: Test Redis Queue Manager
- L4-L13: import section wires external dependencies and local modules.
- Walkthrough:
  - L15-L69: function `test_redis_queue` contains callable workflow logic (key calls: RedisQueueManager, add_discovered_file, claim_extraction_work, complete_extraction, get_queue_stats, int).

### `test_worker_claim.py` (44 lines)
- L1-L6: import section wires external dependencies and local modules.
- L8-L8: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `validate_dashboard_sync.py` (225 lines)
- Module intent: Dashboard Data Sync Validation Script
- L5-L13: import section wires external dependencies and local modules.
- Walkthrough:
  - L15-L222: function `main` contains callable workflow logic (key calls: Redis, abs, execute, format, format_size, get).

### `validate_heartbeats.py` (57 lines)
- Module intent: Validate worker heartbeats – checks that all workers are alive and reporting.
- L2-L9: import section wires external dependencies and local modules.
- L11-L11: module constants/config defaults are declared.
- Walkthrough:
  - L13-L53: function `main` contains callable workflow logic (key calls: add, fromtimestamp, get_queue_manager, get_worker_heartbeats, items, join).

### `verify_dashboard_data.py` (51 lines)
- Module intent: Quick test to verify dashboard data pipeline works end-to-end.
- L2-L4: import section wires external dependencies and local modules.
- L6-L50: module constants/config defaults are declared.
- Walkthrough:
  - L18-L24: function `safe_int` contains callable workflow logic (key calls: int).

### `verify_fix_logic.py` (31 lines)
- L2-L8: import section wires external dependencies and local modules.
- Walkthrough:
  - L10-L28: function `verify_logic` contains callable workflow logic (key calls: RedisQueueManager, get_queue_stats, items, print).

### `verify_preprocessing.py` (126 lines)
- L2-L12: import section wires external dependencies and local modules.
- Walkthrough:
  - L14-L27: function `create_base_image` contains callable workflow logic (key calls: ones, putText, rectangle).
  - L29-L36: function `apply_rotation` contains callable workflow logic (key calls: rotate).
  - L38-L39: function `apply_inversion` contains callable workflow logic (key calls: bitwise_not).
  - L41-L52: function `apply_shadow` contains callable workflow logic (key calls: astype, clip, copy, int, range, zeros).
  - L54-L123: function `test_preprocessing` contains callable workflow logic (key calls: ImagePreprocessor, NamedTemporaryFile, apply_inversion, apply_rotation, apply_shadow, chr).

### `verify_search.py` (48 lines)
- L1-L4: import section wires external dependencies and local modules.
- L8-L18: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).

### `verify_system.py` (201 lines)
- Module intent: Quick System Verification Script
- L6-L9: import section wires external dependencies and local modules.
- Walkthrough:
  - L13-L63: function `check_opensearch` contains callable workflow logic (key calls: get, json, print, str).
  - L66-L85: function `check_redis` contains callable workflow logic (key calls: Redis, keys, len, ping, print).
  - L88-L120: function `check_logs` contains callable workflow logic (key calls: len, open, print, readlines, strip).
  - L123-L174: function `test_search` contains callable workflow logic (key calls: get, json, post, print, str).
  - L177-L197: function `main` contains callable workflow logic (key calls: check_logs, check_opensearch, check_redis, print, test_search).

## Tools (tools/)

### `tools/print_config_info.py` (6 lines)
- L1-L1: import section wires external dependencies and local modules.
- L2-L2: module constants/config defaults are declared.
- This module is primarily declarative (imports/constants only).
