# apps/documents/tasks.py
import os
import uuid
from celery import shared_task
from django.db import connection, transaction
from django.conf import settings
from pypdf import PdfReader
from qdrant_client.models import PointStruct

from config.ai_clients import get_embedding_model, get_qdrant_client
from apps.credits.services import CreditService
from .models import Document


@shared_task(bind=True, max_retries=3, default_retry_delay=15)
def process_document_task(self, document_id: int):
    """
    Asynchronous Celery task for document processing:
    1. Acquires an atomic lock and marks the document as PROCESSING (idempotent across SQLite & Postgres).
    2. Extracts text and calculates total pages (PDF or TXT).
    3. Charges the Organization Manager's credit balance for the compute.
    4. Performs sliding-window chunking (500 words with 50-word overlap).
    5. Computes embeddings via the shared SentenceTransformer singleton and indexes into Qdrant.
    6. Updates document status to READY.
    """
    # 1. Acquire atomic row-lock to guarantee idempotency across concurrent workers
    with transaction.atomic():
        try:
            qs = Document.objects.select_related(
                'department__organization__manager', 'uploaded_by'
            )
            # Use nowait=True only if the active backend (PostgreSQL) supports it
            if connection.features.has_select_for_update_nowait:
                doc = qs.select_for_update(nowait=True).get(id=document_id)
            else:
                doc = qs.select_for_update().get(id=document_id)
        except Exception:
            # Another Celery worker already has this document locked or processed
            return

        if doc.status != 'PENDING':
            return  # Already processed or currently processing

        doc.status = 'PROCESSING'
        doc.error_message = None
        doc.save(update_fields=['status', 'error_message'])

    # 2. Extract Text & Calculate Page Count (Heavy compute outside the lock)
    try:
        file_path = doc.file.path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Physical file missing from storage at: {file_path}")

        raw_pages = []
        is_pdf = doc.filename.lower().endswith('.pdf')

        if is_pdf:
            reader = PdfReader(file_path)
            page_count = len(reader.pages)
            for page_idx, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    raw_pages.append((text.strip(), page_idx + 1))
        else:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                raw_pages.append((content, 1))
            page_count = 1

        # 3. Atomically bill the Organization Manager for Ingestion Compute
        org = doc.department.organization
        CreditService.charge_document_ingestion(
            organization=org,
            actor_user=doc.uploaded_by,
            document_id=doc.id,
            filename=doc.filename,
            page_count=page_count
        )

        # 4. Sliding-Window Chunking (500 words with 50-word overlap)
        chunks = []
        global_chunk_idx = 0
        for text, page_num in raw_pages:
            words = text.split()
            step = 450  # 500 - 50 overlap
            for i in range(0, len(words), step):
                chunk_slice = words[i:i + 500]
                chunk_str = " ".join(chunk_slice)
                if len(chunk_str.strip()) > 30:
                    chunks.append({
                        "content": chunk_str,
                        "page": page_num,
                        "chunk_index": global_chunk_idx
                    })
                    global_chunk_idx += 1

        # 5. Generate Embeddings & Upsert to Qdrant using Centralized Singletons
        if chunks:
            model = get_embedding_model()
            vectors = model.encode([c["content"] for c in chunks], batch_size=32).tolist()

            qdrant = get_qdrant_client()
            points = []
            for idx, chunk in enumerate(chunks):
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vectors[idx],
                    payload={
                        "content": chunk["content"],
                        "page": chunk["page"],
                        "chunk_index": chunk["chunk_index"],
                        "filename": doc.filename,
                        "document_id": doc.id,
                        "department_id": doc.department.id,
                        "organization_id": org.id
                    }
                ))

            qdrant.upsert(
                collection_name=settings.QDRANT_COLLECTION,
                points=points,
                wait=True
            )

        # 6. Mark Document as Ready and persist chunk & vector metrics
        with transaction.atomic():
            doc_final = Document.objects.select_for_update().get(id=doc.id)
            doc_final.status = 'READY'
            doc_final.chunk_count = len(chunks)
            doc_final.vector_count = len(chunks)
            doc_final.save(update_fields=['status', 'chunk_count', 'vector_count'])

    except Exception as exc:
        with transaction.atomic():
            Document.objects.filter(id=document_id).update(
                status='FAILED',
                error_message=str(exc)
            )
        raise self.retry(exc=exc)