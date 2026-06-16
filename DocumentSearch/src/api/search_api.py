"""
Search API - FastAPI REST endpoints
"""

from fastapi import FastAPI, HTTPException, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List
import os
import secrets

from core.logging_manager import get_logger
from core.config_manager import get_config
from core.queue_manager import get_queue_manager
from indexing.opensearch_client import OpenSearchClient
from .query_builder import QueryBuilder

logger = get_logger("api")

# Initialize app
app = FastAPI(
    title="Enterprise Document Search API",
    description="Search API for enterprise document indexing system",
    version="1.0.0"
)

# Initialize components
config = get_config()
api_config = config.api
os_client = OpenSearchClient()
query_builder = QueryBuilder()
queue_manager = get_queue_manager()

# CORS configuration
if api_config.cors_enabled:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Authentication
def verify_token(authorization: Optional[str] = Header(None)):
    """Verify API token"""
    if not api_config.require_auth:
        return True
    
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    
    token = authorization.replace("Bearer ", "")
    expected_token = os.getenv("API_TOKEN")
    
    # Use constant-time comparison to prevent timing attacks
    if not expected_token or not secrets.compare_digest(token, expected_token):
        raise HTTPException(status_code=403, detail="Invalid token")
    
    return True


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "name": "Enterprise Document Search API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/search")
def search(
    q: str = Query(..., description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Results per page"),
    fields: Optional[List[str]] = Query(None, description="Fields to search"),
    authenticated: bool = Depends(verify_token)
):
    """
    Search documents
    
    Args:
        q: Search query
        page: Page number (1-indexed)
        size: Results per page
        fields: Fields to search (default: all)
    """
    try:
        # Build query
        if not fields:
            fields = api_config.search['default_fields']
        
        query = query_builder.build_search_query(
            query_text=q,
            fields=fields,
            page=page,
            size=size
        )
        
        # Execute search
        from_offset = (page - 1) * size
        
        response = os_client.client.search(
            index=os_client.index_name,
            body=query,
            from_=from_offset,
            size=size
        )
        
        # Format response
        hits = response['hits']
        results = {
            'total': hits['total']['value'],
            'page': page,
            'size': size,
            'results': [
                {
                    'id': hit['_id'],
                    'score': hit['_score'],
                    'document': hit['_source'],
                    'highlights': hit.get('highlight', {})
                }
                for hit in hits['hits']
            ]
        }
        
        return results
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/document/{doc_id}")
def get_document(
    doc_id: str,
    authenticated: bool = Depends(verify_token)
):
    """Get a specific document by ID"""
    try:
        response = os_client.client.get(
            index=os_client.index_name,
            id=doc_id
        )
        
        return {
            'id': response['_id'],
            'document': response['_source']
        }
        
    except Exception as e:
        logger.error(f"Error fetching document {doc_id}: {e}")
        raise HTTPException(status_code=404, detail="Document not found")


@app.get("/status")
def get_status():
    """Get system status"""
    try:
        queue_stats = queue_manager.get_queue_stats()
        
        # Calculate progress using correct keys from get_queue_stats()
        # Keys are: 'discovery', 'extraction', 'indexing', 'ocr' 
        # with sub-keys as status values: 'pending', 'processing', 'completed', 'failed'
        discovery = queue_stats.get('discovery', {})
        total_discovered = sum(discovery.values()) if discovery else 0
        completed = discovery.get('completed', 0)
        failed = discovery.get('failed', 0)
        
        progress = 0
        if total_discovered > 0:
            progress = ((completed + failed) / total_discovered) * 100
        
        return {
            'status': 'running',
            'progress_percent': round(progress, 2),
            'total_discovered': total_discovered,
            'completed': completed,
            'failed': failed,
            'queues': {
                'extraction_pending': queue_stats.get('extraction', {}).get('pending', 0),
                'indexing_pending': queue_stats.get('indexing', {}).get('pending', 0),
                'ocr_pending': queue_stats.get('ocr', {}).get('pending', 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
def get_metrics(authenticated: bool = Depends(verify_token)):
    """Get detailed system metrics"""
    try:
        queue_stats = queue_manager.get_queue_stats()
        
        return {
            'queues': queue_stats,
            'opensearch': os_client.get_stats()
        }
        
    except Exception as e:
        logger.error(f"Metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=api_config.host,
        port=api_config.port,
        workers=api_config.workers
    )
