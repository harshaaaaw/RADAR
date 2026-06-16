## Metadata Tagging Implementation Checklist

### Feature Checklist

1. Metadata input channels
- [x] CLI metadata input added (`--metadata-file`)
- [x] UI metadata upload/path input added
- [x] Config metadata path support added
- [ ] API metadata input endpoint (optional, not implemented)

2. Input precedence
- [x] Source priority implemented: CLI > UI > API > Config
- [x] Active source lock prevents lower-priority override unless forced

3. Dynamic mode behavior
- [x] Metadata mode activates when valid metadata file exists
- [x] SpaCy-only mode activates when metadata file is absent
- [x] Mode/source status exposed via metadata manager status API

4. Tagging policy
- [x] Metadata explicit tag used first (with taxonomy canonicalization)
- [x] Metadata-derived tag used second
- [x] Content/spaCy model used when metadata missing/unmatched
- [x] Deterministic fallback defaults used as final safety
- [x] Per-field source attribution added in confidence payload

5. Empty/different field handling
- [x] Invalid/non-canonical metadata values drop to model path
- [x] Empty fields end with deterministic default, never blank
- [x] Review-required is retained for low-confidence/fallback paths

6. Strict non-empty export behavior
- [x] Upsert sanitizes core fields before persistence
- [x] Export fills missing columns and empty cells deterministically
- [x] State Matrix required columns validated to non-empty values

7. UX/operational visibility
- [x] Live Audit tab shows metadata mode and active file
- [x] UI supports setting and clearing active metadata source

### Real Validation Executed

1. Command
`/Users/venkataditya/Library/CloudStorage/Box-Box/VGCN/Harsha/RADAR/DocumentSearch/.venv/bin/python validate_metadata_implementation.py`

Result
- PASS Metadata source activation
- PASS Metadata-first tagging
- PASS No-metadata fallback tagging
- PASS Export non-empty guarantee
- Summary: 4/4 passed, exit code 0

2. Command
`/Users/venkataditya/Library/CloudStorage/Box-Box/VGCN/Harsha/RADAR/DocumentSearch/.venv/bin/python src/main.py start --help`

Result
- PASS `--metadata-file` option visible in CLI help

3. Command
`/Users/venkataditya/Library/CloudStorage/Box-Box/VGCN/Harsha/RADAR/DocumentSearch/.venv/bin/python -c "import sys; sys.path.insert(0,'src'); import ui.dashboard as d; print('dashboard_import_ok')"`

Result
- PASS Dashboard import successful after metadata UI changes

### Follow-up Validation Commands

1. Metadata via CLI
`/Users/venkataditya/Library/CloudStorage/Box-Box/VGCN/Harsha/RADAR/DocumentSearch/.venv/bin/python src/main.py start --mode full --metadata-file /absolute/path/to/metadata.xlsx`

2. Metadata via UI
- Open dashboard
- Use Metadata Input section to upload/select workbook
- Confirm active source and mode banner

3. Final export verification
- Generate State Matrix export from dashboard
- Verify required columns contain no blank cells
