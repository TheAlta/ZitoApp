from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from src.models import CourseKbDocument, User


def build_user_context(user: User) -> str:
    profile = user.profile
    return (
        f"User ID: {user.id}\n"
        f"Display name: {user.display_name}\n"
        f"Work or study field: {profile.work_or_study_field if profile else 'unknown'}\n"
        f"Education level: {profile.education_level if profile else 'unknown'}\n"
        f"Learning goals: {profile.learning_goal_interests if profile else 'unknown'}\n"
        f"AI familiarity: {profile.ai_familiarity_level if profile else 'unknown'}\n"
        f"Daily learning minutes: {profile.daily_learning_minutes if profile else 'unknown'}\n"
        f"Preferred career path: {profile.preferred_career_path if profile else 'unknown'}"
    )


def retrieve_context(db: Session, course_id: int, query: str, *, limit: int = 3) -> str:
    terms = [term.strip() for term in query.replace(",", " ").split() if len(term.strip()) >= 3]
    if not terms:
        docs = db.scalars(
            select(CourseKbDocument)
            .where(CourseKbDocument.course_id == course_id)
            .order_by(CourseKbDocument.id.desc())
            .limit(limit)
        ).all()
    else:
        filters = []
        for term in terms[:5]:
            pattern = f"%{term}%"
            filters.append(CourseKbDocument.title.ilike(pattern))
            filters.append(CourseKbDocument.content.ilike(pattern))
            filters.append(CourseKbDocument.tags.ilike(pattern))
        docs = db.scalars(
            select(CourseKbDocument)
            .where(CourseKbDocument.course_id == course_id, or_(*filters))
            .limit(limit)
        ).all()

    if not docs:
        return "No internal knowledge base context was found."

    return "\n\n".join(f"[{doc.title}]\n{doc.content[:1600]}" for doc in docs)
