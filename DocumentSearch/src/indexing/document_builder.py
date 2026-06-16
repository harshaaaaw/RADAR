"""
Document Builder - Constructs OpenSearch documents from extraction data
"""

import json
from typing import Dict, Any
from datetime import datetime
from pathlib import Path

from core.logging_manager import get_logger
from core.config_manager import get_config

logger = get_logger("indexing.builder")

# Maximum content lengths to prevent HTTP 413 errors
MAX_MAIN_CONTENT_CHARS = 500_000  # 500K chars (~500KB)
MAX_EMBEDDED_CONTENT_CHARS = 200_000  # 200K chars (~200KB)
MAX_OCR_CONTENT_CHARS = 200_000  # 200K chars (~200KB)


class DocumentBuilder:
    """Builds OpenSearch documents from extracted content"""
    
    def __init__(self):
        """Initialize document builder with config"""
        try:
            self.config = get_config()
            # Use config value if available, otherwise use defaults
            self.max_text_length = getattr(self.config.tika, 'max_text_length', MAX_MAIN_CONTENT_CHARS)
        except Exception:
            self.max_text_length = MAX_MAIN_CONTENT_CHARS
    
    def _truncate_content(self, content: str, max_chars: int, field_name: str = "") -> str:
        """Truncate content to max characters, preserving word boundaries"""
        if not content or len(content) <= max_chars:
            return content
        
        # Truncate to max_chars, try to end at word boundary
        truncated = content[:max_chars]
        last_space = truncated.rfind(' ')
        if last_space > max_chars * 0.8:  # Don't go back more than 20%
            truncated = truncated[:last_space]
        
        if field_name:
            logger.warning(f"Truncated {field_name} from {len(content):,} to {len(truncated):,} chars")
        
        return truncated + " [content truncated]"
    
    def build_document(self, document_json: str) -> Dict[str, Any]:
        """
        Build OpenSearch document from extraction data
        
        Args:
            document_json: JSON string from extraction stage
            
        Returns:
            Document ready for OpenSearch indexing
        """
        try:
            # Parse extraction data
            extracted = json.loads(document_json)
            
            # Extract file name from path
            file_path = extracted.get('file_path', '')
            file_name = Path(file_path).name if file_path else ''
            
            embedded_files_raw = extracted.get('embedded_files', [])
            if not isinstance(embedded_files_raw, list):
                logger.warning("Embedded files payload is not a list for %s; defaulting to empty", file_path)
                embedded_files = []
            else:
                embedded_files = embedded_files_raw

            embedded_count = extracted.get('embedded_count')
            if not isinstance(embedded_count, int):
                embedded_count = len(embedded_files)

            # Build base document with content truncation to prevent 413 errors
            main_content = extracted.get('main_content', '')
            main_content = self._truncate_content(main_content, MAX_MAIN_CONTENT_CHARS, f"main_content for {file_path}")
            
            document = {
                'file_path': file_path,
                'file_name': file_name,
                'file_hash': extracted.get('file_hash', ''),
                'content_hash': extracted.get('content_hash', ''),
                'main_content': main_content,
                'metadata': extracted.get('metadata', {}),
                'embedded_files': embedded_files,
                'embedded_count': embedded_count,
                'needs_ocr': extracted.get('needs_ocr', False),
                'ocr_completed': False,
                'indexed_at': datetime.now().isoformat(),
                'extraction_time_ms': extracted.get('extraction_time_ms', 0)
            }
            
            # Add file size if available
            if 'file_size' in extracted:
                document['file_size'] = extracted['file_size']
            
            # Handle embedded content - always set this field
            embedded_content = []
            if document['embedded_files']:
                for embedded in document['embedded_files']:
                    content = embedded.get('content', '')
                    if content:
                        embedded_content.append(content)
            
            # Always set embedded_content field (with truncation)
            raw_embedded = '\n\n'.join(embedded_content) if embedded_content else ''
            document['embedded_content'] = self._truncate_content(raw_embedded, MAX_EMBEDDED_CONTENT_CHARS, f"embedded_content for {file_path}")
            
            # Always set ocr_content field (empty string initially, updated later by OCR worker)
            document['ocr_content'] = ''
            document['ocr_confidence'] = 0.0
            
            return document
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing document JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Error building document: {e}", exc_info=True)
            return None
    
    def build_ocr_update(self, ocr_text: str, confidence: float) -> Dict[str, Any]:
        """
        Build OCR update for existing document
        
        Args:
            ocr_text: Extracted OCR text
            confidence: OCR confidence score
            
        Returns:
            Update dictionary for OpenSearch
        """
        # Truncate OCR content to prevent 413 errors
        truncated_ocr = self._truncate_content(ocr_text, MAX_OCR_CONTENT_CHARS, "ocr_content")
        
        return {
            'ocr_content': truncated_ocr,
            'ocr_confidence': confidence,
            'ocr_completed': True,
            'ocr_updated_at': datetime.now().isoformat()
        }
