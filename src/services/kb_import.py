"""Controlled ingestion of checked-in Markdown into the course KB.

The fake CMS uses this module today. A future CMS can create the same
``CourseKbDocument`` records through its own workflow without changing the
learner retrieval path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models import Course, CourseKbDocument, CourseKbDocumentModule, CourseModule, CourseVersion
from src.services.rag import document_content_checksum, sync_document_chunks


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MOCK_PERSONAL_DEVELOPMENT_KB_REFERENCE = "knowledge_base/personal-development-ai-mock-kb.md"
MOCK_PERSONAL_DEVELOPMENT_KB_PATH = PROJECT_ROOT / MOCK_PERSONAL_DEVELOPMENT_KB_REFERENCE
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_MODULE_HEADER = re.compile(r"^##\s+سرفصل\s+([0-9۰-۹]+)\s*:\s*(.+?)\s*$", re.MULTILINE)


class KnowledgeBaseImportError(ValueError):
    """Raised when a checked-in source cannot be mapped safely to a course."""


@dataclass(frozen=True)
class MarkdownKnowledgeSource:
    title: str
    content: str
    source_reference: str
    source_type: str
    tags: tuple[str, ...]
    module_number: int | None = None


@dataclass
class KnowledgeBaseSyncSummary:
    created: int = 0
    updated: int = 0
    archived: int = 0
    scopes_created: int = 0
    scopes_removed: int = 0
    chunk_changes: int = 0
    documents: list[CourseKbDocument] = field(default_factory=list)


def _normalize_module_number(value: str) -> int:
    try:
        return int(value.translate(_PERSIAN_DIGITS))
    except ValueError as exc:
        raise KnowledgeBaseImportError(f"Invalid module number in Markdown heading: {value!r}") from exc


def _normalized_tags(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in values if isinstance(item, str) and item.strip()))


def load_personal_development_mock_sources(
    *,
    course_title: str,
    modules_by_number: Mapping[int, CourseModule],
) -> list[MarkdownKnowledgeSource]:
    """Parse the fixed mock source and map every section to its known module.

    The parser is intentionally strict: a missing or extra module heading is
    a content-publishing error, rather than a reason to silently index content
    under the wrong learning module.
    """
    try:
        markdown = MOCK_PERSONAL_DEVELOPMENT_KB_PATH.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise KnowledgeBaseImportError(
            f"Could not read mock knowledge-base source: {MOCK_PERSONAL_DEVELOPMENT_KB_REFERENCE}"
        ) from exc

    headings = list(_MODULE_HEADER.finditer(markdown))
    if not headings:
        raise KnowledgeBaseImportError("Mock knowledge-base Markdown has no module headings.")

    seen_numbers: set[int] = set()
    source_sections: dict[int, str] = {}
    for position, heading in enumerate(headings):
        module_number = _normalize_module_number(heading.group(1))
        if module_number in seen_numbers:
            raise KnowledgeBaseImportError(f"Mock knowledge-base repeats module {module_number}.")
        seen_numbers.add(module_number)
        section_end = headings[position + 1].start() if position + 1 < len(headings) else len(markdown)
        source_sections[module_number] = markdown[heading.start():section_end].strip()

    expected_numbers = set(modules_by_number)
    missing_numbers = sorted(expected_numbers - seen_numbers)
    unexpected_numbers = sorted(seen_numbers - expected_numbers)
    if missing_numbers or unexpected_numbers:
        details = []
        if missing_numbers:
            details.append(f"missing module(s): {missing_numbers}")
        if unexpected_numbers:
            details.append(f"unknown module(s): {unexpected_numbers}")
        raise KnowledgeBaseImportError("Mock knowledge-base module map is invalid: " + ", ".join(details))

    sources: list[MarkdownKnowledgeSource] = []
    overview = markdown[:headings[0].start()].strip()
    if overview:
        sources.append(
            MarkdownKnowledgeSource(
                title=f"دانش پایه عمومی دوره: {course_title}",
                content=overview,
                source_reference=f"{MOCK_PERSONAL_DEVELOPMENT_KB_REFERENCE}#course-overview",
                source_type="mock_markdown",
                tags=("phase2", "course_global", "personal-development"),
            )
        )

    for module_number in sorted(source_sections):
        module = modules_by_number[module_number]
        module_tags = module.tags_json if isinstance(module.tags_json, list) else []
        sources.append(
            MarkdownKnowledgeSource(
                title=f"دانش پایه سرفصل: {module.title}",
                content=source_sections[module_number],
                source_reference=f"{MOCK_PERSONAL_DEVELOPMENT_KB_REFERENCE}#module-{module_number}",
                source_type="mock_markdown",
                tags=_normalized_tags(["phase2", "module", *module_tags]),
                module_number=module_number,
            )
        )
    return sources


def _update_document(
    document: CourseKbDocument,
    *,
    course: Course,
    course_version: CourseVersion,
    source: MarkdownKnowledgeSource,
) -> bool:
    values = {
        "course_id": course.id,
        "course_version_id": course_version.id,
        "title": source.title,
        "content": source.content,
        "content_checksum": document_content_checksum(source.content),
        "tags": ",".join(source.tags),
        "source_type": source.source_type,
        "source_reference": source.source_reference,
        "status": "approved",
    }
    changed = False
    for field_name, value in values.items():
        if getattr(document, field_name) != value:
            setattr(document, field_name, value)
            changed = True
    return changed


def _sync_document_scope(
    db: Session,
    *,
    document: CourseKbDocument,
    course_version: CourseVersion,
    desired_module: CourseModule | None,
) -> tuple[int, int]:
    scopes = list(
        db.scalars(
            select(CourseKbDocumentModule).where(CourseKbDocumentModule.document_id == document.id)
        ).all()
    )
    desired_module_id = desired_module.id if desired_module else None
    found_desired_scope = False
    removed = 0
    for scope in scopes:
        if desired_module_id is not None and scope.course_module_id == desired_module_id:
            scope.course_version_id = course_version.id
            found_desired_scope = True
            continue
        db.delete(scope)
        removed += 1

    if desired_module_id is None or found_desired_scope:
        return 0, removed

    db.add(
        CourseKbDocumentModule(
            document_id=document.id,
            course_module_id=desired_module_id,
            course_version_id=course_version.id,
        )
    )
    return 1, removed


def sync_personal_development_mock_kb(
    db: Session,
    *,
    course: Course,
    course_version: CourseVersion,
    modules_by_number: Mapping[int, CourseModule],
) -> KnowledgeBaseSyncSummary:
    """Upsert the approved mock Markdown KB and queue only necessary reindexing."""
    if course.id is None or course_version.id is None:
        raise KnowledgeBaseImportError("Course and course version must be saved before syncing knowledge-base content.")
    if any(module.id is None for module in modules_by_number.values()):
        raise KnowledgeBaseImportError("All course modules must be saved before syncing knowledge-base content.")

    sources = load_personal_development_mock_sources(
        course_title=course.title,
        modules_by_number=modules_by_number,
    )
    summary = KnowledgeBaseSyncSummary()
    existing_documents = list(
        db.scalars(
            select(CourseKbDocument).where(CourseKbDocument.course_version_id == course_version.id)
        ).all()
    )
    existing_by_reference = {
        document.source_reference: document
        for document in existing_documents
        if document.source_reference
    }
    existing_seed_by_title = {
        document.title: document
        for document in existing_documents
        if document.source_type in {"seed", "mock_markdown"}
    }
    desired_references = {source.source_reference for source in sources}

    for source in sources:
        document = existing_by_reference.get(source.source_reference)
        if document is None:
            document = existing_seed_by_title.get(source.title)
        if document is None:
            document = CourseKbDocument(
                course_id=course.id,
                course_version_id=course_version.id,
                title=source.title,
                content=source.content,
                content_checksum=document_content_checksum(source.content),
                tags=",".join(source.tags),
                source_type=source.source_type,
                source_reference=source.source_reference,
                status="approved",
            )
            db.add(document)
            db.flush()
            summary.created += 1
        elif _update_document(
            document,
            course=course,
            course_version=course_version,
            source=source,
        ):
            summary.updated += 1

        desired_module = modules_by_number.get(source.module_number) if source.module_number else None
        scopes_created, scopes_removed = _sync_document_scope(
            db,
            document=document,
            course_version=course_version,
            desired_module=desired_module,
        )
        summary.scopes_created += scopes_created
        summary.scopes_removed += scopes_removed
        summary.documents.append(document)

    source_prefix = f"{MOCK_PERSONAL_DEVELOPMENT_KB_REFERENCE}#"
    for document in existing_documents:
        if (
            document.source_type == "mock_markdown"
            and document.source_reference
            and document.source_reference.startswith(source_prefix)
            and document.source_reference not in desired_references
            and document.status != "archived"
        ):
            document.status = "archived"
            summary.archived += 1

    db.flush()
    summary.chunk_changes = sync_document_chunks(db, summary.documents)
    return summary
