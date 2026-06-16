"""Debug: show per-candidate scores for specific problem documents."""
import sys, os, warnings
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from tagging.tagging_engine import TaggingEngine, _MAX_RAW_SCORE
from tagging.tagging_models import TaggingRequest

engine = TaggingEngine()

BASE = r"C:\Users\DELL\Downloads\TestDocuments\real_test_docs"

# Problem files
problem_files = [
    "offer_letter_amit_verma.txt",
    "service_agreement_2024.txt",
    "data_protection_policy_v3.txt",
    "board_meeting_minutes_jan2024.txt",
    "employee_id_verification.txt",
]

for filename in problem_files:
    filepath = os.path.join(BASE, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Monkey-patch _score_field to capture detailed scores
    original_score_field = engine._score_field

    def patched_score_field(**kwargs):
        field = kwargs["field"]
        result = original_score_field(**kwargs)

        # Reconstruct candidates from the method
        rows = kwargs["rows"]
        alias_map = kwargs["alias_map"]
        full_text = kwargs["full_text"]
        tokens = kwargs["tokens"]

        # Re-run to get all scores (hacky but works)
        candidates = {}
        for row in rows:
            if not row.active:
                continue
            candidates[row.label] = {"score": 0.0, "reasons": []}

        # Use file_context and spacy_doc from kwargs
        has_spacy = engine._spacy_nlp is not None

        # Just print the winning label and runner-ups
        print(f"  [{field}] Winner: {result.label} (score={result.score:.3f})")
        print(f"           Reasons: {result.reasons}")
        return result

    engine._score_field = patched_score_field
    
    req = TaggingRequest(
        file_id=0, file_path=filepath, file_name=filename, file_hash="test",
        doc_id="test", file_type="txt", mime_type="text/plain", main_content=content,
    )
    
    print(f"\n{'='*70}")
    print(f"FILE: {filename}")
    r = engine.tag(req)
    update = r.to_document_update()
    print(f"  Category: {update['category']}")
    print(f"  Department: {update['department']}")
    print(f"  Purpose: {update['purpose']}")
    print(f"  Confidence: {update['tag_confidence_overall']:.3f}")
    
    engine._score_field = original_score_field  # restore
