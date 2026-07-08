from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models import KnowledgeDocument, User


def build_user_context(user: User) -> str:
    answers = "\n".join(
        f"- {answer.question.text}: {answer.answer_text}"
        for answer in sorted(user.answers, key=lambda item: item.question.sort_order)
    )
    return (
        f"User ID: {user.id}\n"
        f"Full name: {user.full_name or 'unknown'}\n"
        f"Username: {user.username or 'unknown'}\n"
        f"Profession: {user.profession or 'unknown'}\n"
        f"Onboarding answers:\n{answers or '- no answers'}"
    )


def retrieve_context(db: Session, query: str, *, limit: int = 3) -> str:
    terms = [term.strip() for term in query.replace(",", " ").split() if len(term.strip()) >= 3]
    if not terms:
        docs = db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.id.desc()).limit(limit)).all()
    else:
        filters = []
        for term in terms[:5]:
            pattern = f"%{term}%"
            filters.append(KnowledgeDocument.title.ilike(pattern))
            filters.append(KnowledgeDocument.content.ilike(pattern))
            filters.append(KnowledgeDocument.tags.ilike(pattern))
        docs = db.scalars(select(KnowledgeDocument).where(or_(*filters)).limit(limit)).all()

    if not docs:
        return "No internal knowledge base context was found."

    return "\n\n".join(f"[{doc.title}]\n{doc.content[:1600]}" for doc in docs)
