import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from src.db import get_db
from src.lib.arvan_client import ArvanAIError
from src.models import Answer, KnowledgeDocument, Question, User, UserProgress
from src.schemas import (
    AdminAnswerUpdate,
    AnswerIn,
    AnswerOut,
    KnowledgeIn,
    KnowledgeOut,
    OnboardingAnswerOut,
    OnboardingStartOut,
    OnboardingStateOut,
    PhoneLoginIn,
    PhoneLoginOut,
    QuestionOut,
    TrainingAnswerIn,
    TrainingLessonOut,
    TrainingMessageIn,
    TrainingQuestionIn,
    UserOut,
)
from src.security import require_admin
from src.seed import seed_questions
from src.services.rag import build_user_context
from src.services.training import answer_training_question, generate_lesson, looks_like_question
from src.services.validation import evaluate_training_answer, validate_initial_answer, validate_training_question

router = APIRouter()


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    if not re.fullmatch(r"09\d{9}", digits):
        raise HTTPException(status_code=422, detail="شماره موبایل را با فرمت درست وارد کن؛ مثلا 09123456789.")
    return digits


def _answer_out(answer: Answer) -> AnswerOut:
    return AnswerOut(
        id=answer.id,
        question_id=answer.question_id,
        question_text=answer.question.text,
        answer_text=answer.answer_text,
        is_valid=answer.is_valid,
        validation_reason=answer.validation_reason,
        validated_at=answer.validated_at,
    )


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        profession=user.profession,
        created_at=user.created_at,
        answers=[_answer_out(answer) for answer in sorted(user.answers, key=lambda item: item.question.sort_order)],
    )


def _next_question(db: Session, user: User) -> Question | None:
    answered_question_ids = {answer.question_id for answer in user.answers if answer.is_valid}
    return db.scalars(
        select(Question)
        .where(Question.is_active.is_(True), Question.id.not_in(answered_question_ids))
        .order_by(Question.sort_order)
        .limit(1)
    ).first()


def _guidance_for(question: Question) -> str:
    if question.key == "identity":
        return "برای این سوال فقط نام و نام خانوادگی واقعی بنویس؛ مثلا: علی رضایی یا مریم احمدی."
    if question.key == "profession":
        return "یکی از مسیرهای آموزشی را واضح انتخاب کن: حسابداری و هوش مصنوعی، روانشناسی و هوش مصنوعی، یا حقوق و هوش مصنوعی."
    return "لطفا یک جواب کوتاه، مرتبط و قابل فهم به همین سوال بنویس."

def _apply_profile_field(user: User, question: Question, answer_text: str) -> None:
    if question.key == "identity":
        user.full_name = answer_text.strip()
    elif question.key == "profession":
        user.profession = answer_text.strip()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.post("/api/auth/phone", response_model=PhoneLoginOut)
def login_with_phone(payload: PhoneLoginIn, db: Session = Depends(get_db)) -> PhoneLoginOut:
    phone = _normalize_phone(payload.phone)
    user = db.scalars(select(User).where(User.username == phone).order_by(User.id.desc()).limit(1)).first()
    if not user:
        user = User(username=phone)
        db.add(user)
        db.commit()
        db.refresh(user)
    return PhoneLoginOut(user_id=user.id, username=phone, redirect_url=f"/chat?user_id={user.id}")


@router.post("/api/onboarding/start", response_model=OnboardingStartOut)
def start_onboarding(db: Session = Depends(get_db)) -> OnboardingStartOut:
    seed_questions(db)
    user = User()
    db.add(user)
    db.commit()
    db.refresh(user)
    question = db.scalars(select(Question).where(Question.is_active.is_(True)).order_by(Question.sort_order).limit(1)).first()
    if not question:
        raise HTTPException(status_code=500, detail="No onboarding questions are configured.")
    return OnboardingStartOut(user_id=user.id, question=QuestionOut.model_validate(question))


@router.get("/api/onboarding/{user_id}/state", response_model=OnboardingStateOut)
def onboarding_state(user_id: int, db: Session = Depends(get_db)) -> OnboardingStateOut:
    seed_questions(db)
    user = db.get(User, user_id, options=[selectinload(User.answers).selectinload(Answer.question)])
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    question = _next_question(db, user)
    return OnboardingStateOut(
        user_id=user.id,
        completed=question is None,
        question=QuestionOut.model_validate(question) if question else None,
    )


@router.post("/api/onboarding/{user_id}/answer", response_model=OnboardingAnswerOut)
async def answer_onboarding(user_id: int, payload: AnswerIn, db: Session = Depends(get_db)) -> OnboardingAnswerOut:
    user = db.get(User, user_id, options=[selectinload(User.answers).selectinload(Answer.question)])
    question = db.get(Question, payload.question_id)
    if not user or not question:
        raise HTTPException(status_code=404, detail="User or question not found.")

    expected = _next_question(db, user)
    if expected and expected.id != question.id:
        raise HTTPException(status_code=409, detail=f"Expected answer for question_id={expected.id}.")

    try:
        validation = await validate_initial_answer(question.text, payload.answer_text, question.id)
    except (ArvanAIError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not validation["valid"]:
        return OnboardingAnswerOut(
            valid=False,
            reason=validation["reason"],
            guidance=_guidance_for(question),
            completed=False,
            next_question=QuestionOut.model_validate(question),
        )

    answer_text = validation.get("normalized_answer") or payload.answer_text.strip()
    answer = Answer(
        user_id=user.id,
        question_id=question.id,
        answer_text=answer_text,
        is_valid=True,
        validation_reason=validation["reason"],
    )
    db.add(answer)
    _apply_profile_field(user, question, answer_text)
    db.commit()

    db.refresh(user)
    user = db.get(User, user_id, options=[selectinload(User.answers).selectinload(Answer.question)])
    next_question = _next_question(db, user)
    return OnboardingAnswerOut(
        valid=True,
        reason=validation["reason"],
        completed=next_question is None,
        next_question=QuestionOut.model_validate(next_question) if next_question else None,
    )


@router.get("/api/admin/users", response_model=list[UserOut], dependencies=[Depends(require_admin)])
def list_users(db: Session = Depends(get_db)) -> list[UserOut]:
    users = db.scalars(select(User).options(selectinload(User.answers).selectinload(Answer.question)).order_by(User.id.desc())).all()
    return [_user_out(user) for user in users]


@router.get("/api/admin/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_admin)])
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserOut:
    user = db.get(User, user_id, options=[selectinload(User.answers).selectinload(Answer.question)])
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_out(user)


@router.put("/api/admin/answers/{answer_id}", response_model=AnswerOut, dependencies=[Depends(require_admin)])
def update_answer(answer_id: int, payload: AdminAnswerUpdate, db: Session = Depends(get_db)) -> AnswerOut:
    answer = db.get(Answer, answer_id, options=[selectinload(Answer.question), selectinload(Answer.user)])
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found.")
    answer.answer_text = payload.answer_text.strip()
    _apply_profile_field(answer.user, answer.question, answer.answer_text)
    db.commit()
    db.refresh(answer)
    return _answer_out(answer)


@router.delete("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    db.delete(user)
    db.commit()
    return {"deleted": True}


@router.post("/api/training/knowledge", response_model=KnowledgeOut, dependencies=[Depends(require_admin)])
def create_knowledge(payload: KnowledgeIn, db: Session = Depends(get_db)) -> KnowledgeOut:
    doc = KnowledgeDocument(title=payload.title, content=payload.content, tags=payload.tags)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return KnowledgeOut(id=doc.id, title=doc.title, content=doc.content, tags=doc.tags)


@router.post("/api/training/{user_id}/lesson", response_model=TrainingLessonOut)
async def create_lesson(user_id: int, db: Session = Depends(get_db)) -> TrainingLessonOut:
    user = db.get(
        User,
        user_id,
        options=[
            selectinload(User.answers).selectinload(Answer.question),
            selectinload(User.progress),
        ],
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.progress:
        user.progress = UserProgress(user_id=user.id, current_step=1, percentage=0)
        db.add(user.progress)
        db.commit()
        db.refresh(user)

    try:
        lesson = await generate_lesson(db, user)
    except (ArvanAIError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user.progress.last_lesson = str(lesson)
    db.commit()
    return TrainingLessonOut(
        title=str(lesson.get("title") or "درس Zito"),
        lesson=str(lesson.get("lesson") or ""),
        key_points=[str(item) for item in lesson.get("key_points", [])],
        exercise=str(lesson.get("exercise") or ""),
        check_question=str(lesson.get("check_question") or ""),
        percentage=user.progress.percentage,
    )


@router.post("/api/training/{user_id}/question")
async def ask_training_question(user_id: int, payload: TrainingQuestionIn, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id, options=[selectinload(User.answers).selectinload(Answer.question)])
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    user_context = build_user_context(user)
    try:
        validation = await validate_training_question(payload.question, user_context)
    except (ArvanAIError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not validation["valid"]:
        return {
            "valid": False,
            "reason": validation["reason"],
            "guidance": "سوالت را واضح تر و مرتبط با مسیر آموزشی یا حرفه ات بپرس.",
        }

    try:
        answer = await answer_training_question(db, user, payload.question)
    except ArvanAIError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"valid": True, "answer": answer}


@router.post("/api/training/{user_id}/answer")
async def submit_training_answer(user_id: int, payload: TrainingAnswerIn, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id, options=[selectinload(User.progress)])
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.progress:
        user.progress = UserProgress(user_id=user.id, current_step=1, percentage=0)
        db.add(user.progress)
        db.commit()
        db.refresh(user)

    try:
        evaluation = await evaluate_training_answer(payload.lesson, payload.check_question, payload.answer_text)
    except (ArvanAIError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if evaluation["passed"]:
        user.progress.current_step += 1
        user.progress.percentage = min(100, user.progress.percentage + 25)
        db.commit()

    return {
        "passed": evaluation["passed"],
        "feedback": evaluation["feedback"],
        "score": evaluation["score"],
        "percentage": user.progress.percentage,
        "current_step": user.progress.current_step,
    }


@router.post("/api/training/{user_id}/message")
async def submit_training_message(user_id: int, payload: TrainingMessageIn, db: Session = Depends(get_db)) -> dict:
    user = db.get(
        User,
        user_id,
        options=[
            selectinload(User.answers).selectinload(Answer.question),
            selectinload(User.progress),
        ],
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.progress:
        user.progress = UserProgress(user_id=user.id, current_step=1, percentage=0)
        db.add(user.progress)
        db.commit()
        db.refresh(user)

    if looks_like_question(payload.message):
        user_context = build_user_context(user)
        try:
            validation = await validate_training_question(payload.message, user_context)
        except (ArvanAIError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        if not validation["valid"]:
            return {
                "kind": "retry",
                "message": "سوالت را کمی روشن تر و مرتبط با حسابداری، روانشناسی یا حقوق در کاربرد هوش مصنوعی بپرس.",
                "percentage": user.progress.percentage,
            }

        try:
            answer = await answer_training_question(db, user, payload.message)
        except ArvanAIError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return {
            "kind": "answer",
            "message": f"{answer}\n\nهر وقت آماده بودی، جواب تمرین همین درس را بنویس.",
            "percentage": user.progress.percentage,
        }

    try:
        evaluation = await evaluate_training_answer(payload.lesson, payload.check_question, payload.message)
    except (ArvanAIError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if not evaluation["passed"]:
        return {
            "kind": "retry",
            "message": evaluation["feedback"] or "جوابت را با یک مثال کوتاه و اشاره به محدودیت های هوش مصنوعی کامل تر کن.",
            "percentage": user.progress.percentage,
        }

    user.progress.current_step += 1
    user.progress.percentage = min(100, user.progress.percentage + 25)
    db.commit()
    db.refresh(user)

    if user.progress.percentage >= 100:
        return {
            "kind": "complete",
            "message": "عالیه. این مسیر آموزشی کامل شد و می توانی برای مرور یا سوال های تکمیلی ادامه بدهی.",
            "percentage": user.progress.percentage,
        }

    try:
        next_lesson = await generate_lesson(db, user)
    except (ArvanAIError, ValueError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    user.progress.last_lesson = str(next_lesson)
    db.commit()
    return {
        "kind": "next_lesson",
        "message": "می رویم سراغ مرحله بعد.",
        "lesson": {
            "title": str(next_lesson.get("title") or "درس Zito"),
            "lesson": str(next_lesson.get("lesson") or ""),
            "key_points": [str(item) for item in next_lesson.get("key_points", [])],
            "exercise": str(next_lesson.get("exercise") or ""),
            "check_question": str(next_lesson.get("check_question") or ""),
            "percentage": user.progress.percentage,
        },
        "percentage": user.progress.percentage,
    }

