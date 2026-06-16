"""
Query Builder - Constructs OpenSearch query DSL
ACCURATE SEARCH - No fuzzy/phonetic matching for 100% accuracy
Enhanced with exact numeric/value matching using .keyword subfields
"""

import re
from typing import List, Dict, Any, Optional

from core.config_manager import get_config


class QueryBuilder:
    """
    Builds OpenSearch query DSL for ACCURATE search
    
    Features:
    - Exact phrase matching for quoted queries
    - Exact numeric/formatted value matching (e.g., "2,480,821.04")
    - Boolean operators (AND, OR, NOT)
    - Field-specific boosting
    - NO fuzzy matching (for accuracy)
    - NO phonetic matching (removed)
    - Configurable minimum match threshold
    """
    
    # Pattern to detect numeric values with formatting (commas, decimals, etc.)
    NUMERIC_PATTERN = re.compile(r'^[\d,.\s$€£¥]+$')
    
    def __init__(self):
        self.config = get_config()
        self.mapping = self.config.indexing.mapping
        self.field_boost = self.mapping.get('field_boost', {})
        
        # Default field boosts for relevance ranking
        self.default_boosts = {
            'file_name': 3.0,
            'main_content': 2.0,
            'ocr_content': 1.5,
            'embedded_content': 1.0
        }
    
    def _is_numeric_query(self, query_text: str) -> bool:
        """Detect if query looks like a formatted number or numeric value"""
        clean = query_text.strip().strip('"')
        return bool(self.NUMERIC_PATTERN.match(clean))
    
    def build_search_query(
        self,
        query_text: str,
        fields: List[str],
        page: int = 1,
        size: int = 20,
        exact_match: bool = False,
        minimum_should_match: str = "75%"
    ) -> Dict[str, Any]:
        """
        Build ACCURATE search query - NO fuzzy/phonetic matching
        
        Args:
            query_text: Search query string
            fields: Fields to search
            page: Page number
            size: Results per page
            exact_match: If True, require exact phrase match
            minimum_should_match: Minimum % of terms that must match
            
        Returns:
            OpenSearch query DSL
        """
        # Check if query is quoted (exact phrase) or numeric value
        is_phrase_query = (
            query_text.startswith('"') and query_text.endswith('"')
        ) or exact_match
        
        is_numeric = self._is_numeric_query(query_text)
        
        if is_phrase_query:
            # Exact phrase matching
            clean_query = query_text.strip('"')
            query = self._build_phrase_query(clean_query, fields)
        elif is_numeric:
            # Numeric/formatted value - use exact + analyzed matching
            clean_query = query_text.strip()
            query = self._build_numeric_query(clean_query, fields)
        else:
            # Multi-match with high accuracy settings
            query = self._build_accurate_query(query_text, fields, minimum_should_match)
        
        # Add highlighting
        query["highlight"] = {
            "pre_tags": ["<mark>"],
            "post_tags": ["</mark>"],
            "fields": {
                "main_content": {
                    "fragment_size": 200,
                    "number_of_fragments": 3,
                    "type": "unified"
                },
                "embedded_content": {
                    "fragment_size": 150,
                    "number_of_fragments": 2,
                    "type": "unified"
                },
                "ocr_content": {
                    "fragment_size": 150,
                    "number_of_fragments": 2,
                    "type": "unified"
                },
                "file_name": {
                    "fragment_size": 100,
                    "number_of_fragments": 1,
                    "type": "unified"
                }
            }
        }
        
        return query
    
    def _build_phrase_query(self, query_text: str, fields: List[str]) -> Dict[str, Any]:
        """Build exact phrase match query"""
        should_clauses = []
        
        for field in fields:
            boost = self.field_boost.get(field, self.default_boosts.get(field, 1.0))
            should_clauses.append({
                "match_phrase": {
                    field: {
                        "query": query_text,
                        "boost": boost,
                        "slop": 0  # Exact phrase, no word gaps
                    }
                }
            })
        
        return {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            }
        }
    
    def _build_numeric_query(self, query_text: str, fields: List[str]) -> Dict[str, Any]:
        """
        Build query for numeric/formatted values with exact matching
        Uses .keyword subfield for exact match (high boost) + analyzed field for flexibility
        """
        should_clauses = []
        
        for field in fields:
            base_boost = self.field_boost.get(field, self.default_boosts.get(field, 1.0))
            
            # Exact match on .keyword subfield (if available) - HIGHEST priority
            if field in ['main_content', 'embedded_content', 'ocr_content']:
                should_clauses.append({
                    "match_phrase": {
                        f"{field}.keyword": {
                            "query": query_text,
                            "boost": base_boost * 10.0  # 10x boost for exact match
                        }
                    }
                })
            
            # Also search analyzed field as exact phrase (lower boost)
            should_clauses.append({
                "match_phrase": {
                    field: {
                        "query": query_text,
                        "boost": base_boost,
                        "slop": 0
                    }
                }
            })
        
        return {
            "query": {
                "bool": {
                    "should": should_clauses,
                    "minimum_should_match": 1
                }
            }
        }
    
    def _build_accurate_query(
        self,
        query_text: str,
        fields: List[str],
        minimum_should_match: str = "75%"
    ) -> Dict[str, Any]:
        """
        Build accurate multi-field query WITHOUT fuzzy matching
        """
        # Apply field boosts
        boosted_fields = []
        for field in fields:
            boost = self.field_boost.get(field, self.default_boosts.get(field, 1.0))
            if boost != 1.0:
                boosted_fields.append(f"{field}^{boost}")
            else:
                boosted_fields.append(field)
        
        # Use cross_fields for better multi-word matching across fields
        # NO fuzziness for accuracy
        return {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": boosted_fields,
                                "type": "cross_fields",
                                "operator": "or",
                                "minimum_should_match": minimum_should_match
                                # NO fuzziness - exact word matching only
                            }
                        }
                    ],
                    "should": [
                        # Boost exact phrase matches
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": boosted_fields,
                                "type": "phrase",
                                "boost": 2.0
                            }
                        }
                    ]
                }
            }
        }
    
    def build_filter_query(
        self,
        query_text: str,
        filters: Dict[str, Any],
        fields: List[str],
        page: int = 1,
        size: int = 20
    ) -> Dict[str, Any]:
        """Build query with filters - ACCURATE matching"""
        # Apply field boosts
        boosted_fields = []
        for field in fields:
            boost = self.field_boost.get(field, self.default_boosts.get(field, 1.0))
            if boost != 1.0:
                boosted_fields.append(f"{field}^{boost}")
            else:
                boosted_fields.append(field)
        
        must_clauses = [
            {
                "multi_match": {
                    "query": query_text,
                    "fields": boosted_fields,
                    "type": "cross_fields",
                    "operator": "or",
                    "minimum_should_match": "75%"
                    # NO fuzziness for accuracy
                }
            }
        ]
        
        filter_clauses = []
        
        # Add filters
        for field, value in filters.items():
            if isinstance(value, list):
                filter_clauses.append({"terms": {field: value}})
            else:
                filter_clauses.append({"term": {field: value}})
        
        query = {
            "query": {
                "bool": {
                    "must": must_clauses,
                    "filter": filter_clauses
                }
            },
            "highlight": {
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"],
                "fields": {
                    "main_content": {"fragment_size": 200, "number_of_fragments": 3},
                    "embedded_content": {"fragment_size": 150, "number_of_fragments": 2},
                    "ocr_content": {"fragment_size": 150, "number_of_fragments": 2}
                }
            }
        }
        
        return query
