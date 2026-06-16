# Codebase Issues Audit

Generated: 2026-02-10T13:37:05.573919

## Resolution Status (Updated)

- All confirmed functional/logical bugs listed in this audit were fixed in code.
- Critical static errors (`F821`, `F811`, `E9`) for `src/` now pass:
  - Command run: `python -m ruff check src --select F821,F811,E9`
  - Result: `All checks passed!`
- Syntax validation now passes:
  - Command run: `compileall` on `src/` and repo root
  - Result: success

## Scope

- Repository-wide Python review (excluding `.venv/` and `__pycache__/`).
- Manual validation of core runtime paths (`src/`) plus static checks.
- This is a best-effort exhaustive audit of identified defects, logical errors, and bug risks.

## Confirmed Functional/Logical Bugs

- `Critical` `src/ocr/ocr_worker.py:646`
  Issue: `len(images)` is referenced after `del images`; this raises at runtime and sends `_process_pdf_file` into exception path, causing PDF OCR failures.
  Suggested fix: Track total pages in a separate counter and log that value instead of `len(images)` after deletion.
- `Critical` `src/ocr/ocr_worker.py:325, src/ocr/ocr_worker.py:663, src/ocr/ocr_worker.py:116`
  Issue: Code says OCR update is queued for retry, but no code appends to `self.pending_updates`; `_flush_updates` is effectively dead for retries.
  Suggested fix: Append failed OCR updates to `pending_updates` and define bounded retry policy.
- `Critical` `src/main.py:293`
  Issue: `stop` command POSTs to `/api/shutdown`, but no such route exists in API module.
  Suggested fix: Implement `/api/shutdown` or change CLI to orchestrator IPC/signal path.
- `Critical` `src/main.py:706, src/main.py:709, src/main.py:712 + src/core/redis_queue_manager.py:861 + src/core/queue_manager.py:977`
  Issue: `reset_stale` command calls SQLite-style signature (`table_name`, `timeout`) on active Redis manager (`timeout_minutes` only), causing argument mismatch.
  Suggested fix: Normalize queue manager interface or branch by backend type.
- `High` `src/api/search_api.py:182 + src/core/redis_queue_manager.py:1145-1240`
  Issue: Status endpoint reads `queue_stats['extraction']['pending']`, but Redis stats shape stores pending under `extraction_total.pending`; extraction pending is reported as 0 incorrectly.
  Suggested fix: Read from `extraction_total.pending` in API status response.
- `High` `src/core/config_manager.py:314-315, src/core/config_manager.py:326-327, src/core/config_manager.py:348`
  Issue: Environment loader overwrites config credentials/tokens with `None` when env vars are unset, silently discarding config-file values.
  Suggested fix: Only override when env var is non-empty; otherwise preserve existing config value.
- `High` `src/api/search_api.py:53-56`
  Issue: Auth token verification reads only `os.getenv('API_TOKEN')` instead of config-resolved token object; combined with config overwrite behavior can lock out auth unexpectedly.
  Suggested fix: Use `api_config.api_token` (already loaded by config manager) with secure compare.
- `High` `src/core/redis_queue_manager.py:187 and src/core/redis_queue_manager.py:1596`
  Issue: `reset_database` is defined twice in the same class; the latter silently overrides the former, increasing maintenance risk and hiding behavior changes.
  Suggested fix: Keep a single canonical implementation.
- `High` `src/core/redis_queue_manager.py:213-227`
  Issue: `WATCH` is set on pipeline but `ZRANGE` is executed on `self.client` (different command path), weakening optimistic-lock semantics and allowing racey claims.
  Suggested fix: Use watched pipeline connection for both read and remove in one optimistic transaction.
- `High` `src/core/queue_manager.py:1652-1658`
  Issue: SQLite->Redis sync marks `rows[:synced]` as synced; if failures occur mid-loop, wrong rows can be marked synced while failed rows remain unsynced data-wise.
  Suggested fix: Track actual synced row IDs and update exactly those IDs.
- `High` `src/orchestrator/master_orchestrator.py:64-67`
  Issue: Resume mode loads checkpoint data but never uses it (`checkpoint_data` dead variable), so resume semantics are incomplete.
  Suggested fix: Apply checkpoint restore flow or remove misleading resume branch.
- `Medium` `src/orchestrator/master_orchestrator.py:157-207 and src/orchestrator/master_orchestrator.py:384-426`
  Issue: All extraction workers use `tika_ports[0]`; additional configured ports are ignored, reducing throughput and increasing hotspot failures.
  Suggested fix: Distribute workers across configured ports (round-robin or weighted).
- `Medium` `src/orchestrator/master_orchestrator.py:451-460`
  Issue: `_is_work_complete` ignores discovery/OCR queues, yet log says 'All queues empty'; completion signal can be semantically wrong.
  Suggested fix: Include all active stage queues in completion condition or adjust message.
- `Medium` `src/api/search_api.py:152-154`
  Issue: `get_document` maps every exception to HTTP 404, masking OpenSearch outages/timeouts as 'not found'.
  Suggested fix: Differentiate NotFound vs transport/system errors (404 vs 5xx).
- `Medium` `src/orchestrator.py:109, src/orchestrator.py:844-856`
  Issue: Legacy orchestrator references undefined `queue_stats` and missing `_count_total_pending` implementation path; static analysis shows undefined names.
  Suggested fix: Fix or deprecate/remove legacy orchestrator file to avoid accidental usage.
- `Low` `deep_dive_tests.py:8 and ocr_accuracy_tests.py:11`
  Issue: Invalid escape sequences (`\S`) in docstrings produce SyntaxWarning and may break in future Python versions.
  Suggested fix: Use raw strings or escaped backslashes (`\\`).
- `Low` `generate_test_dataset.py:49`
  Issue: Mutable default argument `base_images=[]` can leak state between calls.
  Suggested fix: Use `None` default and initialize list inside function.

## Critical Static Errors (Ruff F821/F811/E9)

```text
F811 Redefinition of unused `reset_database` from line 187
    --> src\core\redis_queue_manager.py:1596:9
     |
1594 |         return pending
1595 |     
1596 |     def reset_database(self) -> None:
     |         ^^^^^^^^^^^^^^ `reset_database` redefined here
1597 |         """Reset all Redis data (WARNING: deletes everything!)"""
1598 |         try:
     |
    ::: src\core\redis_queue_manager.py:187:9
     |
 185 |         return keys
 186 |     
 187 |     def reset_database(self) -> None:
     |         -------------- previous definition of `reset_database` here
 188 |         """
 189 |         Reset all queues by flushing Redis keys
     |
help: Remove definition: `reset_database`

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:844:27
    |
842 |         total = 0
843 |         # Discovery queue
844 |         if 'discovery' in queue_stats:
    |                           ^^^^^^^^^^^
845 |             total += queue_stats['discovery'].get('pending', 0)
846 |         # Extraction queues
    |

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:845:22
    |
843 |         # Discovery queue
844 |         if 'discovery' in queue_stats:
845 |             total += queue_stats['discovery'].get('pending', 0)
    |                      ^^^^^^^^^^^
846 |         # Extraction queues
847 |         if 'extraction' in queue_stats:
    |

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:847:28
    |
845 |             total += queue_stats['discovery'].get('pending', 0)
846 |         # Extraction queues
847 |         if 'extraction' in queue_stats:
    |                            ^^^^^^^^^^^
848 |             for category_stats in queue_stats['extraction'].values():
849 |                 if isinstance(category_stats, dict):
    |

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:848:35
    |
846 |         # Extraction queues
847 |         if 'extraction' in queue_stats:
848 |             for category_stats in queue_stats['extraction'].values():
    |                                   ^^^^^^^^^^^
849 |                 if isinstance(category_stats, dict):
850 |                     total += category_stats.get('pending', 0)
    |

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:852:26
    |
850 |                     total += category_stats.get('pending', 0)
851 |         # Indexing queue
852 |         if 'indexing' in queue_stats:
    |                          ^^^^^^^^^^^
853 |             total += queue_stats['indexing'].get('pending', 0)
854 |         # OCR queue
    |

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:853:22
    |
851 |         # Indexing queue
852 |         if 'indexing' in queue_stats:
853 |             total += queue_stats['indexing'].get('pending', 0)
    |                      ^^^^^^^^^^^
854 |         # OCR queue
855 |         if 'ocr' in queue_stats:
    |

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:855:21
    |
853 |             total += queue_stats['indexing'].get('pending', 0)
854 |         # OCR queue
855 |         if 'ocr' in queue_stats:
    |                     ^^^^^^^^^^^
856 |             total += queue_stats['ocr'].get('pending', 0)
857 |         return total
    |

F821 Undefined name `queue_stats`
   --> src\orchestrator.py:856:22
    |
854 |         # OCR queue
855 |         if 'ocr' in queue_stats:
856 |             total += queue_stats['ocr'].get('pending', 0)
    |                      ^^^^^^^^^^^
857 |         return total
    |

F811 [*] Redefinition of unused `sys` from line 10
   --> src\orchestrator\master_orchestrator.py:251:16
    |
249 |         """Run discovery worker in separate process"""
250 |         # Fix Python path for multiprocessing workers
251 |         import sys
    |                ^^^ `sys` redefined here
252 |         from pathlib import Path
253 |         src_dir = Path(__file__).parent.parent
    |
   ::: src\orchestrator\master_orchestrator.py:10:8
    |
  8 | from pathlib import Path
  9 | import signal
 10 | import sys
    |        --- previous definition of `sys` here
 11 | import glob
    |
help: Remove definition: `sys`

F811 [*] Redefinition of unused `sys` from line 10
   --> src\orchestrator\master_orchestrator.py:264:16
    |
262 |         """Run extraction worker in separate process"""
263 |         # Fix Python path for multiprocessing workers
264 |         import sys
    |                ^^^ `sys` redefined here
265 |         from pathlib import Path
266 |         src_dir = Path(__file__).parent.parent
    |
   ::: src\orchestrator\master_orchestrator.py:10:8
    |
  8 | from pathlib import Path
  9 | import signal
 10 | import sys
    |        --- previous definition of `sys` here
 11 | import glob
    |
help: Remove definition: `sys`

F811 [*] Redefinition of unused `sys` from line 10
   --> src\orchestrator\master_orchestrator.py:277:16
    |
275 |         """Run indexing worker in separate process"""
276 |         # Fix Python path for multiprocessing workers
277 |         import sys
    |                ^^^ `sys` redefined here
278 |         from pathlib import Path
279 |         src_dir = Path(__file__).parent.parent
    |
   ::: src\orchestrator\master_orchestrator.py:10:8
    |
  8 | from pathlib import Path
  9 | import signal
 10 | import sys
    |        --- previous definition of `sys` here
 11 | import glob
    |
help: Remove definition: `sys`

F811 [*] Redefinition of unused `sys` from line 10
   --> src\orchestrator\master_orchestrator.py:290:16
    |
288 |         """Run OCR worker in separate process"""
289 |         # Fix Python path for multiprocessing workers
290 |         import sys
    |                ^^^ `sys` redefined here
291 |         from pathlib import Path
292 |         src_dir = Path(__file__).parent.parent
    |
   ::: src\orchestrator\master_orchestrator.py:10:8
    |
  8 | from pathlib import Path
  9 | import signal
 10 | import sys
    |        --- previous definition of `sys` here
 11 | import glob
    |
help: Remove definition: `sys`

Found 13 errors.
[*] 4 fixable with the `--fix` option.
```

## Duplicate Definitions Detected

- `src/core/redis_queue_manager.py` `class RedisQueueManager` `reset_database` at lines [187, 1596]
- `src/orchestrator.py` `class MasterOrchestrator` `_restore_from_checkpoint` at lines [820, 859]

## Bare Except / Swallowed Exceptions (Risk Appendix)

- Bare `except:` occurrences in `src/`: 5
- `src/orchestrator/recovery_manager.py:199` bare except
- `src/orchestrator/recovery_manager.py:210` bare except
- `src/orchestrator/recovery_manager.py:215` bare except
- `src/orchestrator.py:487` bare except
- `src/tools/fix_stats.py:103` bare except

- `except Exception` with pass/continue in `src/`: 34
- `src/core/queue_manager.py:1678` except Exception: pass/continue
- `src/core/queue_manager.py:133` except Exception: pass/continue
- `src/discovery/discovery_worker.py:352` except Exception: pass/continue
- `src/extraction/extraction_worker.py:524` except Exception: pass/continue
- `src/extraction/extraction_worker.py:543` except Exception: pass/continue
- `src/extraction/tika_client.py:180` except Exception: pass/continue
- `src/extraction/tika_client.py:216` except Exception: pass/continue
- `src/indexing/document_builder.py:66` except Exception: pass/continue
- `src/indexing/indexing_worker.py:408` except Exception: pass/continue
- `src/main.py:600` except Exception: pass/continue
- `src/main.py:613` except Exception: pass/continue
- `src/main.py:667` except Exception: pass/continue
- `src/ocr/ocr_worker.py:798` except Exception: pass/continue
- `src/ocr/ocr_worker.py:191` except Exception: pass/continue
- `src/ocr/ocr_worker.py:624` except Exception: pass/continue
- `src/ocr/tesseract_wrapper.py:273` except Exception: pass/continue
- `src/ocr/tesseract_wrapper.py:193` except Exception: pass/continue
- `src/ocr/tesseract_wrapper.py:188` except Exception: pass/continue
- `src/orchestrator/health_monitor.py:52` except Exception: pass/continue
- `src/orchestrator/recovery_manager.py:156` except Exception: pass/continue
- `src/orchestrator/recovery_manager.py:134` except Exception: pass/continue
- `src/orchestrator.py:700` except Exception: pass/continue
- `src/orchestrator.py:719` except Exception: pass/continue
- `src/ui/dashboard.py:205` except Exception: pass/continue
- `src/ui/dashboard.py:231` except Exception: pass/continue
- `src/ui/dashboard.py:238` except Exception: pass/continue
- `src/ui/dashboard.py:263` except Exception: pass/continue
- `src/ui/dashboard.py:277` except Exception: pass/continue
- `src/ui/dashboard.py:369` except Exception: pass/continue
- `src/ui/dashboard.py:442` except Exception: pass/continue
- `src/ui/dashboard.py:1945` except Exception: pass/continue
- `src/ui/dashboard.py:1978` except Exception: pass/continue
- `src/ui/dashboard.py:366` except Exception: pass/continue
- `src/ui/dashboard.py:439` except Exception: pass/continue

## Mutable Default Arguments

- `generate_test_dataset.py:49` function `generate_docx_files`
