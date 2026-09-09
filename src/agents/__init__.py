"""Agent team - router plus specialists answering over indexed docs.

The team reads what the pipeline already built (OpenSearch chunks,
taxonomy tags, audit trail) and never re-implements it. Search and counts
are injected callables so the team runs in tests without services; prod
wiring against OpenSearchClient lands with the API step.
"""
