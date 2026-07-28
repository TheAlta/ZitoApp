import re

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from src.db import get_db
from src.lib.arvan_client import ArvanAIError
from src.models import (
    Answer,
    Course,
    CourseStageContent,
    CourseVersion,
    KnowledgeDocument,
    Question,
    User,
    UserCourseEnrollment,
    UserProfile,
    UserProgress,
)
from src.schemas import (
    AdminAnswerUpdate,
    AdminLoginIn,
    AdminLoginOut,
    AnswerIn,
    AnswerOut,
    CourseOut,
    EnrollmentOut,
    KnowledgeIn,
    KnowledgeOut,
    OnboardingAnswerOut,
    OnboardingStartOut,
    OnboardingStateOut,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    PhoneLoginOut,
    ProfileOut,
    ProfilePatchIn,
    QuestionOut,
    TrainingAnswerIn,
    TrainingLessonOut,
    TrainingMessageIn,
    TrainingQuestionIn,
    UserMeOut,
    UserOut,
)
from src.security import (
    authenticate_admin,
    clear_admin_cookie,
    clear_user_cookie,
    create_admin_session,
    create_user_session,
    require_admin,
    require_user,
    revoke_current_user_session,
    revoke_user_sessions,
    set_admin_cookie,
    set_user_cookie,
)
from src.seed import seed_questions
from src.services.rag import build_user_context
from src.services.otp import OtpError, OtpRateLimitError, request_otp, verify_otp
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
        phone=user.phone,
        display_name=user.display_name,
        work_or_study_field=user.profile.work_or_study_field if user.profile else None,
        deleted_at=user.deleted_at,
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

def _apply_profile_field(db: Session, user: User, question: Question, answer_text: str) -> None:
    if question.key == "identity":
        user.display_name = answer_text.strip()
    elif question.key == "profession":
        profile = user.profile or UserProfile(user_id=user.id)
        profile.work_or_study_field = answer_text.strip()
        if user.profile is None:
            db.add(profile)


def _get_or_create_phone_user(db: Session, phone: str, display_name: str) -> User:
    now = datetime.now(timezone.utc)
    user = db.scalars(select(User).where(User.phone == phone).limit(1)).first()
    if user:
        if user.deleted_at is not None:
            raise HTTPException(
                status_code=403,
                detail="این حساب غیرفعال شده است. برای بازیابی با پشتیبانی تماس بگیر.",
            )
        user.display_name = display_name
        user.phone_verified_at = now
        user.last_login_at = now
        return user
    user = User(
        phone=phone,
        display_name=display_name,
        phone_verified_at=now,
        last_login_at=now,
    )
    db.add(user)
    db.flush()
    return user


PROFILE_FIELDS = (
    "work_or_study_field",
    "education_level",
    "learning_goal_interests",
    "ai_familiarity_level",
    "daily_learning_minutes",
    "preferred_career_path",
    "referral_source",
)


def _profile_is_complete(profile: UserProfile) -> bool:
    return all(getattr(profile, field) not in (None, "") for field in PROFILE_FIELDS)


def _profile_out(user: User, profile: UserProfile | None) -> ProfileOut:
    if not profile:
        return ProfileOut(user_id=user.id, display_name=user.display_name, completed=False)
    return ProfileOut(
        user_id=user.id,
        display_name=user.display_name,
        completed=_profile_is_complete(profile),
        work_or_study_field=profile.work_or_study_field,
        education_level=profile.education_level,
        learning_goal_interests=profile.learning_goal_interests,
        ai_familiarity_level=profile.ai_familiarity_level,
        daily_learning_minutes=profile.daily_learning_minutes,
        preferred_career_path=profile.preferred_career_path,
        referral_source=profile.referral_source,
        completed_at=profile.completed_at,
    )


def _published_version_for(course: Course) -> CourseVersion | None:
    versions = sorted(course.versions, key=lambda item: item.version_number, reverse=True)
    return next((version for version in versions if version.status == "published"), None)


def _course_out(course: Course) -> CourseOut | None:
    version = _published_version_for(course)
    if not version:
        return None
    return CourseOut(
        id=course.id,
        title=course.title,
        slug=course.slug,
        domain=course.domain,
        version_id=version.id,
        version_number=version.version_number,
        stage_count=len([stage for stage in version.stages if stage.status == "approved"]),
    )


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "ok"}


@router.post("/api/admin/login", response_model=AdminLoginOut)
def admin_login(payload: AdminLoginIn, response: Response, db: Session = Depends(get_db)) -> AdminLoginOut:
    admin = authenticate_admin(db, payload.username.strip(), payload.password)
    if not admin:
        raise HTTPException(status_code=401, detail="نام کاربری یا رمز عبور مدیر درست نیست.")
    set_admin_cookie(response, create_admin_session(admin))
    return AdminLoginOut(username=admin.username)


@router.post("/api/admin/logout")
def admin_logout(response: Response) -> dict:
    clear_admin_cookie(response)
    return {"ok": True}


@router.get("/api/admin/me", dependencies=[Depends(require_admin)])
def admin_me() -> dict:
    return {"ok": True}


@router.post("/api/auth/otp/request", response_model=OtpRequestOut)
async def request_phone_otp(payload: OtpRequestIn, db: Session = Depends(get_db)) -> OtpRequestOut:
    phone = _normalize_phone(payload.phone)
    try:
        result = await request_otp(db, phone)
    except OtpRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "message": str(exc),
                "retry_after_seconds": exc.retry_after_seconds,
            },
        ) from exc
    except OtpError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return OtpRequestOut(
        phone=result.phone,
        expires_in_seconds=result.expires_in_seconds,
        resend_after_seconds=result.resend_after_seconds,
        provider=result.provider,
        mock_code=result.mock_code,
    )


@router.post("/api/auth/otp/verify", response_model=PhoneLoginOut)
def verify_phone_otp(
    payload: OtpVerifyIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> PhoneLoginOut:
    phone = _normalize_phone(payload.phone)
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="یک نام وارد کن.")
    if not verify_otp(db, phone, payload.code):
        raise HTTPException(status_code=401, detail="کد تایید اشتباه است یا منقضی شده.")
    user = _get_or_create_phone_user(db, phone, display_name)
    session_token = create_user_session(db, user, request)
    db.commit()
    db.refresh(user)
    set_user_cookie(response, session_token)
    return PhoneLoginOut(
        user_id=user.id,
        phone=phone,
        display_name=user.display_name,
        redirect_url="/app/",
    )


@router.post("/api/auth/logout")
def user_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    revoke_current_user_session(request, db)
    db.commit()
    clear_user_cookie(response)
    return {"ok": True}


@router.get("/api/me", response_model=UserMeOut)
def get_me(user: User = Depends(require_user)) -> UserMeOut:
    return UserMeOut(id=user.id, phone=user.phone or "", display_name=user.display_name)


@router.get("/api/me/profile", response_model=ProfileOut)
def get_my_profile(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    profile = db.get(UserProfile, user.id)
    return _profile_out(user, profile)


@router.patch("/api/me/profile", response_model=ProfileOut)
def update_my_profile(
    payload: ProfilePatchIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="حداقل یک فیلد پروفایل را ارسال کن.")

    profile = db.get(UserProfile, user.id)
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    for field, value in updates.items():
        normalized = value.strip() if isinstance(value, str) else value
        setattr(profile, field, normalized or None)

    profile.completed_at = datetime.now(timezone.utc) if _profile_is_complete(profile) else None
    db.commit()
    db.refresh(profile)
    return _profile_out(user, profile)


@router.get("/api/profile/{user_id}", response_model=ProfileOut, include_in_schema=False)
def get_profile_compat(
    user_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> ProfileOut:
    if user.id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user profile.")
    return _profile_out(user, db.get(UserProfile, user.id))


@router.get("/api/courses", response_model=list[CourseOut])
def list_published_courses(db: Session = Depends(get_db)) -> list[CourseOut]:
    courses = db.scalars(
        select(Course)
        .where(Course.status == "published")
        .options(
            selectinload(Course.versions).selectinload(CourseVersion.stages),
        )
        .order_by(Course.id)
    ).all()
    output = [_course_out(course) for course in courses]
    return [course for course in output if course]


@router.post("/api/courses/{course_id}/enroll", response_model=EnrollmentOut)
def enroll_course(
    course_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> EnrollmentOut:
    profile = db.get(UserProfile, user.id)
    if not profile or not _profile_is_complete(profile):
        raise HTTPException(status_code=409, detail="Complete your profile before enrollment.")
    course = db.get(
        Course,
        course_id,
        options=[selectinload(Course.versions).selectinload(CourseVersion.stages)],
    )
    if not course or course.status != "published":
        raise HTTPException(status_code=404, detail="Course not found.")

    version = _published_version_for(course)
    if not version:
        raise HTTPException(status_code=409, detail="Course does not have a published version.")

    enrollment = db.scalars(
        select(UserCourseEnrollment).where(
            UserCourseEnrollment.user_id == user.id,
            UserCourseEnrollment.course_version_id == version.id,
        )
    ).first()
    if not enrollment:
        enrollment = UserCourseEnrollment(
            user_id=user.id,
            course_id=course.id,
            course_version_id=version.id,
            status="active",
            current_stage_number=1,
            progress_percentage=0,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)

    return EnrollmentOut(
        id=enrollment.id,
        user_id=enrollment.user_id,
        course_id=enrollment.course_id,
        course_version_id=enrollment.course_version_id,
        status=enrollment.status,
        current_stage_number=enrollment.current_stage_number,
        progress_percentage=enrollment.progress_percentage,
    )


@router.post("/api/onboarding/start", response_model=OnboardingStartOut)
def start_onboarding(db: Session = Depends(get_db)) -> OnboardingStartOut:
    raise HTTPException(status_code=410, detail="Use OTP login and /api/me/profile.")


@router.get("/api/onboarding/{user_id}/state", response_model=OnboardingStateOut)
def onboarding_state(
    user_id: int,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> OnboardingStateOut:
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user.")
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
async def answer_onboarding(
    user_id: int,
    payload: AnswerIn,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> OnboardingAnswerOut:
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user.")
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
    _apply_profile_field(db, user, question, answer_text)
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
def list_users(include_deleted: bool = False, db: Session = Depends(get_db)) -> list[UserOut]:
    query = select(User).options(
        selectinload(User.profile),
        selectinload(User.answers).selectinload(Answer.question),
    )
    if not include_deleted:
        query = query.where(User.deleted_at.is_(None))
    users = db.scalars(query.order_by(User.id.desc())).all()
    return [_user_out(user) for user in users]


@router.get("/api/admin/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_admin)])
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserOut:
    user = db.get(
        User,
        user_id,
        options=[
            selectinload(User.profile),
            selectinload(User.answers).selectinload(Answer.question),
        ],
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_out(user)


@router.put("/api/admin/answers/{answer_id}", response_model=AnswerOut, dependencies=[Depends(require_admin)])
def update_answer(answer_id: int, payload: AdminAnswerUpdate, db: Session = Depends(get_db)) -> AnswerOut:
    answer = db.get(Answer, answer_id, options=[selectinload(Answer.question), selectinload(Answer.user)])
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found.")
    answer.answer_text = payload.answer_text.strip()
    _apply_profile_field(db, answer.user, answer.question, answer.answer_text)
    db.commit()
    db.refresh(answer)
    return _answer_out(answer)


@router.delete("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.deleted_at is None:
        user.deleted_at = datetime.now(timezone.utc)
        revoke_user_sessions(db, user.id)
    db.commit()
    return {"deleted": True, "soft_deleted": True}


@router.post("/api/admin/users/{user_id}/restore", dependencies=[Depends(require_admin)])
def restore_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.deleted_at = None
    db.commit()
    return {"restored": True}


@router.post("/api/training/knowledge", response_model=KnowledgeOut, dependencies=[Depends(require_admin)])
def create_knowledge(payload: KnowledgeIn, db: Session = Depends(get_db)) -> KnowledgeOut:
    doc = KnowledgeDocument(title=payload.title, content=payload.content, tags=payload.tags)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return KnowledgeOut(id=doc.id, title=doc.title, content=doc.content, tags=doc.tags)


@router.post("/api/training/{user_id}/lesson", response_model=TrainingLessonOut)
async def create_lesson(
    user_id: int,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> TrainingLessonOut:
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user.")
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
async def ask_training_question(
    user_id: int,
    payload: TrainingQuestionIn,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user.")
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
async def submit_training_answer(
    user_id: int,
    payload: TrainingAnswerIn,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user.")
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
async def submit_training_message(
    user_id: int,
    payload: TrainingMessageIn,
    current_user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> dict:
    if current_user.id != user_id:
        raise HTTPException(status_code=403, detail="You cannot access another user.")
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

