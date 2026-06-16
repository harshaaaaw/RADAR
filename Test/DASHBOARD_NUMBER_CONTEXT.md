# Dashboard Number Context

This document maps every dashboard numeric value to its source and formula.

Live validator:
- Command: `python src/tools/validate_dashboard_numbers.py`
- Latest report output path: `runtime/reports/dashboard_validation_*.md`

## Sidebar: Data Progress
| UI Number | Source | Formula |
|---|---|---|
| Total Discovered (files) | Redis `docsearch:counter:discovered` via `get_size_statistics()` | direct |
| Total Discovered (size) | Redis `docsearch:counter:discovered_bytes` via `get_size_statistics()` | direct |
| In Pipeline (files) | Redis queue lengths + processing hashes via `get_size_statistics()` | `extraction_pending + extraction_processing + indexing_pending + indexing_processing + ocr_pending + ocr_processing + tagging_pending + tagging_processing` |
| In Pipeline (size) | `get_size_statistics()` | `max(0, discovered_bytes - completed_bytes)` |
| Searchable root files | Redis `docsearch:counter:root_completed` (fallbacks in `get_size_statistics()`) | direct |
| Searchable items | Redis `docsearch:counter:completed` | direct |
| Searchable size | Redis `docsearch:counter:completed_bytes` | direct |
| Failed files | Redis `HLEN docsearch:failed` | direct |
| Overall Progress (file mode) | sidebar computed | `searchable_root_files / discovered_files * 100` |
| Overall Progress (size mode) | sidebar computed | `searchable_size / discovered_size * 100` |
| Discovery progress bar | `extract_summary(queue_stats)` | `discovery_completed / discovered_total` |
| Extraction progress bar | `extract_summary(queue_stats)` | `extraction_completed / extraction_total` |
| Indexing progress bar | `extract_summary(queue_stats)` | `indexing_completed / indexing_total` |
| OCR progress bar | `extract_summary(queue_stats)` | `ocr_completed / ocr_total` |

## System Monitor: Overall Progress
| UI Number | Source | Formula |
|---|---|---|
| Files Discovered | `summary.discovered_total` | from queue stats discovery total |
| Fully Processed | `summary.completed_total` | from completed stats (`root_completed` authoritative) |
| In Pipeline | summary | sum of extraction/indexing/ocr/tagging pending + processing |
| Failed | `summary.total_failures` | Redis `HLEN docsearch:failed` |
| Overall Progress | monitor computed | `completed_total / max(1, discovered_total - duplicates)` |
| Data Discovered | `size_stats.discovered.size_bytes` | direct |
| Data Indexed | `size_stats.searchable.size_bytes` | direct |
| Data In Pipeline | `size_stats.in_pipeline.size_bytes` | estimated bytes remaining |

## System Monitor: Pipeline Status
| UI Number | Source |
|---|---|
| Extraction Pending/Processing/Done | `summary.extraction_pending`, `summary.extraction_processing`, `summary.extraction_completed` |
| Indexing Pending/Processing/Done | `summary.indexing_pending`, `summary.indexing_processing`, `summary.indexing_completed` |
| OCR Pending/Processing/Done | `summary.ocr_pending`, `summary.ocr_processing`, `summary.ocr_completed` |
| Avg Extract | `completed.avg_extraction_ms` |
| Avg Index | `completed.avg_indexing_ms` |
| Duplicates | `completed.duplicates` |

## System Monitor: ETA
| UI Number | Formula |
|---|---|
| Extraction Remaining | `extraction_pending + extraction_processing` |
| Indexing Remaining | `indexing_pending + indexing_processing` |
| OCR Remaining | `ocr_pending + ocr_processing` |
| Stage ETAs | `(remaining * avg_stage_sec) / worker_count` |
| Est. Time (wall) | `max(extraction_eta, indexing_eta, ocr_eta)` |

## System Monitor: Failure Analysis
| UI Number | Source |
|---|---|
| Failure chart counts | Redis `docsearch:failure_counts` (fallback scans `docsearch:failed`) |
| Total failures | queue stats `total_failures` |
| Failure percentages | `count / total_failures * 100` |

## System Monitor: Queue Status Table
| UI Number | Source |
|---|---|
| Discovery pending/processing/completed/failed/total | `queue_stats.discovery` |
| Extraction by size category | `queue_stats.extraction.{tiny,small,medium,large}` |
| Indexing pending/processing/completed/total | `queue_stats.indexing` |
| OCR pending/processing/completed/total | `queue_stats.ocr` |
| Tagging pending/processing/completed/total | `queue_stats.tagging` |

## Live Audit Tab
| UI Number | Source |
|---|---|
| Rows shown | SQLite `audit.db` table `audit_events`, `LIMIT` from UI |
| Filtered row counts | `search_events(filter_query, limit)` |
| Export row count | SQLite `file_state` rows after filters (`export_state_matrix_xlsx`) |

## Search Tab
| UI Number | Source |
|---|---|
| Recently Indexed Documents count | OpenSearch query result length in dashboard |
| Search result counts | OpenSearch API response |

