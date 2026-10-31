# config/ai_clients.py
from django.conf import settings

_embedding_model = None
_qdrant_client = None

def get_embedding_model():
    """
    Lazy-load SentenceTransformer only when first invoked.
    Keeps Django CLI / manage.py commands instantaneous.
    """
    global _embedding_model
    if _embedding_model is None:
        # Import moved inside the function to eliminate startup overhead
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
    return _embedding_model


def get_qdrant_client():
    """
    Lazy-load QdrantClient and register collection/indices only on first query.
    """
    global _qdrant_client
    if _qdrant_client is None:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, PayloadSchemaType

        _qdrant_client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        
        # Verify collection and payload schema once
        existing_collections = [c.name for c in _qdrant_client.get_collections().collections]
        if settings.QDRANT_COLLECTION not in existing_collections:
            _qdrant_client.create_collection(
                collection_name=settings.QDRANT_COLLECTION,
                vectors_config=VectorParams(
                    size=settings.EMBEDDING_DIMENSION,
                    distance=Distance.COSINE
                )
            )
            _qdrant_client.create_payload_index(
                collection_name=settings.QDRANT_COLLECTION,
                field_name="organization_id",
                field_schema=PayloadSchemaType.INTEGER
            )
            _qdrant_client.create_payload_index(
                collection_name=settings.QDRANT_COLLECTION,
                field_name="department_id",
                field_schema=PayloadSchemaType.INTEGER
            )
            _qdrant_client.create_payload_index(
                collection_name=settings.QDRANT_COLLECTION,
                field_name="document_id",
                field_schema=PayloadSchemaType.INTEGER
            )
    return _qdrant_client