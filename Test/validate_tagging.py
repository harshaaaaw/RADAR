"""
Validate tagging engine accuracy against realistic test documents.
Run the tagging engine directly on each file, display results, and compare
with expected values. This proves the system works with real content.
"""
import sys, os, json
sys.path.insert(0, "src")

from tagging.tagging_engine import TaggingEngine
from tagging.tagging_models import TaggingRequest

engine = TaggingEngine()
print(f"SpaCy loaded: {engine._spacy_nlp is not None}")
print(f"Taxonomy loaded: {engine.taxonomy is not None}")
print()

BASE = r"C:\Users\DELL\Downloads\TestDocuments\real_test_docs"

# Expected results for validation
expected = {
    "invoice_acme_consulting_2024.txt": {
        "category": "Invoice",
        "department": "Finance",
        "names_should_contain": ["Rajesh Kumar", "Priya Sharma"],
        "amounts_expected": True,
    },
    "offer_letter_amit_verma.txt": {
        "category": "Offer Letter",  # or "Letter"
        "department": "HR",
        "names_should_contain": ["Amit Verma", "Sneha Patel", "Meera Krishnan"],
        "amounts_expected": True,
    },
    "service_agreement_2024.txt": {
        "category": "Contract",  # or "Agreement"
        "department": "Legal",
        "names_should_contain": ["Vikram Rao", "Ananya Desai"],
        "amounts_expected": True,
    },
    "tax_computation_fy2024.txt": {
        "category": "Tax Document",
        "department": "Finance",
        "names_should_contain": ["Rajesh Kumar", "Suresh Iyer"],
        "amounts_expected": True,
    },
    "system_performance_report_q1.txt": {
        "category": "Report",
        "department": "Engineering",
        "names_should_contain": ["Karthik Menon", "Sneha Patel"],
        "amounts_expected": True,
    },
    "data_protection_policy_v3.txt": {
        "category": "Policy",
        "department": "Compliance",
        "names_should_contain": ["Anand Sharma", "Kavitha Nair"],
        "amounts_expected": False,
    },
    "purchase_order_laptops_2024.txt": {
        "category": "Purchase Order",
        "department": "Procurement",  # POs belong to Procurement, not IT
        "names_should_contain": ["Sanjay Gupta", "Neha Chopra"],
        "amounts_expected": True,
    },
    "board_meeting_minutes_jan2024.txt": {
        "category": "Meeting Minutes",
        "department": "Executive",  # Board meeting minutes belong to Executive
        "names_should_contain": ["Arun Nair", "Vikram Rao", "Rajesh Kumar"],
        "amounts_expected": True,
    },
    "security_incident_report_feb2024.txt": {
        "category": "Report",
        "department": "Security",
        "names_should_contain": ["Arjun Reddy", "Prashant Joshi"],
        "amounts_expected": True,
    },
    "employee_id_verification.txt": {
        "category": "Identity Document",
        "department": "HR",
        "names_should_contain": ["Deepa Venkatesh", "Meera Krishnan"],
        "amounts_expected": False,
    },
}

results = []
for filename in sorted(os.listdir(BASE)):
    filepath = os.path.join(BASE, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    req = TaggingRequest(
        file_id=0,
        file_path=filepath,
        file_name=filename,
        file_hash="test",
        doc_id="test",
        file_type="txt",
        mime_type="text/plain",
        main_content=content,
    )
    result = engine.tag(req)
    update = result.to_document_update()

    exp = expected.get(filename, {})
    cat_match = exp.get("category", "").lower() in update["category"].lower() if exp.get("category") else "?"
    dept_match = exp.get("department", "").lower() in update["department"].lower() if exp.get("department") else "?"

    # Check names
    found_names = update.get("key_names", [])
    expected_names = exp.get("names_should_contain", [])
    names_found = sum(1 for n in expected_names if any(n.lower() in fn.lower() for fn in found_names))

    print("=" * 70)
    print(f"FILE: {filename}")
    print(f"  Category: {update['category']:25s} Expected: {exp.get('category', '?'):20s} {'✅' if cat_match else '❌'}")
    print(f"  Department: {update['department']:23s} Expected: {exp.get('department', '?'):20s} {'✅' if dept_match else '❌'}")
    print(f"  Purpose: {update['purpose']}")
    print(f"  Confidence: {update['tag_confidence_overall']:.3f}")
    print(f"  Status: {update['tagging_status']}")
    print(f"  Confidentiality: {update['confidentiality']}")
    print(f"  Key Names: {found_names}")
    print(f"    -> Expected names found: {names_found}/{len(expected_names)}")
    print(f"  Amounts: {update['amount_found']}")
    print(f"  Dates: {update['important_dates']}")
    print(f"  Subtags: {update['dynamic_subtags']}")

    results.append({
        "file": filename,
        "cat_ok": cat_match,
        "dept_ok": dept_match,
        "names_found": names_found,
        "names_expected": len(expected_names),
        "confidence": update["tag_confidence_overall"],
    })

print("\n" + "=" * 70)
print("ACCURACY SUMMARY")
print("=" * 70)
cat_correct = sum(1 for r in results if r["cat_ok"] is True)
dept_correct = sum(1 for r in results if r["dept_ok"] is True)
total_names_found = sum(r["names_found"] for r in results)
total_names_expected = sum(r["names_expected"] for r in results)
avg_conf = sum(r["confidence"] for r in results) / len(results) if results else 0

print(f"Category accuracy:    {cat_correct}/{len(results)} ({cat_correct/len(results)*100:.0f}%)")
print(f"Department accuracy:  {dept_correct}/{len(results)} ({dept_correct/len(results)*100:.0f}%)")
print(f"Names extraction:     {total_names_found}/{total_names_expected} ({total_names_found/max(total_names_expected,1)*100:.0f}%)")
print(f"Average confidence:   {avg_conf:.3f}")
