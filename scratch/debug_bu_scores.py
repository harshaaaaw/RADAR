import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')

from indexing.opensearch_client import OpenSearchClient
from tagging.tagging_engine import _norm, _BU_KEYWORD_MAP

osc = OpenSearchClient()
res = osc.client.search(index=osc.index_name, body={'query': {'term': {'file_name.keyword': 'Engineering_Budget_Proposal_20250605_0444.docx'}}})
src = res['hits']['hits'][0]['_source']

full_text = _norm(' '.join([src['file_name'], src['file_path'], src['main_content']]))
text_lower = full_text.lower()

print(f"Full Text:\n{full_text}\n")
print("Keyword matches:")
print("-" * 50)

bu_scores = {}
for bu, keywords in _BU_KEYWORD_MAP.items():
    score = 0.0
    for kw in keywords:
        if kw.lower() in text_lower:
            specificity_weight = 1.0 + (len(kw.split()) - 1) * 0.5
            score += specificity_weight
            print(f"Matched: {bu} -> '{kw}' (weight {specificity_weight})")
    if score > 0:
        bu_scores[bu] = score

print("-" * 50)
print("Final scores:", bu_scores)
