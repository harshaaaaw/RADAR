# Enterprise Document Search System - Complete Codebase Analysis

**Date:** February 9, 2026  
**System Version:** 1.0.0  
**Build Date:** 2026-01-21

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
4. [Queue Management](#queue-management)
5. [Worker Processes](#worker-processes)
6. [Data Pipeline](#data-pipeline)
7. [Search & API](#search--api)
8. [Configuration Management](#configuration-management)
9. [Monitoring & Ops](#monitoring--ops)
10. [Code Flow](#code-flow)
11. [Key Files Reference](#key-files-reference)

---

## Executive Summary

The Enterprise Document Search System is a **high-performance production-grade document indexing and search platform** designed to process large-scale document collections (2+ million documents) with full extraction, OCR, and search capabilities.

### Core Statistics
- **Target Throughput:** 245-420 files/sec extraction, 12,000-20,000 docs/sec indexing
- **Processing Time:** 2-4 hours for 2 million documents
- **Workers:** 150+ parallel processes
- **Storage:** OpenSearch 12GB heap, Tika 7x2GB instances
- **OCR:** 30-50 Tesseract workers in parallel
- **Platform:** Windows Server 2022, Python 3.10+, Java 11+

### Key Features
✅ Multi-stage distributed processing pipeline  
✅ Size-based workload routing (4 tracks)  
✅ Express lane for small files (<1MB)  
✅ Bloom filter deduplication  
✅ Persistent SQLite/Redis queues  
✅ Crash recovery & resume capability  
✅ Real-time monitoring dashboard  
✅ NLP-based text correction  
✅ Advanced OCR with preprocessing  
✅ Full-text search with accurate matching  

---

## System Architecture

### High-Level Pipeline

```
DISCOVERY (4 workers)
    |
    v (files discovered)
EXTRACTION (100 workers)
    |
    +→ [Tika 7x2GB] for content extraction
    |
    v (documents extracted)
INDEXING (16 workers)
    |
    +→ [OpenSearch 12GB] for full-text indexing
    |
    v (documents indexed → searchable)
    ↓ (parallel, doesn't block search)
OCR (30-50 workers)
    |
    +→ [Tesseract] for image/scanned document OCR
    |
    v (OCR text indexed as background enrichment)
SEARCH API
    |
    +→ [FastAPI] REST endpoints
    +→ [Streamlit] Dashboard
```

### Processing Stages

1. **Discovery** - Recursive filesystem scanning, file deduplication via Bloom filters
2. **Extraction** - Tika-based content extraction (PDF, DOCX, XLS, TXT, etc.)
3. **Indexing** - Bulk indexing to OpenSearch with adaptive batching
4. **OCR** - Tesseract-based text extraction from images and scanned documents
5. **Search** - REST API + Web dashboard for document retrieval

### Size-Based Routing

Files are routed to different worker pools based on size:

| Category | Size Range | Workers | Tika Port | Target Time |
|----------|-----------|---------|-----------|------------|
| **Tiny** | < 1 MB | Fast track | 9998 | 0.2 sec |
| **Small** | 1-10 MB | Standard | 9997 | 2 sec |
| **Medium** | 10-50 MB | Heavy | 9996 | 15 sec |
| **Large** | > 50 MB | Extreme | 9995 | 60 sec |

---

## Core Components

### 1. Main Entry Point (`src/main.py`)

**Purpose:** CLI interface and application launcher

**Commands:**
```python
python src/main.py check      # Verify all services running
python src/main.py init       # Initialize system, create dirs, validate config
python src/main.py start      # Begin document processing
python src/main.py ui         # Start Streamlit dashboard
```

**Key Functions:**
- `check()` - Health checks for Tika, OpenSearch, Tesseract
- `init()` - Database initialization, directory creation
- `start()` - Master orchestrator launch with mode selection (full/resume/incremental)

---

### 2. Configuration Management (`src/core/config_manager.py`)

**Purpose:** Centralized configuration loading and validation

**Key Classes:**
- `PathConfig` - Directory and file paths
- `TikaInstance` - Individual Tika server configuration
- `WorkerPool` - Worker pool definitions
- `ExtractionConfig` - Extraction stage configuration
- `OpenSearchConfig` - Search index configuration
- `DiscoveryConfig` - File discovery configuration

**Configuration Hierarchy:**
```yaml
config/
  ├── default-config.yaml      # Base configuration
  ├── aws-config.yaml          # AWS production settings
  └── local-config.yaml        # Development overrides
```

**Key Attributes:**
```python
config.paths.source_drive       # Root directory to scan
config.extraction.tika.instances # List of Tika servers
config.indexing.opensearch      # OpenSearch cluster config
config.discovery.num_workers    # Number of discovery workers
config.extraction.total_workers # Total extraction workers
```

---

### 3. Logging Management (`src/core/logging_manager.py`)

**Purpose:** Structured logging with rotation and component separation

**Features:**
- Centralized logging configuration
- Component-specific log files
- Rotating file handlers
- JSON logging support (optional)
- Error log segregation

**Log Outputs:**
```
logs/
  ├── application.log           # Main application log
  ├── errors.log                # Errors and critical messages
  ├── discovery.log             # Discovery worker logs
  ├── extraction.log            # Extraction worker logs
  ├── indexing.log              # Indexing worker logs
  ├── ocr.log                   # OCR worker logs
  └── api.log                   # API server logs
```

**Usage:**
```python
from core.logging_manager import get_logger
logger = get_logger("component_name")
logger.info("Message")
logger.error("Error message")
```

---

### 4. Constants (`src/core/constants.py`)

**Purpose:** System-wide constant definitions

**Key Enums:**
```python
class QueueStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    DUPLICATE = "duplicate"

class SizeCategory(str, Enum):
    TINY = "tiny"       # < 1 MB
    SMALL = "small"     # 1-10 MB
    MEDIUM = "medium"   # 10-50 MB
    LARGE = "large"     # > 50 MB

class WorkerPoolType(str, Enum):
    FAST_TRACK = "fast_track"
    STANDARD_TRACK = "standard_track"
    HEAVY_TRACK = "heavy_track"
    EXTREME_TRACK = "extreme_track"

class ProcessingStage(str, Enum):
    DISCOVERY = "discovery"
    EXTRACTION = "extraction"
    INDEXING = "indexing"
    OCR = "ocr"
    COMPLETED = "completed"

class ErrorType(str, Enum):
    TIMEOUT = "timeout"
    CORRUPTED_FILE = "corrupted_file"
    PERMISSION_DENIED = "permission_denied"
    SERVICE_UNAVAILABLE = "service_unavailable"
    PARSE_ERROR = "parse_error"
    OCR_ERROR = "ocr_error"
    # ... 12 more error types
```

**Batch Sizes:**
```python
DISCOVERY_BATCH_SIZE = 5000
INDEXING_BATCH_SIZE_INITIAL = 1000
OCR_UPDATE_BATCH_SIZE = 100
QUEUE_SYNC_BATCH_SIZE = 5000
```

---

## Queue Management

### Architecture Choice: SQLite + Redis Hybrid

The system supports **two queue backends**:

#### 1. SQLite Queue Manager (`src/core/queue_manager.py`)

**Default backend for development**

**Features:**
- ACID transactions with proper isolation
- WAL mode for concurrent access
- Thread-safe with connection pooling
- Persistent storage in `queue_db/queues.db`
- Full SQL query capability

**Database Schema:**
```sql
discovered_files    -- All discovered files with metadata
extraction_queue    -- Files pending extraction (by size category)
indexing_queue      -- Documents pending indexing
ocr_queue           -- Documents pending OCR
failed_files        -- Files that failed processing
completed_files     -- Successfully processed files
file_hashes         -- SHA-256 hashes for deduplication
content_hashes      -- Content hashes for duplicate detection
worker_heartbeats   -- Worker process status
```

**Key Tables:**

```python
# discovered_files
id, file_path, file_name, file_size, file_extension,
file_hash, last_modified, created, size_category,
priority, status, discovered_at, worker_id,
processing_started_at, processing_completed_at,
error_type, error_message, retry_count

# extraction_queue
id, file_id, file_path, file_size, size_category,
priority, status, worker_id, claimed_at, completed_at,
processing_time_ms, FOREIGN KEY (file_id)

# indexing_queue
id, file_id, document_json, priority, status,
worker_id, claimed_at, completed_at

# ocr_queue
id, file_id, document_id, needs_ocr, priority,
status, worker_id, claimed_at, completed_at

# failed_files
id, file_id, file_path, error_type, error_message,
failed_at, retry_count
```

#### 2. Redis Queue Manager (`src/core/redis_queue_manager.py`)

**High-performance backend for production**

**Data Structures:**
- **Lists:** FIFO queues for discovery and indexing
- **Sorted Sets:** Priority queues with scores
- **Hashes:** Metadata storage (fast KV lookups)
- **Sets:** Deduplication tracking
- **Counters:** Aggregated statistics

**Redis Keys:**
```python
docsearch:queue:discovery           # Discovery folder FIFO queue
docsearch:queue:extraction          # Extraction work queue (size-based)
docsearch:queue:extraction:tiny     # Tiny files queue
docsearch:queue:extraction:small    # Small files queue
docsearch:queue:extraction:medium   # Medium files queue
docsearch:queue:extraction:large    # Large files queue
docsearch:queue:indexing            # Indexing pipeline
docsearch:queue:ocr                 # OCR pipeline
docsearch:processing:extraction:*   # In-flight extraction jobs
docsearch:processing:indexing:*     # In-flight indexing jobs
docsearch:processing:ocr:*          # In-flight OCR jobs
docsearch:files                     # Hash: file_id → metadata
docsearch:completed                 # Hash: file_hash → completion data
docsearch:failed                    # Hash: file_id → failure data
docsearch:file_hashes               # Set of known file hashes
docsearch:content_hashes            # Set of known content hashes
docsearch:worker_heartbeats         # Hash: worker_id → last_heartbeat
```

**Key Operations:**
```python
# Discovery
queue_manager.push_folder(folder_path)      # Add folder to scan queue
folder = queue_manager.pop_folder()         # Get next folder to scan

# File management
queue_manager.add_discovered_file(...)      # Register discovered file
queue_manager.claim_extraction_work(size_category, batch_size)
queue_manager.mark_extraction_completed(...) # Mark file extracted

# Indexing
queue_manager.claim_indexing_work(worker_id, batch_size)
queue_manager.mark_indexing_completed(...)

# OCR
queue_manager.claim_ocr_work(worker_id, batch_size)
queue_manager.update_ocr_text(...)          # Update document with OCR text

# Statistics
queue_manager.get_queue_statistics()        # Current queue snapshot
queue_manager.get_size_statistics()         # Files by processing stage
queue_manager.get_failed_files(limit)       # Failed files for review
```

### Queue Flow

```
DISCOVERY QUEUE
│   ↓ (folders to scan)
├─→ Discovery Worker pops folder
│   ├─→ Scans directory
│   ├─→ Hashes files (SHA-256)
│   ├─→ Checks Bloom filter for duplicates
│   └─→ Pushes files to EXTRACTION QUEUE
│
EXTRACTION QUEUE (size-based)
│   ├─→ tiny    (< 1MB)   → Fast track workers
│   ├─→ small   (1-10MB)  → Standard workers
│   ├─→ medium  (10-50MB) → Heavy workers
│   └─→ large   (> 50MB)  → Extreme workers
│
├─→ Extraction Worker claims file
│   ├─→ Sends to Tika server
│   ├─→ Applies NLP correction
│   └─→ Pushes document to INDEXING QUEUE
│
INDEXING QUEUE
│   ↓ (documents to index)
├─→ Indexing Worker claims batch
│   ├─→ Creates OpenSearch bulk request
│   ├─→ Submits batch
│   └─→ Marks files searchable
│       └─→ Pushes to OCR QUEUE (parallel)
│
OCR QUEUE
│   ↓ (documents needing OCR)
├─→ OCR Worker processes image/scanned doc
│   ├─→ Preprocesses image (sharpen, denoise, etc.)
│   ├─→ Runs Tesseract OCR
│   ├─→ Corrects with NLP
│   └─→ Updates document in OpenSearch
```

### Deduplication Strategy

**Multi-Level Deduplication:**

1. **File-Level Deduplication (Discovery Stage)**
   - SHA-256 hash of file bytes
   - Bloom filter for fast O(1) membership testing
   - Database lookup for confirmation
   - Prevents duplicate file extraction
   - False positive rate: 1% (configurable)

2. **Content-Level Deduplication (Extraction Stage)**
   - SHA-256 hash of normalized content
   - Detects files with identical content but different binary
   - Prevents duplicate indexing
   - Detected after Tika extraction

3. **Duplicate Status Tracking**
   - Status: `DUPLICATE` in database
   - Links to original file via hash
   - Not indexed separately (avoids search noise)

---

## Worker Processes

### 1. Discovery Worker (`src/discovery/discovery_worker.py`)

**Purpose:** Recursive filesystem scanning and file enumeration

**Configuration:**
```python
num_workers: 4                    # Number of discovery workers
batch_size: 5000                  # Files per batch
target_rate: 1000                 # Target files/second
exclude_patterns: [...]           # Patterns to skip
filter_by_extension: true         # Filter by extension
```

**Workflow:**
```
1. Pop folder from queue
2. Get cached mtime (for differential scanning)
3. Scan directory (non-recursively - just immediate children)
4. Push subfolders back to queue (BFS traversal)
5. Hash files and check Bloom filter
6. Queue unique files to EXTRACTION QUEUE
7. Repeat until queue empty
```

**Key Methods:**

```python
def run(self)
    # Main worker loop
    
def _initialize_bloom_filter(self)
    # Load from disk or create new
    # Populate from database
    
def _should_deduplicate_by_scan(self, file_path, file_size, mtime)
    # Check if file metadata matches existing record
```

**Components:**

- **FileScanner** - Non-recursive directory iteration with filtering
- **HashCalculator** - SHA-256 file hashing (mmap for large files)
- **BloomFilter** - Fast duplicate detection

---

### 2. Extraction Worker (`src/extraction/extraction_worker.py`)

**Purpose:** Content extraction from files using Tika

**Configuration:**
```python
num_workers: 100                  # Total extraction workers
pools:
  fast_track:
    num_workers: 20
    tika_ports: [9998]
    target_time_seconds: 0.2
  standard_track:
    num_workers: 40
    tika_ports: [9997]
    target_time_seconds: 2
  heavy_track:
    num_workers: 30
    tika_ports: [9996]
    target_time_seconds: 15
  extreme_track:
    num_workers: 10
    tika_ports: [9995]
    target_time_seconds: 60
```

**Workflow:**
```
1. Claim extraction work (size-category specific)
2. Send file to Tika (HTTP PUT request)
3. Parse Tika response (JSON)
4. Normalize and clean extracted content
5. Calculate content hash
6. Detect if OCR needed (low text detection)
7. Emit DOCUMENT_JSON
8. Push to INDEXING QUEUE
9. Push to OCR QUEUE (if needed)
```

**Key Methods:**

```python
def run(self)
    # Main worker loop with memory management
    
def _process_file(self, work_item)
    # Send to Tika, parse response, handle errors
    
def _heartbeat_loop(self)
    # Periodic status updates
```

**Components:**

- **TikaClient** - HTTP client with retry logic and connection pooling
- **ContentExtractor** - Parses Tika responses and normalizes content
- **TextCorrector (NLP)** - Optional text correction pre-indexing

---

### 3. Indexing Worker (`src/indexing/indexing_worker.py`)

**Purpose:** Bulk indexing of documents to OpenSearch

**Configuration:**
```python
num_workers: 16                   # Number of indexing workers
initial_batch_size: 1000          # Starting documents per batch
min_batch_size: 100
max_batch_size: 5000
target_batch_time: 10.0           # Seconds per batch
fast_threshold: 2.0               # Seconds (increase batch)
slow_threshold: 30.0              # Seconds (decrease batch)
```

**Adaptive Batching:**

The indexing worker automatically adjusts batch size based on performance:

```
Measure time to index batch:
  if time < 2 seconds (fast_threshold):
    increase batch size by step (e.g., +100)
  else if time > 30 seconds (slow_threshold):
    decrease batch size by step (e.g., -100)
  else:
    keep same size
```

This keeps OpenSearch operating at optimal throughput (~20K docs/sec).

**Workflow:**
```
1. Claim indexing work (micro-batch accumulation)
2. Accumulate documents until:
   - Batch size reached, OR
   - 10 second flush timeout
3. Send bulk index request to OpenSearch
4. Measure response time
5. Adjust batch size for next iteration
6. Continue until empty
```

**Key Methods:**

```python
def run(self)
    # Main worker loop with adaptive batching
    
def _process_batch(self, documents)
    # Send bulk request, measure time, adjust batch size
    
def _get_field_types(self)
    # Ensure all fields exist in mapping
```

**Components:**

- **OpenSearchClient** - Client with connection pooling
- **DocumentBuilder** - Constructs indexable documents

---

### 4. OCR Worker (`src/ocr/ocr_worker.py`)

**Purpose:** Extract text from images and scanned documents

**Configuration:**
```python
num_workers: 30                   # Initial OCR workers
tesseract:
  command: "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
  languages: ['eng']              # Language models
  engine_mode: "LSTM"             # 0=Legacy, 1=LSTM, 2=Combined
  page_segmentation_mode: "AUTO"  # 0-13 PSM modes
  timeout_seconds: 120
quality:
  min_confidence: 25              # Minimum acceptable confidence
  good_confidence: 70             # Threshold for "good" quality
```

**Workflow:**
```
1. Claim OCR work (documents with images or low text)
2. Extract images from document
3. Preprocess image (sharpen, denoise, CLAHE, gamma)
4. Run Tesseract with confidence scores
5. Apply NLP text correction
6. Update document in OpenSearch
7. Continue until queue empty
```

**Key Methods:**

```python
def run(self)
    # Main worker loop

def _process_document(self, doc_id, document_json)
    # Extract images, run OCR, update OpenSearch

def _process_pdf(self, file_path)
    # Convert PDF pages to images (pdf2image)

def _process_image(self, image_path)
    # Preprocess, run Tesseract, get confidence
```

**Components:**

- **ImagePreprocessor** - Advanced preprocessing (CLAHE, denoising, sharpening)
- **TesseractWrapper** - Tesseract integration with confidence scoring
- **TextCorrector (NLP)** - Post-OCR text correction

---

## Data Pipeline

### File Processing States

```
PENDING
  ├─→ PROCESSING (in extraction queue)
  │   └─→ COMPLETED (extracted, moved to indexing)
  │       ├─→ COMPLETED (indexed, searchable)
  │       └─→ Parallel: OCR PENDING
  │           ├─→ OCR PROCESSING
  │           └─→ OCR COMPLETED
  │
  └─→ DUPLICATE (matched in Bloom filter)
  └─→ SKIPPED (extension filtered)
  └─→ FAILED (error during processing)
```

### Document Structure (OpenSearch)

```json
{
  "file_path": "/path/to/file.pdf",
  "file_name": "file.pdf",
  "file_hash": "sha256_of_binary",
  "content_hash": "sha256_of_normalized_content",
  "file_size": 1048576,
  "main_content": "Extracted text from Tika...",
  "embedded_content": "Text from embedded files...",
  "ocr_content": "Text from OCR (populated later)...",
  "ocr_confidence": 0.87,
  "ocr_completed": true,
  "metadata": {
    "content_type": "application/pdf",
    "author": "John Doe",
    "created_date": "2023-01-15T10:30:00",
    "page_count": 42
  },
  "needs_ocr": false,
  "embedded_count": 2,
  "indexed_at": "2026-02-09T14:30:00",
  "extraction_time_ms": 245
}
```

### Document Lifecycle

```
1. DISCOVERY
   - File discovered: file_path, size, hash
   - Inserted to discovered_files table
   - Status: PENDING

2. EXTRACTION
   - Extraction worker claims file
   - Tika extracts content
   - ContentExtractor parses response
   - Embedded files identified
   - Document JSON created
   - Status: PROCESSING → COMPLETED

3. INDEXING
   - DocumentBuilder formats for OpenSearch
   - Indexing worker submits bulk request
   - Document becomes SEARCHABLE
   - Status: PROCESSING → INDEXING

4. OCR (Parallel)
   - If needs_ocr=true, added to OCR queue
   - ImagePreprocessor enhances images
   - Tesseract extracts text
   - TextCorrector cleans OCR output
   - OCR update sent to OpenSearch
   - ocr_content and ocr_confidence populated
```

---

## Search & API

### FastAPI Server (`src/api/search_api.py`)

**Configuration:**
```python
api:
  host: "127.0.0.1"
  port: 8000
  workers: 4
  require_auth: false               # (or true with API_TOKEN env var)
  cors_enabled: true
  allowed_origins: ["*"]
  search:
    default_fields:
      - main_content
      - embedded_content
      - ocr_content
      - file_name
```

**REST Endpoints:**

```python
GET /
    # Root endpoint - API info

GET /search?q=<query>&page=<int>&size=<int>&fields=<str>
    # Search documents
    # Query: search terms (supports "quoted phrases")
    # Page: 1-indexed page number
    # Size: results per page (1-100)
    # Fields: comma-separated field list to search
    # Returns: { total, page, size, results: [{ id, score, document, highlights }] }

GET /document/{doc_id}
    # Retrieve specific document by ID
    # Returns: { id, document }

GET /stats
    # System statistics (discovered, indexed, failed counts)

GET /health
    # Health check endpoint
```

**Authentication:**
```python
def verify_token(authorization: Optional[str] = Header(None))
    # Validates Bearer token if require_auth=true
    # Token from API_TOKEN environment variable
```

### Query Builder (`src/api/query_builder.py`)

**Search Features:**

1. **Exact Phrase Matching**
   ```
   "search term" → match_phrase with slop=0
   ```

2. **Numeric/Formatted Value Matching**
   ```
   Query: "2,480,821.04"
   Matched against: .keyword fields (exact) + analyzed (fuzzy)
   ```

3. **Boolean Operators (Future)**
   ```
   search AND term
   search OR term
   search NOT term
   ```

4. **Field Boosting**
   ```python
   file_name: 3.0x boost (most relevant)
   main_content: 2.0x boost
   ocr_content: 1.5x boost
   embedded_content: 1.0x boost
   ```

5. **Highlighting**
   ```
   300-char context around matches
   3 separate highlights per field
   ```

**No Fuzzy/Phonetic Matching:**
- Removed fuzzy matching (e.g., "teh" ≠ "the")
- Removed phonetic matching (Metaphone)
- **Rationale:** 100% accuracy preferred over recall for financial documents

---

### Streamlit Dashboard (`src/ui/dashboard.py`)

**Purpose:** Real-time monitoring and control UI

**Features:**

1. **Queue Statistics**
   - Files discovered (count and size)
   - In-pipeline (extraction + indexing + OCR)
   - Searchable (completed and indexed)
   - Failed (with error breakdown)

2. **Performance Metrics**
   - Throughput (files/sec)
   - Time-to-searchable (avg latency)
   - Cumulative stats (total processed, time elapsed)

3. **Failed Files Review**
   - Top 50 failed files
   - Error types and messages
   - Retry count
   - Quick links to file paths

4. **OCR Pending**
   - Documents awaiting OCR
   - Confidence scores
   - File types

5. **Largest Files**
   - Top 10 completed files
   - Processing times
   - Success rate

6. **System Controls**
   - Pause/Resume buttons
   - View logs
   - Open failed files

**Performance Optimization:**
- Caching with 30-60 second TTL
- Timeout protection (5 second max per query)
- Thread pool executor
- Cache invalidation on state changes

---

## Configuration Management

### Configuration Files

**Location:** `config/` directory

**Files:**
1. `default-config.yaml` - Base configuration
2. `aws-config.yaml` - AWS production settings
3. `local-config.yaml` - Development overrides

### Configuration Schema

```yaml
# Paths
paths:
  source_drive: "C:\data\documents"
  working_root: "C:\DocumentSearch\work"
  queue_db: "C:\DocumentSearch\work\queue_db"
  temp_dir: "C:\temp"
  logs_dir: "C:\DocumentSearch\logs"

# Discovery
discovery:
  num_workers: 4
  batch_size: 5000
  exclude_patterns:
    - "*.tmp"
    - "$RECYCLE.BIN"
  filter_by_extension: true
  included_extensions:
    - ".pdf"
    - ".docx"
    - ".xlsx"

# Extraction (Tika)
extraction:
  total_workers: 100
  pools:
    fast_track:
      num_workers: 20
      tika_ports: [9998]
    standard_track:
      num_workers: 40
      tika_ports: [9997]
    heavy_track:
      num_workers: 30
      tika_ports: [9996]
    extreme_track:
      num_workers: 10
      tika_ports: [9995]
  tika:
    instances:
      - host: localhost
        port: 9998
        memory_mb: 2048
    timeout_seconds: 300
    max_retries: 3
    retry_backoff_seconds: [1, 3, 10]

# Indexing (OpenSearch)
indexing:
  opensearch:
    hosts:
      - "https://localhost:9200"
    username: "admin"
    password: "admin123"
    index_name: "documents"
    initial_batch_size: 1000
    min_batch_size: 100
    max_batch_size: 5000
    target_batch_time_seconds: 10.0
    timeout_seconds: 60

# OCR (Tesseract)
ocr:
  num_workers: 30
  tesseract:
    command: "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
    languages: ["eng"]
    engine_mode: "LSTM"
    page_segmentation_mode: "AUTO"
    timeout_seconds: 120
  quality:
    min_confidence: 25
    good_confidence: 70

# NLP Text Correction
nlp:
  enabled: true
  spacy_model: "en_core_web_sm"

# Logging
logging:
  default_level: "INFO"
  use_json: false
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
```

---

## Monitoring & Ops

### 1. Health Monitor (`src/orchestrator/health_monitor.py`)

**Checks:**
- Tika instance availability (all ports)
- OpenSearch cluster health
- Tesseract executable availability

**Usage:**
```bash
python src/main.py check
```

### 2. Resource Monitor (`src/orchestrator/resource_monitor.py`)

**Metrics:**
- CPU usage (%)
- Memory usage (GB, %)
- Disk space (GB free, %)

**Thresholds:**
```yaml
orchestrator:
  cpu:
    high_threshold_percent: 85
  memory:
    warning_threshold_gb: 50
    critical_threshold_gb: 60
  disk:
    warning_threshold_gb: 100
    critical_threshold_gb: 50
```

### 3. Checkpoint Manager (`src/orchestrator/checkpoint_manager.py`)

**Purpose:** State persistence for resume capability

**Checkpoint Contents:**
```python
{
  "timestamp": "20260209_143000",
  "created_at": "2026-02-09T14:30:00",
  "queue_stats": {
    "discovered": 50000,
    "extraction_pending": 20000,
    "indexing_pending": 5000,
    "ocr_pending": 15000,
    "completed": 10000,
    "failed": 50
  }
}
```

**Usage:**
```bash
python src/main.py start --mode=resume
```

### 4. Recovery Manager (`src/orchestrator/recovery_manager.py`)

**Purpose:** Detect and rescue "zombie" zombie tasks from previous runs

**Zombie Types:**
1. **Orphaned Extraction** - File marked PROCESSING but not in any extraction queue
2. **Orphaned Indexing** - Document marked PROCESSING but not in indexing queue
3. **Orphaned OCR** - Document marked PROCESSING but not in OCR queue

**Recovery Strategy:**
1. Scan all file records
2. Check if marked PROCESSING but not found in corresponding queue
3. Requeue file to appropriate queue
4. Reset worker_id and timestamps

**Triggers On:**
- System startup (automatic)
- After unexpected crashes
- Manual invocation: `python src/tools/recovery_debug.py`

---

## Worker Orchestration

### Master Orchestrator (`src/orchestrator/master_orchestrator.py`)

**Purpose:** Spawns and manages all worker processes

**Initialization:**
```python
def start(self, mode: str = 'full')
    # full: Reset discovery, start fresh
    # resume: Load checkpoint, continue processing
    # incremental: Skip already discovered, add new files
```

**Worker Spawning:**
```python
def _spawn_discovery_workers(self)
    # 4 discovery workers (parallel directory traversal)

def _spawn_extraction_workers(self)
    # 100 extraction workers across 4 Tika instances
    # Fast/Standard/Heavy/Extreme tracks

def _spawn_indexing_workers(self)
    # 16 indexing workers
    # Micro-batch accumulation with adaptive sizing

def _spawn_ocr_workers(self)
    # 30-50 OCR workers
    # Processes after indexing (parallel, non-blocking)
```

**Management:**
```python
def _main_loop(self)
    # Health checks
    # Worker crash recovery
    # Resource monitoring
    # Statistics logging

def _signal_handler(self, sig, frame)
    # Graceful shutdown on Ctrl+C
    # Allows in-flight work to complete
    # Saves checkpoint
```

---

## Key Files Reference

### Core System
- **src/main.py** - CLI entry point, commands
- **src/orchestrator.py** - Top-level orchestration module
- **src/orchestrator/master_orchestrator.py** - Worker spawning and management

### Queue Management
- **src/core/queue_manager.py** - SQLite queue (default)
- **src/core/redis_queue_manager.py** - Redis queue (production)

### Configuration & Logging
- **src/core/config_manager.py** - Configuration loading
- **src/core/constants.py** - System constants
- **src/core/logging_manager.py** - Structured logging

### Discovery Stage
- **src/discovery/discovery_worker.py** - Discovery orchestration
- **src/discovery/file_scanner.py** - Directory traversal
- **src/discovery/hash_calculator.py** - File hashing
- **src/utils/bloom_filter.py** - Duplicate detection

### Extraction Stage
- **src/extraction/extraction_worker.py** - Extraction orchestration
- **src/extraction/tika_client.py** - Tika HTTP client
- **src/extraction/content_extractor.py** - Tika response parsing

### Indexing Stage
- **src/indexing/indexing_worker.py** - Indexing orchestration
- **src/indexing/opensearch_client.py** - OpenSearch client
- **src/indexing/document_builder.py** - Document formatting

### OCR Stage
- **src/ocr/ocr_worker.py** - OCR orchestration
- **src/ocr/image_preprocessor_advanced.py** - Image enhancement
- **src/ocr/tesseract_wrapper.py** - Tesseract integration

### API & Search
- **src/api/search_api.py** - FastAPI REST server
- **src/api/query_builder.py** - OpenSearch query DSL

### UI
- **src/ui/dashboard.py** - Streamlit dashboard (1739 lines)

### NLP
- **src/nlp/text_corrector.py** - SpaCy-based text correction

### Orchestration
- **src/orchestrator/health_monitor.py** - Service health checks
- **src/orchestrator/resource_monitor.py** - System resource monitoring
- **src/orchestrator/checkpoint_manager.py** - State persistence
- **src/orchestrator/recovery_manager.py** - Zombie task recovery

---

## Code Flow: Document Processing Example

### Scenario: Processing a 5MB PDF file

```
1. DISCOVERY STAGE
   ├─ DiscoveryWorker.run()
   │  ├─ Pop folder from queue
   │  ├─ FileScanner.scan_folder(folder)
   │  │  └─ os.scandir() → file metadata
   │  ├─ Check filter_by_extension → ".pdf" allowed
   │  ├─ HashCalculator.calculate_hash("file.pdf")
   │  │  └─ SHA-256 of 5MB file (mmap for large files)
   │  ├─ BloomFilter.contains(file_hash)
   │  │  └─ O(1) check (may have 1% false positives)
   │  ├─ Also check database for exact match
   │  ├─ If UNIQUE:
   │  │  └─ QueueManager.add_discovered_file()
   │  │     ├─ Insert to discovered_files table
   │  │     ├─ Status: PENDING
   │  │     └─ Push to EXTRACTION QUEUE (size=SMALL)
   │  └─ Repeat for next file
   │
   2. EXTRACTION STAGE (Assigned to Standard Track)
   ├─ ExtractionWorker(extraction-std-1).run()
   │  ├─ QueueManager.claim_extraction_work(size_category=SMALL, batch_size=1)
   │  │  ├─ Check extraction_queue where size_category="small"
   │  │  ├─ Mark status: PROCESSING
   │  │  ├─ Return 1 work item
   │  │
   │  ├─ ExtractionWorker._process_file(work_item)
   │  │  ├─ TikaClient.extract("file.pdf")
   │  │  │  ├─ Open file (streaming)
   │  │  │  ├─ HTTP PUT to http://localhost:9997/rmeta/text
   │  │  │  │  └─ Response: JSON with content + metadata
   │  │  │  └─ Retry up to 3 times on failure
   │  │  │
   │  │  ├─ ContentExtractor.process_tika_response(response)
   │  │  │  ├─ Extract main content (text)
   │  │  │  ├─ Extract metadata (author, dates, etc.)
   │  │  │  ├─ Detect embedded files
   │  │  │  ├─ Normalize content (lowercase, remove extra spaces)
   │  │  │  ├─ Calculate content_hash (SHA-256)
   │  │  │  ├─ Check if OCR needed (low text score)
   │  │  │  └─ Return structured document data
   │  │  │
   │  │  ├─ Apply NLP text correction (if enabled)
   │  │  │  ├─ Import from nlp.text_corrector
   │  │  │  ├─ Fix common OCR errors
   │  │  │  └─ (Optional: This PDF doesn't need OCR yet)
   │  │  │
   │  │  └─ QueueManager.mark_extraction_completed(file_id, document_json)
   │  │     ├─ Update status: COMPLETED
   │  │     ├─ Push document_json to INDEXING QUEUE
   │  │     └─ If needs_ocr: also push to OCR QUEUE
   │  │
   │  └─ Loop back for next file (or wait)
   │
   3. INDEXING STAGE (Parallel)
   ├─ IndexingWorker(indexing-1).run()
   │  ├─ QueueManager.claim_indexing_work(worker_id, batch_size=1000)
   │  │  ├─ Check indexing_queue
   │  │  ├─ Accumulate documents until batch_size reached
   │  │  │
   │  │  ├─ DocumentBuilder.build_document(document_json)
   │  │  │  ├─ Parse JSON
   │  │  │  ├─ Truncate long content (prevent 413 errors)
   │  │  │  ├─ Format with metadata, file_name, hashes
   │  │  │  └─ Initialize empty ocr_content, ocr_confidence
   │  │  │
   │  │  ├─ OpenSearchClient.bulk_index(documents)
   │  │  │  ├─ Prepare bulk index request
   │  │  │  ├─ HTTP POST to OpenSearch /_bulk
   │  │  │  ├─ Measure response time
   │  │  │  ├─ If < 2 seconds: increase next batch size
   │  │  │  ├─ If > 30 seconds: decrease next batch size
   │  │  │  └─ Mark documents indexed
   │  │  │
   │  │  └─ QueueManager.mark_indexing_completed(files)
   │  │     └─ Status: COMPLETED (now searchable!)
   │  │
   │  └─ Loop back for next batch
   │
   4. OCR STAGE (Parallel, Non-blocking)
   ├─ OCRWorker(ocr-1).run()
   │  ├─ QueueManager.claim_ocr_work(worker_id, batch_size=10)
   │  │
   │  ├─ OCRWorker._process_document(doc_id, document_json)
   │  │  ├─ Check if needs_ocr (usually false for PDFs with text)
   │  │  │  └─ (Skip OCR for this PDF)
   │  │  │
   │  │  └─ Continue to next
   │  │
   │  └─ Loop back for next document
   │
   5. SEARCH (Available immediately after indexing)
   ├─ SearchAPI GET /search?q=keyword
   │  ├─ QueryBuilder.build_search_query(q="keyword", fields=[...])
   │  │  └─ Construct OpenSearch query DSL
   │  │
   │  ├─ OpenSearchClient.search(query)
   │  │  ├─ HTTP POST to OpenSearch /_search
   │  │  ├─ Return matching documents with scores
   │  │  └─ Add highlighting
   │  │
   │  └─ Return results to user within 100-500ms
```

---

## Key Design Patterns

### 1. Worker Pool Pattern
Multiple worker processes claiming work from queues independently. No coordination needed.

### 2. Micro-Batching
Accumulate work items into small batches for efficiency without delaying results.

### 3. Adaptive Batching
Adjust batch size based on observed performance to optimize throughput.

### 4. Size-Based Routing
Route files to different worker pools based on size for optimal resource utilization.

### 5. Parallel Pipelines
Multiple stages (extraction, indexing, OCR) run in parallel on independent queues.

### 6. Circuit Breaker
OpenSearch client tracks consecutive failures and opens circuit to prevent cascading failures.

### 7. Bloom Filter Deduplication
Fast probabilistic duplicate detection followed by exact database verification.

### 8. Heartbeat Monitoring
Worker processes send periodic status updates for health monitoring and crash detection.

### 9. Graceful Shutdown
Signal handlers allow workers to finish current task before stopping.

### 10. State Checkpointing
System state persisted periodically for crash recovery and resume capability.

---

## Performance Characteristics

### Throughput

| Stage | Throughput | Bottleneck |
|-------|-----------|-----------|
| Discovery | 1,000-2,000 files/sec | Disk I/O |
| Extraction | 245-420 files/sec | Tika processing |
| Indexing | 12,000-20,000 docs/sec | OpenSearch ingest |
| OCR | 5-15 files/sec | Image preprocessing + Tesseract |

### Latency (Time-to-Searchable)

```
Discovery: 0-30 seconds (can start extraction immediately)
Extraction: 2-60 seconds (depending on file size)
Indexing: 0.1-2 seconds (batch processing)
Total: 10-30 seconds average
```

### Resource Usage

```
Memory:
  - OpenSearch: 12 GB heap
  - Tika (7 instances): 2 GB each = 14 GB
  - Workers: ~50-100 MB each (100 workers = 5-10 GB)
  - Total: ~30-40 GB

Disk:
  - SQLite queue DB: ~1-2 GB (for 5M files)
  - OpenSearch indices: ~5-10% of ingested data
  - Temp files: ~100 MB

CPU:
  - Idle: 2-5%
  - Processing: 60-85% (limited by I/O)
  - Peak: 90%+
```

---

## Summary

The Enterprise Document Search System is a **sophisticated distributed document processing platform** designed for high-throughput, reliable processing of massive document collections. Key strengths:

✅ **Scalability** - 150+ workers processing in parallel  
✅ **Reliability** - ACID queues, crash recovery, zombie task detection  
✅ **Performance** - 2-4 hours for 2M documents  
✅ **Flexibility** - Size-based routing, multiple processing backends  
✅ **Observability** - Real-time dashboard, structured logging  
✅ **NLP Integration** - Text correction at extraction and OCR stages  
✅ **Search Accuracy** - Exact matching, no fuzzy/phonetic matching  
✅ **Resumability** - Checkpoint/restore capability  

The codebase is well-organized, documented, and production-ready for enterprise use.

---

**END OF CODEBASE ANALYSIS**
