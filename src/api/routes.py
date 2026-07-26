import re

from fastapi import APIRouter, Depends, HTTPException, Response
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
    ProfileBuilderAnswer,
    Question,
    User,
    UserCourseEnrollment,
    UserProfileV2,
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
    PhoneLoginIn,
    PhoneLoginOut,
    ProfileV2In,
    ProfileV2Out,
    QuestionOut,
    TrainingAnswerIn,
    TrainingLessonOut,
    TrainingMessageIn,
    TrainingQuestionIn,
    UserOut,
)
from src.security import authenticate_admin, clear_admin_cookie, create_admin_session, require_admin, set_admin_cookie
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


def _get_or_create_phone_user(db: Session, phone: str) -> User:
    user = db.scalars(select(User).where(User.username == phone).order_by(User.id.desc()).limit(1)).first()
    if user:
        return user
    user = User(username=phone)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _profile_out(user_id: int, profile: UserProfileV2 | None) -> ProfileV2Out:
    if not profile:
        return ProfileV2Out(user_id=user_id, completed=False)
    completed = bool(profile.full_name and profile.work_domain and profile.daily_study_minutes)
    return ProfileV2Out(
        user_id=user_id,
        completed=completed,
        full_name=profile.full_name,
        work_domain=profile.work_domain,
        referral_source=profile.referral_source,
        daily_study_minutes=profile.daily_study_minutes,
        learning_goal=profile.learning_goal,
        experience_level=profile.experience_level,
        preferred_learning_style=profile.preferred_learning_style,
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


@router.post("/api/auth/phone", response_model=PhoneLoginOut)
def login_with_phone(payload: PhoneLoginIn, db: Session = Depends(get_db)) -> PhoneLoginOut:
    phone = _normalize_phone(payload.phone)
    user = _get_or_create_phone_user(db, phone)
    return PhoneLoginOut(user_id=user.id, username=phone, redirect_url="/app/")


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
def verify_phone_otp(payload: OtpVerifyIn, db: Session = Depends(get_db)) -> PhoneLoginOut:
    phone = _normalize_phone(payload.phone)
    if not verify_otp(db, phone, payload.code):
        raise HTTPException(status_code=401, detail="کد تایید اشتباه است یا منقضی شده.")
    user = _get_or_create_phone_user(db, phone)
    return PhoneLoginOut(user_id=user.id, username=phone, redirect_url="/app/")


@router.get("/api/profile/{user_id}", response_model=ProfileV2Out)
def get_profile_v2(user_id: int, db: Session = Depends(get_db)) -> ProfileV2Out:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    profile = db.scalars(select(UserProfileV2).where(UserProfileV2.user_id == user.id)).first()
    return _profile_out(user.id, profile)


@router.post("/api/profile/{user_id}", response_model=ProfileV2Out)
def submit_profile_v2(user_id: int, payload: ProfileV2In, db: Session = Depends(get_db)) -> ProfileV2Out:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    profile = db.scalars(select(UserProfileV2).where(UserProfileV2.user_id == user.id)).first()
    if not profile:
        profile = UserProfileV2(user_id=user.id)
        db.add(profile)

    profile.full_name = payload.full_name.strip()
    profile.work_domain = payload.work_domain.strip()
    profile.referral_source = payload.referral_source.strip() if payload.referral_source else None
    profile.daily_study_minutes = payload.daily_study_minutes
    profile.learning_goal = payload.learning_goal.strip() if payload.learning_goal else None
    profile.experience_level = payload.experience_level.strip() if payload.experience_level else None
    profile.preferred_learning_style = (
        payload.preferred_learning_style.strip() if payload.preferred_learning_style else None
    )

    user.full_name = profile.full_name
    user.profession = profile.work_domain

    answers = {
        "full_name": profile.full_name,
        "work_domain": profile.work_domain,
        "referral_source": profile.referral_source,
        "daily_study_minutes": profile.daily_study_minutes,
        "learning_goal": profile.learning_goal,
        "experience_level": profile.experience_level,
        "preferred_learning_style": profile.preferred_learning_style,
    }
    for step_key, value in answers.items():
        current = db.scalars(
            select(ProfileBuilderAnswer).where(
                ProfileBuilderAnswer.user_id == user.id,
                ProfileBuilderAnswer.step_key == step_key,
            )
        ).first()
        answer_json = {"value": value}
        if current:
            current.answer_json = answer_json
        else:
            db.add(ProfileBuilderAnswer(user_id=user.id, step_key=step_key, answer_json=answer_json))

    db.commit()
    db.refresh(profile)
    return _profile_out(user.id, profile)


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
def enroll_course(course_id: int, user_id: int, db: Session = Depends(get_db)) -> EnrollmentOut:
    user = db.get(User, user_id)
    course = db.get(
        Course,
        course_id,
        options=[selectinload(Course.versions).selectinload(CourseVersion.stages)],
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
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

