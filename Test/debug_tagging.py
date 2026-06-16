"""Debug taxonomy scoring for a single document to understand category classification."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from tagging.tagging_engine import TaggingEngine, _norm
from tagging.tagging_models import TaggingRequest

engine = TaggingEngine()
snap = engine.taxonomy.get_snapshot()

# Check alias_map for category
print("=== Category Alias Map ===")
for alias, label in sorted(snap.alias_map.get("category", {}).items()):
    print(f"  '{alias}' -> '{label}'")

print(f"\n=== Category Rows ===")
for row in snap.rows_by_field.get("category", []):
    print(f"  {row.label}: aliases={row.aliases[:5]}, keywords={row.keywords[:5]}, priority={row.priority}, active={row.active}")

# Now simulate scoring for budget_operations_019.txt
content = """Budget - Operations Department
Date: 2025-11-11
Author: David Brown
Reference: DOC-0019

1. Executive Summary
This budget outlines the key findings and recommendations for the Operations department.
The analysis covers the period from Q1 to Q4 2025 with total expenditures of $1,250,000.

2. Key Findings
- Revenue increased by 15% year over year to $4,500,000
- Operating costs reduced by 8% through process optimization

3. Financial Summary
Total Budget: $2,000,000.00
Amount Spent: $1,750,000.00
Remaining: $250,000.00
Invoice Number: INV-31318

5. Contact Information
David Brown
Operations Department"""

req = TaggingRequest(
    file_id=0,
    file_path=r"c:\users\hp212560601\downloads\documentsearch_v6\documentsearch_v5\documentsearch\test_documents\budget_operations_019.txt",
    file_name="budget_operations_019.txt",
    file_type="txt",
    main_content=content,
)

result = engine.tag(req)
print(f"\n=== Tagging Result ===")
print(f"  category:    {result.category}")
print(f"  department:  {result.department}")
print(f"  purpose:     {result.purpose}")
print(f"  key_names:   {result.key_names}")
print(f"  amount:      {result.amount_found}")
print(f"  dates:       {result.important_dates}")
print(f"  locations:   {result.location_mentioned}")
print(f"  confidence:  {result.tag_confidence_overall:.3f}")
print(f"  by_field:    {result.tag_confidence_by_field}")
