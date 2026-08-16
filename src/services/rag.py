"""Version-scoped, pgvector-backed retrieval and durable KB indexing.

No learner request creates chunks or embeds course content. Publishing or
changing a document creates an index job; a worker processes that job outside
the request path. A learner question embeds only the question, then PostgreSQL
performs the nearest-neighbor lookup over already indexed course content.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import re

from sqlalchemy import case, exists, or_, select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.lib.arvan_embeddings import ArvanEmbeddingError, cosine_similarity, embed_texts
from src.models import (
    CourseKbDocument,
    CourseKbDocumentChunk,
    CourseKbDocumentModule,
    CourseKbIndexJob,
    CourseRagConfig,
    User,
)


_TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)
_ACTIVE_JOB_STATUSES = {"queued", "running", "retry"}


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: int
    document_title: str
    content: str
    score: float
    scope: str

    def citation(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "title": self.document_title,
            "score": round(self.score, 4),
            "scope": self.scope,
        }


@dataclass(frozen=True)
class RetrievalResult:
    rag_config: CourseRagConfig | None
    method: str
    chunks: list[RetrievedChunk]
    error_message: str | None = None

    @property
    def grounded(self) -> bool:
        return bool(self.chunks)


@dataclass(frozen=True)
class IndexJobOutcome:
    job_id: int
    status: str
    attempt_count: int
    error_message: str | None


def build_user_context(user: User) -> str:
    """Legacy-compatible context builder that deliberately excludes identity secrets."""
    profile = user.profile
    return "\n".join(
        [
            f"Display name: {user.display_name}",
            f"Work or study field: {profile.work_or_study_field if profile else 'unknown'}",
            f"Education level: {profile.education_level if profile else 'unknown'}",
            f"Learning goals: {profile.learning_goal_interests if profile else 'unknown'}",
            f"AI familiarity: {profile.ai_familiarity_level if profile else 'unknown'}",
            f"Daily learning time: {profile.daily_learning_time_text if profile else 'unknown'}",
            f"Preferred career path: {profile.preferred_career_path if profile else 'unknown'}",
        ]
    )


def document_content_checksum(content: str) -> str:
    """Checksum the source text exactly as it is stored for reindex decisions."""
    return hashlib.sha256(content.strip().encode("utf-8")).hexdigest()


def _chunk_checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN_PATTERN.findall(text.lower()) if len(token) >= 2}


def split_document(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    """Split one approved source document into deterministic overlapping chunks."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(len(normalized), start + chunk_size)
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start + chunk_size // 2:
                end = boundary
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)
    return chunks


def ensure_course_rag_config(db: Session, course_version_id: int) -> CourseRagConfig:
    """Create non-secret version routing only during seed/publish/index operations."""
    config = db.scalars(
        select(CourseRagConfig).where(CourseRagConfig.course_version_id == course_version_id)
    ).first()
    if config:
        return config

    settings = get_settings()
    config = CourseRagConfig(
        course_version_id=course_version_id,
        provider="zito_embedding",
        endpoint_config_ref="ARVAN_EMBEDDING_API_BASE_URL",
        embedding_model=settings.arvan_embedding_model,
        embedding_dimensions=settings.arvan_embedding_dimensions,
        status="ready",
    )
    db.add(config)
    db.flush()
    return config


def enqueue_document_index_job(
    db: Session,
    document: CourseKbDocument,
    *,
    force: bool = False,
) -> CourseKbIndexJob:
    """Queue one document safely; only one active job may exist per document."""
    if document.id is None or document.course_version_id is None:
        raise ValueError("A KB document must be persisted and pinned to a course version before indexing.")

    settings = get_settings()
    source_checksum = document.content_checksum or document_content_checksum(document.content)
    document.content_checksum = source_checksum
    existing_jobs = db.scalars(
        select(CourseKbIndexJob)
        .where(CourseKbIndexJob.document_id == document.id)
        .order_by(CourseKbIndexJob.id.desc())
    ).all()

    for job in existing_jobs:
        same_input = (
            job.source_checksum == source_checksum
            and job.embedding_model == settings.arvan_embedding_model
        )
        if same_input and job.status == "succeeded" and not force:
            return job
        if job.status in _ACTIVE_JOB_STATUSES:
            if same_input and not force:
                return job
            job.status = "superseded"
            job.finished_at = datetime.now(timezone.utc)

    job = CourseKbIndexJob(
        course_version_id=document.course_version_id,
        document_id=document.id,
        source_checksum=source_checksum,
        embedding_model=settings.arvan_embedding_model,
        status="queued",
        max_attempts=settings.rag_index_job_max_attempts,
    )
    db.add(job)
    db.flush()
    return job


def sync_document_chunks(
    db: Session,
    documents: list[CourseKbDocument],
    *,
    enqueue_jobs: bool = True,
) -> int:
    """Synchronize chunks and queue work, without making any external API call."""
    settings = get_settings()
    changed = 0
    changed_documents: list[CourseKbDocument] = []

    for document in documents:
        if document.id is None or document.course_version_id is None:
            raise ValueError("KB documents must be saved with a course version before chunking.")

        source_checksum = document_content_checksum(document.content)
        source_changed = document.content_checksum != source_checksum
        document.content_checksum = source_checksum
        expected_chunks = split_document(
            document.content,
            chunk_size=settings.rag_chunk_size_chars,
            overlap=settings.rag_chunk_overlap_chars,
        )
        existing = {
            chunk.chunk_index: chunk
            for chunk in db.scalars(
                select(CourseKbDocumentChunk).where(CourseKbDocumentChunk.document_id == document.id)
            ).all()
        }
        document_changed = source_changed

        for chunk_index, content in enumerate(expected_chunks, start=1):
            checksum = _chunk_checksum(content)
            current = existing.pop(chunk_index, None)
            if (
                current
                and current.content_checksum == checksum
                and current.course_version_id == document.course_version_id
            ):
                continue
            if current:
                current.course_version_id = document.course_version_id
                current.content = content
                current.content_checksum = checksum
                current.embedding = None
                current.embedding_input_checksum = checksum
                current.embedding_model = None
                current.embedding_dimension = None
                current.embedding_status = "pending"
                current.embedding_indexed_at = None
                current.embedding_error = None
            else:
                db.add(
                    CourseKbDocumentChunk(
                        document_id=document.id,
                        course_version_id=document.course_version_id,
                        chunk_index=chunk_index,
                        content=content,
                        content_checksum=checksum,
                        embedding_input_checksum=checksum,
                        embedding_status="pending",
                    )
                )
            changed += 1
            document_changed = True

        for stale in existing.values():
            db.delete(stale)
            changed += 1
            document_changed = True

        if document_changed:
            changed_documents.append(document)

    if changed:
        db.flush()

    if enqueue_jobs:
        for document in changed_documents:
            enqueue_document_index_job(db, document, force=True)
    return changed


def _scoped_document_conditions(*, course_version_id: int, module_id: int):
    """Include current-module docs plus explicit course-global docs, never other modules."""
    current_module_scope = exists(
        select(1).where(
            CourseKbDocumentModule.document_id == CourseKbDocument.id,
            CourseKbDocumentModule.course_version_id == course_version_id,
            CourseKbDocumentModule.course_module_id == module_id,
        )
    )
    has_any_module_scope = exists(
        select(1).where(CourseKbDocumentModule.document_id == CourseKbDocument.id)
    )
    scope_label = case(
        (current_module_scope, "module"),
        else_="course_global",
    ).label("scope")
    return or_(current_module_scope, ~has_any_module_scope), scope_label


async def retrieve_course_chunks(
    db: Session,
    *,
    course_version_id: int,
    module_id: int,
    question: str,
) -> RetrievalResult:
    """Retrieve only already-indexed content; no document work happens here."""
    clean_question = question.strip()
    config = db.scalars(
        select(CourseRagConfig).where(CourseRagConfig.course_version_id == course_version_id)
    ).first()
    if not config:
        return RetrievalResult(rag_config=None, method="not_configured", chunks=[])
    if config.status != "ready":
        return RetrievalResult(rag_config=config, method="disabled", chunks=[])
    if not clean_question:
        return RetrievalResult(rag_config=config, method="empty_question", chunks=[])

    try:
        query_embedding = (await embed_texts([clean_question]))[0]
    except ArvanEmbeddingError as exc:
        return RetrievalResult(
            rag_config=config,
            method="query_embedding_error",
            chunks=[],
            error_message=str(exc)[:1000],
        )

    scope_condition, scope_label = _scoped_document_conditions(
        course_version_id=course_version_id,
        module_id=module_id,
    )
    base_query = (
        select(CourseKbDocumentChunk, CourseKbDocument, scope_label)
        .join(CourseKbDocument, CourseKbDocument.id == CourseKbDocumentChunk.document_id)
        .where(
            CourseKbDocumentChunk.course_version_id == course_version_id,
            CourseKbDocument.course_version_id == course_version_id,
            CourseKbDocument.status == "approved",
            CourseKbDocumentChunk.embedding_status == "indexed",
            CourseKbDocumentChunk.embedding.is_not(None),
            scope_condition,
        )
    )
    settings = get_settings()
    candidates: list[RetrievedChunk] = []

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        distance = CourseKbDocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        rows = db.execute(
            base_query.add_columns(distance)
            .order_by(distance, CourseKbDocumentChunk.id)
            .limit(settings.rag_retrieval_top_k)
        ).all()
        for chunk, document, scope, cosine_distance in rows:
            score = 1.0 - float(cosine_distance)
            if score >= settings.rag_min_similarity:
                candidates.append(
                    RetrievedChunk(
                        chunk_id=chunk.id,
                        document_id=document.id,
                        document_title=document.title,
                        content=chunk.content,
                        score=score,
                        scope=str(scope),
                    )
                )
        method = "pgvector_halfvec_cosine"
    else:
        # SQLite is used only by unit tests; production PostgreSQL never runs
        # a Python similarity loop.
        rows = db.execute(base_query).all()
        scored = []
        for chunk, document, scope in rows:
            embedding = chunk.embedding if isinstance(chunk.embedding, list) else []
            score = cosine_similarity(query_embedding, [float(value) for value in embedding])
            if score >= settings.rag_min_similarity:
                scored.append((score, chunk, document, scope))
        for score, chunk, document, scope in sorted(scored, key=lambda item: item[0], reverse=True)[: settings.rag_retrieval_top_k]:
            candidates.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    content=chunk.content,
                    score=score,
                    scope=str(scope),
                )
            )
        method = "sqlite_test_cosine"

    return RetrievalResult(rag_config=config, method=method, chunks=candidates)


def _job_due_condition(now: datetime):
    return or_(
        CourseKbIndexJob.status == "queued",
        (CourseKbIndexJob.status == "retry")
        & or_(CourseKbIndexJob.next_attempt_at.is_(None), CourseKbIndexJob.next_attempt_at <= now),
    )


def _with_job_lock(db: Session, statement):
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return statement.with_for_update(skip_locked=True)
    return statement


def _mark_job_running(job: CourseKbIndexJob, now: datetime) -> None:
    job.status = "running"
    job.attempt_count += 1
    job.started_at = now
    job.finished_at = None
    job.next_attempt_at = None
    job.error_message = None


def _record_index_job_failure(db: Session, job: CourseKbIndexJob, error_message: str) -> None:
    now = datetime.now(timezone.utc)
    config = ensure_course_rag_config(db, job.course_version_id)
    config.last_error = error_message
    job.error_message = error_message
    if job.attempt_count >= job.max_attempts:
        job.status = "failed"
        job.finished_at = now
        job.next_attempt_at = None
    else:
        job.status = "retry"
        job.next_attempt_at = now + timedelta(seconds=60 * max(1, job.attempt_count))
    db.flush()


def _recover_expired_index_jobs(db: Session, now: datetime) -> None:
    settings = get_settings()
    lease_cutoff = now - timedelta(seconds=settings.rag_index_job_lease_seconds)
    expired = db.scalars(
        _with_job_lock(
            db,
            select(CourseKbIndexJob)
            .where(
                CourseKbIndexJob.status == "running",
                or_(
                    CourseKbIndexJob.started_at.is_(None),
                    CourseKbIndexJob.started_at <= lease_cutoff,
                ),
            )
            .order_by(CourseKbIndexJob.id),
        )
    ).all()
    for job in expired:
        _record_index_job_failure(db, job, "RAG index worker lease expired before completion.")


def claim_next_index_job(db: Session) -> CourseKbIndexJob | None:
    """Atomically lease one due job. The caller commits before any network call."""
    now = datetime.now(timezone.utc)
    _recover_expired_index_jobs(db, now)
    settings = get_settings()
    job = db.scalars(
        _with_job_lock(
            db,
            select(CourseKbIndexJob)
            .where(
                _job_due_condition(now),
                CourseKbIndexJob.attempt_count < CourseKbIndexJob.max_attempts,
            )
            .order_by(CourseKbIndexJob.requested_at, CourseKbIndexJob.id)
            .limit(1),
        )
    ).first()
    if not job:
        return None
    _mark_job_running(job, now)
    job.max_attempts = settings.rag_index_job_max_attempts
    db.flush()
    return job


async def process_index_job(db: Session, job_id: int) -> CourseKbIndexJob:
    """Build chunks and embeddings for a claimed job outside learner requests."""
    job = db.get(CourseKbIndexJob, job_id)
    if not job:
        raise ValueError("KB index job was not found.")
    if job.status in {"queued", "retry"}:
        _mark_job_running(job, datetime.now(timezone.utc))
        db.flush()
    if job.status != "running":
        return job

    document = db.get(CourseKbDocument, job.document_id)
    if not document or document.status != "approved":
        job.status = "superseded"
        job.finished_at = datetime.now(timezone.utc)
        return job

    if document.course_version_id != job.course_version_id or document.content_checksum != job.source_checksum:
        job.status = "superseded"
        job.finished_at = datetime.now(timezone.utc)
        enqueue_document_index_job(db, document, force=True)
        return job

    try:
        sync_document_chunks(db, [document], enqueue_jobs=False)
        chunks = db.scalars(
            select(CourseKbDocumentChunk)
            .where(
                CourseKbDocumentChunk.document_id == document.id,
                CourseKbDocumentChunk.course_version_id == document.course_version_id,
            )
            .order_by(CourseKbDocumentChunk.chunk_index)
        ).all()
        vectors: list[list[float]] = []
        for start in range(0, len(chunks), 32):
            vectors.extend(await embed_texts([chunk.content for chunk in chunks[start:start + 32]]))
        if len(vectors) != len(chunks):
            raise ArvanEmbeddingError("Embedding provider returned an unexpected number of vectors.")

        indexed_at = datetime.now(timezone.utc)
        settings = get_settings()
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector
            chunk.embedding_input_checksum = chunk.content_checksum
            chunk.embedding_model = settings.arvan_embedding_model
            chunk.embedding_dimension = len(vector)
            chunk.embedding_status = "indexed"
            chunk.embedding_indexed_at = indexed_at
            chunk.embedding_error = None

        config = ensure_course_rag_config(db, document.course_version_id)
        config.embedding_model = settings.arvan_embedding_model
        config.embedding_dimensions = settings.arvan_embedding_dimensions
        config.last_indexed_at = indexed_at
        config.last_error = None
        job.status = "succeeded"
        job.finished_at = indexed_at
        job.next_attempt_at = None
        db.flush()
    except ArvanEmbeddingError as exc:
        _record_index_job_failure(db, job, str(exc)[:1000])
    return job


async def run_pending_index_jobs(db: Session, *, limit: int = 10) -> list[CourseKbIndexJob]:
    """Test/local helper; it intentionally never runs from a learner route."""
    processed: list[CourseKbIndexJob] = []
    for _ in range(max(1, limit)):
        job = claim_next_index_job(db)
        if not job:
            break
        processed.append(await process_index_job(db, job.id))
    return processed


def _job_outcome(job: CourseKbIndexJob) -> IndexJobOutcome:
    return IndexJobOutcome(
        job_id=job.id,
        status=job.status,
        attempt_count=job.attempt_count,
        error_message=job.error_message,
    )


async def run_index_worker_once(
    session_factory: Callable[[], Session],
    *,
    limit: int = 10,
) -> list[IndexJobOutcome]:
    """Process a finite batch with a transaction boundary around each network call."""
    outcomes: list[IndexJobOutcome] = []
    for _ in range(max(1, limit)):
        with session_factory() as claim_db:
            claimed = claim_next_index_job(claim_db)
            if not claimed:
                claim_db.commit()
                break
            job_id = claimed.id
            claim_db.commit()

        try:
            with session_factory() as processing_db:
                completed = await process_index_job(processing_db, job_id)
                outcome = _job_outcome(completed)
                processing_db.commit()
                outcomes.append(outcome)
        except Exception as exc:
            with session_factory() as recovery_db:
                job = recovery_db.get(CourseKbIndexJob, job_id)
                if job and job.status == "running":
                    _record_index_job_failure(
                        recovery_db,
                        job,
                        f"Unhandled RAG index worker error: {type(exc).__name__}",
                    )
                    outcome = _job_outcome(job)
                    recovery_db.commit()
                    outcomes.append(outcome)
                    continue
            raise
    return outcomes


async def run_index_worker_forever(
    session_factory: Callable[[], Session],
    *,
    limit: int = 10,
) -> None:
    """Poll the durable queue without sharing a process with FastAPI requests."""
    settings = get_settings()
    while True:
        outcomes = await run_index_worker_once(session_factory, limit=limit)
        if not outcomes:
            await asyncio.sleep(settings.rag_index_worker_poll_seconds)


def format_retrieved_context(chunks: list[RetrievedChunk]) -> str:
    settings = get_settings()
    remaining = settings.rag_context_char_limit
    sections: list[str] = []
    for number, chunk in enumerate(chunks, start=1):
        header = f"[SOURCE {number}: {chunk.document_title}]\n"
        allowed = max(0, remaining - len(header))
        if allowed <= 0:
            break
        content = chunk.content[:allowed]
        sections.append(f"{header}{content}")
        remaining -= len(header) + len(content)
    return "\n\n".join(sections)


def retrieve_context(db: Session, course_id: int, query: str, *, limit: int = 3) -> str:
    """Compatibility helper for inactive legacy callers; it never feeds the live coach."""
    terms = _tokens(query)
    documents = db.scalars(
        select(CourseKbDocument)
        .where(CourseKbDocument.course_id == course_id, CourseKbDocument.status == "approved")
        .order_by(CourseKbDocument.id)
    ).all()
    if not documents:
        return "No internal knowledge base context was found."
    ranked = sorted(
        documents,
        key=lambda item: len(terms & _tokens(f"{item.title} {item.tags or ''} {item.content}")),
        reverse=True,
    )[:limit]
    return "\n\n".join(f"[{document.title}]\n{document.content[:1600]}" for document in ranked)
