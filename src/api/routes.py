import re

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from src.db import get_db
from src.models import (
    Certificate,
    CoachMessage,
    Course,
    CourseModule,
    CourseModuleStageContent,
    CourseStageContent,
    CourseVersion,
    Exam,
    ExamAttempt,
    LearningStageTemplate,
    User,
    UserCourseEnrollment,
    UserModuleStageProgress,
    UserProfile,
    UserStageProgress,
)
from src.schemas import (
    AdminLoginIn,
    AdminLoginOut,
    CertificateOut,
    CertificateVerificationOut,
    CoachCitationOut,
    CoachHistoryOut,
    CoachMessageOut,
    CoachQuestionIn,
    CoachReplyOut,
    CoachingCheckpointOut,
    CourseOverviewModuleOut,
    CourseOverviewOut,
    CourseOut,
    EnrollmentOut,
    FinalExamAttemptOut,
    FinalExamResultOut,
    FinalExamStateOut,
    FinalExamSubmitIn,
    LearningPathOut,
    LearningModuleOut,
    LearningStageOut,
    LearningStageSummaryOut,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    PhoneLoginOut,
    ProfileOut,
    ProfilePatchIn,
    PersonalizedStageContentOut,
    StageAssessmentOut,
    StageCompleteIn,
    StageCompleteOut,
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
from src.services.otp import (
    OtpError,
    OtpRateLimitError,
    normalize_otp_code,
    request_otp,
    send_welcome_sms,
    verify_otp,
)
from src.services.coach import answer_course_question, list_coach_messages
from src.services.final_exam import (
    FinalExamAIError,
    FinalExamStateError,
    attempt_number,
    attempt_snapshot_questions,
    grade_final_exam,
    issued_certificate,
    latest_attempt,
    public_questions,
    published_final_exam,
    start_final_exam,
)
from src.services.personalized_stage import generate_personalized_work_example

router = APIRouter()
LEARNING_STAGE_COUNT = 20

_PHONE_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone.translate(_PHONE_DIGIT_TRANSLATION))
    if digits.startswith("0098"):
        digits = "0" + digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    if not re.fullmatch(r"09\d{9}", digits):
        raise HTTPException(status_code=422, detail="شماره موبایل را با فرمت درست وارد کن؛ مثلا 09123456789.")
    return digits


def _user_out(user: User) -> UserOut:
    profile = user.profile
    return UserOut(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        deleted_at=user.deleted_at,
        blocked_at=user.blocked_at,
        created_at=user.created_at,
        work_or_study_field=profile.work_or_study_field if profile else None,
        education_level=profile.education_level if profile else None,
        learning_goal_interests=profile.learning_goal_interests if profile else None,
        ai_familiarity_level=profile.ai_familiarity_level if profile else None,
        daily_learning_time_text=profile.daily_learning_time_text if profile else None,
        daily_learning_minutes=profile.daily_learning_minutes if profile else None,
        preferred_career_path=profile.preferred_career_path if profile else None,
        referral_source=profile.referral_source if profile else None,
        profile_completed=bool(profile and _profile_is_complete(profile)),
    )


def _get_or_create_phone_user(db: Session, phone: str, display_name: str | None) -> User:
    now = datetime.now(timezone.utc)
    user = db.scalars(select(User).where(User.phone == phone).limit(1)).first()
    if user:
        if user.blocked_at is not None:
            raise HTTPException(
                status_code=403,
                detail="این حساب توسط مدیریت مسدود شده است.",
            )
        # A normal admin delete is reversible. A verified phone restores its own identity.
        user.deleted_at = None
        user.phone_verified_at = now
        user.last_login_at = now
        return user
    if not display_name:
        raise HTTPException(status_code=422, detail="برای ساخت حساب یک نام وارد کن.")
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
    "daily_learning_time_text",
    "preferred_career_path",
    "referral_source",
)


def _profile_is_complete(profile: UserProfile) -> bool:
    for field in PROFILE_FIELDS:
        if field == "daily_learning_time_text":
            # Existing profiles may predate the raw-answer column and only have a parsed value.
            if profile.daily_learning_time_text not in (None, "") or profile.daily_learning_minutes is not None:
                continue
            return False
        if getattr(profile, field) in (None, ""):
            return False
    return True


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
        daily_learning_time_text=profile.daily_learning_time_text,
        daily_learning_minutes=profile.daily_learning_minutes,
        preferred_career_path=profile.preferred_career_path,
        referral_source=profile.referral_source,
        completed_at=profile.completed_at,
    )


def _published_version_for(course: Course) -> CourseVersion | None:
    versions = sorted(course.versions, key=lambda item: item.version_number, reverse=True)
    return next((version for version in versions if version.status == "published"), None)


def _module_stage_count(version: CourseVersion) -> int:
    """Older module versions keep their original twenty-stage contract."""

    return version.module_stage_count or LEARNING_STAGE_COUNT


def _course_out(db: Session, course: Course) -> CourseOut | None:
    version = _published_version_for(course)
    if not version:
        return None
    if _uses_module_structure(db, version.id):
        try:
            module_stages = _approved_module_stages(db, version.id)
        except HTTPException:
            return None
        return CourseOut(
            id=course.id,
            title=course.title,
            slug=course.slug,
            domain=course.domain,
            version_id=version.id,
            version_number=version.version_number,
            stage_count=len(module_stages),
            module_count=len({stage.course_module_id for stage in module_stages}),
            module_stage_count=_module_stage_count(version),
            requires_final_exam=version.requires_final_exam,
        )
    approved_stages = sorted(
        (
            stage
            for stage in version.stages
            if stage.status == "approved" and stage.review_status == "approved"
        ),
        key=lambda stage: stage.stage_number,
    )
    if [stage.stage_number for stage in approved_stages] != list(range(1, LEARNING_STAGE_COUNT + 1)):
        return None
    return CourseOut(
        id=course.id,
        title=course.title,
        slug=course.slug,
        domain=course.domain,
        version_id=version.id,
        version_number=version.version_number,
        stage_count=len(approved_stages),
        module_count=0,
        module_stage_count=None,
        requires_final_exam=False,
    )


def _course_overview_out(db: Session, course: Course) -> CourseOverviewOut | None:
    version = _published_version_for(course)
    course_out = _course_out(db, course)
    if not version or not course_out:
        return None

    overview = version.overview_json if isinstance(version.overview_json, dict) else {}
    modules: list[CourseOverviewModuleOut] = []
    if _uses_module_structure(db, version.id):
        stages = _approved_module_stages(db, version.id)
        module_stages: dict[int, list[CourseModuleStageContent]] = {}
        for stage in stages:
            module_stages.setdefault(stage.course_module_id, []).append(stage)
        for module_id, items in module_stages.items():
            module = items[0].course_module
            if not module:
                continue
            modules.append(
                CourseOverviewModuleOut(
                    module_id=module_id,
                    module_number=module.module_number,
                    title=module.title,
                    description=module.description,
                    learning_objectives=list(module.learning_objectives_json or []),
                    stage_count=len(items),
                )
            )

    return CourseOverviewOut(
        id=course_out.id,
        title=course_out.title,
        slug=course_out.slug,
        domain=course_out.domain,
        version_id=course_out.version_id,
        version_number=course_out.version_number,
        stage_count=course_out.stage_count,
        module_count=course_out.module_count,
        module_stage_count=course_out.module_stage_count,
        requires_final_exam=course_out.requires_final_exam,
        summary=str(overview.get("summary") or "معرفی این دوره در حال تکمیل است."),
        description=str(overview.get("description") or "محتوای این دوره به‌صورت مرحله‌ای ارائه می‌شود."),
        estimated_learning_minutes=(
            overview.get("estimated_learning_minutes")
            if isinstance(overview.get("estimated_learning_minutes"), int)
            else None
        ),
        estimated_duration_label=(
            str(overview["estimated_duration_label"])
            if overview.get("estimated_duration_label")
            else None
        ),
        learning_outcomes=[str(item) for item in overview.get("learning_outcomes", []) if str(item).strip()],
        career_outcomes=[str(item) for item in overview.get("career_outcomes", []) if str(item).strip()],
        daily_life_outcomes=[str(item) for item in overview.get("daily_life_outcomes", []) if str(item).strip()],
        final_exam_label=(str(overview["final_exam_label"]) if overview.get("final_exam_label") else None),
        modules=modules,
    )


def _approved_stages(db: Session, course_version_id: int) -> list[CourseStageContent]:
    stages = db.scalars(
        select(CourseStageContent)
        .where(
            CourseStageContent.course_version_id == course_version_id,
            CourseStageContent.status == "approved",
            CourseStageContent.review_status == "approved",
        )
        .order_by(CourseStageContent.stage_number)
    ).all()
    if [stage.stage_number for stage in stages] != list(range(1, LEARNING_STAGE_COUNT + 1)):
        raise HTTPException(
            status_code=409,
            detail="نسخه منتشرشده دوره باید دقیقاً ۲۰ مرحله تاییدشده و پیوسته داشته باشد.",
        )
    return list(stages)


def _uses_module_structure(db: Session, course_version_id: int) -> bool:
    return db.scalar(
        select(CourseModule.id)
        .where(CourseModule.course_version_id == course_version_id)
        .limit(1)
    ) is not None


def _approved_module_stages(db: Session, course_version_id: int) -> list[CourseModuleStageContent]:
    version = db.get(CourseVersion, course_version_id)
    if not version:
        raise HTTPException(status_code=409, detail="نسخه دوره پیدا نشد.")
    expected_stage_count = _module_stage_count(version)
    modules = db.scalars(
        select(CourseModule)
        .where(
            CourseModule.course_version_id == course_version_id,
            CourseModule.status == "approved",
        )
        .order_by(CourseModule.module_number)
    ).all()
    if not modules:
        raise HTTPException(status_code=409, detail="نسخه دوره سرفصل تاییدشده ندارد.")

    stages = db.scalars(
        select(CourseModuleStageContent)
        .join(CourseModuleStageContent.course_module)
        .join(CourseModuleStageContent.template)
        .options(
            selectinload(CourseModuleStageContent.course_module),
            selectinload(CourseModuleStageContent.template),
        )
        .where(
            CourseModule.course_version_id == course_version_id,
            CourseModule.status == "approved",
            CourseModuleStageContent.status == "approved",
            CourseModuleStageContent.review_status == "approved",
            LearningStageTemplate.is_active.is_(True),
        )
        .order_by(CourseModule.module_number, CourseModuleStageContent.stage_number)
    ).all()
    expected_numbers = list(range(1, expected_stage_count + 1))
    if len(stages) != len(modules) * expected_stage_count:
        raise HTTPException(
            status_code=409,
            detail=f"هر سرفصل نسخه منتشرشده باید دقیقاً {expected_stage_count} قالب تاییدشده داشته باشد.",
        )
    for module in modules:
        module_numbers = [
            stage.stage_number
            for stage in stages
            if stage.course_module_id == module.id
        ]
        if module_numbers != expected_numbers:
            raise HTTPException(
                status_code=409,
                detail=f"سرفصل «{module.title}» باید {expected_stage_count} قالب پیوسته و تاییدشده داشته باشد.",
            )
    return list(stages)


def _ensure_module_stage_progress(
    db: Session,
    enrollment: UserCourseEnrollment,
    stages: list[CourseModuleStageContent],
) -> list[UserModuleStageProgress]:
    existing = {
        progress.module_stage_content_id: progress
        for progress in db.scalars(
            select(UserModuleStageProgress)
            .where(UserModuleStageProgress.enrollment_id == enrollment.id)
            .order_by(UserModuleStageProgress.id)
        ).all()
    }
    for ordinal, stage in enumerate(stages, start=1):
        if stage.id in existing:
            continue
        progress = UserModuleStageProgress(
            enrollment_id=enrollment.id,
            module_stage_content_id=stage.id,
            status="available" if ordinal == 1 else "locked",
        )
        db.add(progress)
        existing[stage.id] = progress
    db.flush()
    return [existing[stage.id] for stage in stages]


def _sync_module_enrollment_progress(
    enrollment: UserCourseEnrollment,
    progress_rows: list[UserModuleStageProgress],
    *,
    requires_final_exam: bool,
) -> None:
    total = len(progress_rows)
    completed_count = sum(row.status == "completed" for row in progress_rows)
    enrollment.progress_percentage = round(completed_count * 100 / total) if total else 0
    if total and completed_count == total:
        enrollment.current_stage_number = total
        if requires_final_exam:
            enrollment.status = "awaiting_final_exam"
            enrollment.completed_at = None
        else:
            enrollment.status = "completed"
            enrollment.completed_at = enrollment.completed_at or datetime.now(timezone.utc)
        return

    next_index = next(index for index, row in enumerate(progress_rows, start=1) if row.status != "completed")
    next_row = progress_rows[next_index - 1]
    enrollment.status = "active"
    enrollment.current_stage_number = next_index
    enrollment.completed_at = None
    if next_row.status in ("locked", "not_started"):
        next_row.status = "available"


def _final_exam_state(version: CourseVersion, enrollment: UserCourseEnrollment) -> tuple[bool, bool, str]:
    """Expose the compact lifecycle state used by the learning-path views."""

    if not version.requires_final_exam:
        return False, False, "not_required"
    if enrollment.status == "awaiting_final_exam":
        return True, True, "available"
    if enrollment.status == "completed":
        return True, False, "passed"
    return True, False, "locked"


def _certificate_out(certificate: Certificate) -> CertificateOut:
    if (
        certificate.recipient_name is None
        or certificate.course_title is None
        or certificate.course_version_number is None
        or certificate.score is None
        or certificate.passing_score is None
        or certificate.issued_at is None
    ):
        raise HTTPException(status_code=409, detail="اطلاعات گواهی این دوره ناقص است.")
    return CertificateOut(
        certificate_number=certificate.certificate_number,
        recipient_name=certificate.recipient_name,
        course_title=certificate.course_title,
        course_version_number=certificate.course_version_number,
        score=certificate.score,
        passing_score=certificate.passing_score,
        status=certificate.status,
        issued_at=certificate.issued_at,
    )


def _final_exam_attempt_out(
    db: Session,
    *,
    attempt: ExamAttempt,
    exam: Exam,
) -> FinalExamAttemptOut:
    if attempt.enrollment_id is None or attempt.created_at is None:
        raise HTTPException(status_code=409, detail="تلاش آزمون نهایی ناقص است.")
    metadata = attempt.generation_json if isinstance(attempt.generation_json, dict) else {}
    return FinalExamAttemptOut(
        id=attempt.id,
        enrollment_id=attempt.enrollment_id,
        title=exam.title,
        passing_score=exam.passing_score,
        status=attempt.status,
        attempt_number=attempt_number(db, attempt),
        questions=public_questions(attempt_snapshot_questions(attempt)),
        generation_method=str(metadata.get("method") or "approved_fallback"),
        created_at=attempt.created_at,
        submitted_at=attempt.submitted_at,
    )


def _final_exam_state_out(db: Session, enrollment: UserCourseEnrollment) -> FinalExamStateOut:
    version = db.get(CourseVersion, enrollment.course_version_id)
    if not version or version.course_id != enrollment.course_id:
        raise HTTPException(status_code=409, detail="نسخه دوره با ثبت‌نام کاربر همخوانی ندارد.")
    if not version.requires_final_exam:
        return FinalExamStateOut(enrollment_id=enrollment.id, status="not_required")

    try:
        exam = published_final_exam(db, enrollment)
    except FinalExamStateError as exc:
        if enrollment.status in {"awaiting_final_exam", "completed"}:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return FinalExamStateOut(enrollment_id=enrollment.id, status="locked")

    certificate = issued_certificate(db, enrollment)
    if certificate and certificate.status == "issued":
        return FinalExamStateOut(
            enrollment_id=enrollment.id,
            status="passed",
            title=exam.title,
            passing_score=exam.passing_score,
            certificate=_certificate_out(certificate),
        )

    if enrollment.status == "completed":
        return FinalExamStateOut(
            enrollment_id=enrollment.id,
            status="passed",
            title=exam.title,
            passing_score=exam.passing_score,
        )

    active_attempt = latest_attempt(db, enrollment, exam)
    if enrollment.status == "awaiting_final_exam" and active_attempt and active_attempt.status == "in_progress":
        return FinalExamStateOut(
            enrollment_id=enrollment.id,
            status="in_progress",
            title=exam.title,
            passing_score=exam.passing_score,
            attempt=_final_exam_attempt_out(db, attempt=active_attempt, exam=exam),
        )
    if enrollment.status == "awaiting_final_exam":
        return FinalExamStateOut(
            enrollment_id=enrollment.id,
            status="available",
            title=exam.title,
            passing_score=exam.passing_score,
        )
    return FinalExamStateOut(
        enrollment_id=enrollment.id,
        status="locked",
        title=exam.title,
        passing_score=exam.passing_score,
    )


def _requires_final_exam(db: Session, enrollment: UserCourseEnrollment) -> bool:
    version = db.get(CourseVersion, enrollment.course_version_id)
    if not version or version.course_id != enrollment.course_id:
        raise HTTPException(status_code=409, detail="نسخه دوره با ثبت‌نام کاربر همخوانی ندارد.")
    return bool(version.requires_final_exam)


def _assessment_out(
    stage: CourseModuleStageContent,
    progress: UserModuleStageProgress,
) -> StageAssessmentOut | None:
    config = stage.evaluation_config_json if isinstance(stage.evaluation_config_json, dict) else None
    if not config:
        return None
    result = progress.evaluation_json if isinstance(progress.evaluation_json, dict) else {}
    pass_score = config.get("pass_score")
    return StageAssessmentOut(
        evaluated=progress.evaluated_at is not None,
        score=progress.score,
        passed=result.get("passed") if isinstance(result.get("passed"), bool) else None,
        pass_score=pass_score if isinstance(pass_score, int) else None,
        feedback=str(result["feedback"]) if result.get("feedback") else None,
        attempt_count=int(progress.assessment_attempt_count or 0),
    )


def _evaluate_module_assessment(
    stage: CourseModuleStageContent,
    progress: UserModuleStageProgress,
    payload: StageCompleteIn | None,
) -> StageAssessmentOut:
    """Grade a seeded multiple-choice assessment without exposing private answer keys."""

    config = stage.evaluation_config_json if isinstance(stage.evaluation_config_json, dict) else {}
    questions = config.get("questions") if isinstance(config.get("questions"), list) else []
    pass_score = config.get("pass_score") if isinstance(config.get("pass_score"), int) else 60
    response = payload.response if payload and isinstance(payload.response, dict) else {}
    raw_answers = response.get("answers") if isinstance(response.get("answers"), dict) else {}
    answers = {str(key): str(value).strip() for key, value in raw_answers.items() if isinstance(value, str)}

    total_weight = sum(
        item.get("weight", 0)
        for item in questions
        if isinstance(item, dict) and isinstance(item.get("weight", 0), int)
    )
    earned_weight = 0
    answered_count = 0
    for question in questions:
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("id") or "")
        expected = str(question.get("correct_option") or "").strip()
        weight = question.get("weight", 0)
        if not question_id or not expected or not isinstance(weight, int):
            continue
        answer = answers.get(question_id)
        if answer:
            answered_count += 1
        if answer == expected:
            earned_weight += weight

    score = round(earned_weight * 100 / total_weight) if total_weight else 0
    passed = bool(questions) and answered_count == len(questions) and score >= pass_score
    if not questions:
        feedback = "تنظیمات آزمونک این مرحله کامل نیست؛ فعلا نمی‌توان آن را ارزیابی کرد."
    elif answered_count < len(questions):
        feedback = "برای ثبت نتیجه، به همه سوال‌های آزمونک پاسخ بده."
    elif passed:
        feedback = f"آفرین، با نمره {score} این آزمونک را با موفقیت گذراندی."
    else:
        feedback = f"نمره تو {score} شد. حداقل نمره عبور {pass_score} است؛ پاسخ‌ها را مرور و دوباره تلاش کن."

    progress.response_json = response
    progress.score = score
    progress.evaluation_json = {
        "passed": passed,
        "feedback": feedback,
        "answered_count": answered_count,
        "question_count": len(questions),
    }
    progress.assessment_attempt_count = int(progress.assessment_attempt_count or 0) + 1
    progress.evaluated_at = datetime.now(timezone.utc)
    return _assessment_out(stage, progress) or StageAssessmentOut(
        evaluated=True,
        score=score,
        passed=passed,
        pass_score=pass_score,
        feedback=feedback,
        attempt_count=progress.assessment_attempt_count,
    )


def _module_learning_path_out(
    db: Session,
    enrollment: UserCourseEnrollment,
    stages: list[CourseModuleStageContent],
    progress_rows: list[UserModuleStageProgress],
) -> LearningPathOut:
    course = db.get(Course, enrollment.course_id)
    version = db.get(CourseVersion, enrollment.course_version_id)
    if not course or not version or version.course_id != course.id:
        raise HTTPException(status_code=409, detail="اطلاعات دوره این مسیر آموزشی ناقص است.")

    module_rows: dict[int, dict] = {}
    stage_summaries: list[LearningStageSummaryOut] = []
    completed_count = 0
    for ordinal, (stage, progress) in enumerate(zip(stages, progress_rows), start=1):
        module = stage.course_module
        if not module:
            raise HTTPException(status_code=409, detail="رابطه سرفصل و محتوای آموزشی ناقص است.")
        module_data = module_rows.setdefault(
            module.id,
            {
                "module": module,
                "rows": [],
            },
        )
        module_data["rows"].append(progress)
        if progress.status == "completed":
            completed_count += 1
        stage_summaries.append(
            LearningStageSummaryOut(
                stage_number=ordinal,
                stage_type=stage.template.code,
                title=stage.title,
                status=progress.status,
                is_current=(
                    enrollment.status not in ("completed", "awaiting_final_exam")
                    and ordinal == enrollment.current_stage_number
                ),
                module_id=module.id,
                module_number=module.module_number,
                module_title=module.title,
                module_stage_number=stage.stage_number,
            )
        )

    modules: list[LearningModuleOut] = []
    for module_data in module_rows.values():
        module = module_data["module"]
        rows = module_data["rows"]
        module_completed = sum(row.status == "completed" for row in rows)
        module_current = any(
            summary.module_id == module.id and summary.is_current
            for summary in stage_summaries
        )
        if module_completed == len(rows):
            status = "completed"
        elif module_current:
            status = "active"
        else:
            status = "locked"
        modules.append(
            LearningModuleOut(
                module_id=module.id,
                module_number=module.module_number,
                title=module.title,
                description=module.description,
                status=status,
                is_current=module_current,
                completed_stage_count=module_completed,
                total_stage_count=len(rows),
            )
        )

    final_exam_required, final_exam_available, final_exam_status = _final_exam_state(version, enrollment)
    return LearningPathOut(
        enrollment_id=enrollment.id,
        course_id=course.id,
        course_title=course.title,
        course_slug=course.slug,
        course_domain=course.domain,
        course_version_id=version.id,
        course_version_number=version.version_number,
        status=enrollment.status,
        current_stage_number=enrollment.current_stage_number,
        completed_stage_count=completed_count,
        total_stage_count=len(stages),
        progress_percentage=enrollment.progress_percentage,
        stages=stage_summaries,
        module_count=len(modules),
        modules=modules,
        final_exam_required=final_exam_required,
        final_exam_available=final_exam_available,
        final_exam_status=final_exam_status,
    )


def _module_current_stage_out(
    db: Session,
    enrollment: UserCourseEnrollment,
    stages: list[CourseModuleStageContent],
    progress_rows: list[UserModuleStageProgress],
) -> LearningStageOut:
    terminal = enrollment.status in ("completed", "awaiting_final_exam")
    ordinal = len(stages) if terminal else enrollment.current_stage_number
    if ordinal < 1 or ordinal > len(stages):
        raise HTTPException(status_code=409, detail="مرحله جاری این مسیر آموزشی معتبر نیست.")
    stage = stages[ordinal - 1]
    progress = progress_rows[ordinal - 1]
    module = stage.course_module
    course = db.get(Course, enrollment.course_id)
    version = db.get(CourseVersion, enrollment.course_version_id)
    if not course or not module or not version or version.course_id != course.id:
        raise HTTPException(status_code=409, detail="محتوای سرفصل این مسیر پیدا نشد.")
    content = stage.content_json if isinstance(stage.content_json, dict) else {}
    _, final_exam_available, _ = _final_exam_state(version, enrollment)
    return LearningStageOut(
        enrollment_id=enrollment.id,
        course_id=course.id,
        course_title=course.title,
        stage_number=ordinal,
        stage_type=stage.template.code,
        title=stage.title,
        progress_status=progress.status,
        progress_percentage=enrollment.progress_percentage,
        total_stage_count=len(stages),
        course_completed=enrollment.status == "completed",
        content=content,
        coaching=_coaching_checkpoint(
            content,
            enrollment.status == "completed",
            enabled=True,
            stage_number=ordinal,
        ),
        module_id=module.id,
        module_number=module.module_number,
        module_title=module.title,
        module_stage_number=stage.stage_number,
        module_stage_count=_module_stage_count(version),
        total_module_count=len({item.course_module_id for item in stages}),
        final_exam_available=final_exam_available,
        assessment=_assessment_out(stage, progress),
    )


def _complete_module_learning_stage(
    db: Session,
    enrollment: UserCourseEnrollment,
    stage_number: int,
    payload: StageCompleteIn | None,
) -> StageCompleteOut:
    stages = _approved_module_stages(db, enrollment.course_version_id)
    version = db.get(CourseVersion, enrollment.course_version_id)
    if not version:
        raise HTTPException(status_code=409, detail="نسخه دوره پیدا نشد.")
    if stage_number < 1 or stage_number > len(stages):
        raise HTTPException(status_code=404, detail="مرحله آموزشی پیدا نشد.")
    progress_rows = _ensure_module_stage_progress(db, enrollment, stages)
    _sync_module_enrollment_progress(
        enrollment,
        progress_rows,
        requires_final_exam=version.requires_final_exam,
    )
    stage = stages[stage_number - 1]
    progress = progress_rows[stage_number - 1]

    if progress.status != "completed" and stage_number != enrollment.current_stage_number:
        raise HTTPException(
            status_code=409,
            detail=f"ابتدا مرحله {enrollment.current_stage_number} را کامل کن.",
        )

    assessment = _assessment_out(stage, progress)
    if progress.status != "completed":
        if stage.template.code == "module_assessment":
            assessment = _evaluate_module_assessment(stage, progress, payload)
            if not assessment.passed:
                _sync_module_enrollment_progress(
                    enrollment,
                    progress_rows,
                    requires_final_exam=version.requires_final_exam,
                )
                db.commit()
                db.refresh(enrollment)
                path = _module_learning_path_out(db, enrollment, stages, progress_rows)
                content = stage.content_json if isinstance(stage.content_json, dict) else {}
                return StageCompleteOut(
                    enrollment_id=enrollment.id,
                    completed_stage_number=stage_number,
                    next_stage_number=enrollment.current_stage_number,
                    course_completed=False,
                    progress_percentage=enrollment.progress_percentage,
                    coaching=_coaching_checkpoint(content, enabled=True, stage_number=stage_number),
                    path=path,
                    stage_completed=False,
                    assessment=assessment,
                )
        progress.status = "completed"
        progress.completed_at = datetime.now(timezone.utc)
        if payload and payload.response is not None:
            progress.response_json = payload.response
        if stage_number < len(progress_rows):
            next_progress = progress_rows[stage_number]
            if next_progress.status in ("locked", "not_started"):
                next_progress.status = "available"
        _sync_module_enrollment_progress(
            enrollment,
            progress_rows,
            requires_final_exam=version.requires_final_exam,
        )
        db.commit()
        db.refresh(enrollment)

    path = _module_learning_path_out(db, enrollment, stages, progress_rows)
    course_completed = enrollment.status == "completed"
    learning_complete = enrollment.status in ("completed", "awaiting_final_exam")
    content = stage.content_json if isinstance(stage.content_json, dict) else {}
    return StageCompleteOut(
        enrollment_id=enrollment.id,
        completed_stage_number=stage_number,
        next_stage_number=None if learning_complete else enrollment.current_stage_number,
        course_completed=course_completed,
        progress_percentage=enrollment.progress_percentage,
        coaching=_coaching_checkpoint(
            content,
            course_completed,
            enabled=True,
            stage_number=stage_number,
        ),
        path=path,
        stage_completed=True,
        assessment=assessment,
    )


def _validate_enrollment_version(db: Session, enrollment: UserCourseEnrollment) -> None:
    version = db.get(CourseVersion, enrollment.course_version_id)
    if not version or version.course_id != enrollment.course_id:
        raise HTTPException(status_code=409, detail="نسخه دوره با ثبت‌نام کاربر همخوانی ندارد.")


def _owned_enrollment(
    db: Session,
    enrollment_id: int,
    user_id: int,
    *,
    for_update: bool = False,
) -> UserCourseEnrollment:
    statement = select(UserCourseEnrollment).where(
        UserCourseEnrollment.id == enrollment_id,
        UserCourseEnrollment.user_id == user_id,
    )
    if for_update:
        statement = statement.with_for_update()
    enrollment = db.scalars(statement).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="مسیر آموزشی پیدا نشد.")
    _validate_enrollment_version(db, enrollment)
    return enrollment


def _current_enrollment(db: Session, user_id: int) -> UserCourseEnrollment:
    enrollment = db.scalars(
        select(UserCourseEnrollment)
        .where(
            UserCourseEnrollment.user_id == user_id,
            UserCourseEnrollment.status.in_(("active", "awaiting_final_exam", "completed")),
        )
        .order_by(UserCourseEnrollment.updated_at.desc(), UserCourseEnrollment.id.desc())
        .limit(1)
    ).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="هنوز دوره‌ای انتخاب نکرده‌ای.")
    _validate_enrollment_version(db, enrollment)
    return enrollment


def _ensure_stage_progress(
    db: Session,
    enrollment: UserCourseEnrollment,
    stages: list[CourseStageContent],
) -> list[UserStageProgress]:
    progress_by_number = {
        progress.stage_number: progress
        for progress in db.scalars(
            select(UserStageProgress)
            .where(UserStageProgress.enrollment_id == enrollment.id)
            .order_by(UserStageProgress.stage_number)
        ).all()
    }
    legacy_completed_through = (
        LEARNING_STAGE_COUNT
        if enrollment.status == "completed"
        else max(0, min(enrollment.current_stage_number - 1, LEARNING_STAGE_COUNT))
    )
    for stage in stages:
        if stage.stage_number in progress_by_number:
            continue
        if stage.stage_number <= legacy_completed_through:
            status = "completed"
        elif stage.stage_number == legacy_completed_through + 1:
            status = "available"
        else:
            status = "locked"
        progress = UserStageProgress(
            enrollment_id=enrollment.id,
            stage_number=stage.stage_number,
            status=status,
            completed_at=enrollment.updated_at if status == "completed" else None,
        )
        db.add(progress)
        progress_by_number[stage.stage_number] = progress
    db.flush()
    return [progress_by_number[stage.stage_number] for stage in stages]


def _sync_enrollment_progress(
    enrollment: UserCourseEnrollment,
    progress_rows: list[UserStageProgress],
) -> None:
    completed_count = len([row for row in progress_rows if row.status == "completed"])
    enrollment.progress_percentage = round(completed_count * 100 / LEARNING_STAGE_COUNT)
    if completed_count == LEARNING_STAGE_COUNT:
        enrollment.status = "completed"
        enrollment.current_stage_number = LEARNING_STAGE_COUNT
        enrollment.completed_at = enrollment.completed_at or datetime.now(timezone.utc)
        return

    next_row = next(row for row in progress_rows if row.status != "completed")
    enrollment.status = "active"
    enrollment.current_stage_number = next_row.stage_number
    enrollment.completed_at = None
    if next_row.status in ("locked", "not_started"):
        next_row.status = "available"


def _learning_path_out(
    db: Session,
    enrollment: UserCourseEnrollment,
    stages: list[CourseStageContent],
    progress_rows: list[UserStageProgress],
) -> LearningPathOut:
    course = db.get(Course, enrollment.course_id)
    version = db.get(CourseVersion, enrollment.course_version_id)
    if not course or not version:
        raise HTTPException(status_code=409, detail="اطلاعات دوره این ثبت‌نام ناقص است.")
    if version.course_id != course.id:
        raise HTTPException(status_code=409, detail="نسخه دوره با ثبت‌نام کاربر همخوانی ندارد.")
    progress_by_number = {row.stage_number: row for row in progress_rows}
    completed_count = len([row for row in progress_rows if row.status == "completed"])
    return LearningPathOut(
        enrollment_id=enrollment.id,
        course_id=course.id,
        course_title=course.title,
        course_slug=course.slug,
        course_domain=course.domain,
        course_version_id=version.id,
        course_version_number=version.version_number,
        status=enrollment.status,
        current_stage_number=enrollment.current_stage_number,
        completed_stage_count=completed_count,
        total_stage_count=LEARNING_STAGE_COUNT,
        progress_percentage=enrollment.progress_percentage,
        stages=[
            LearningStageSummaryOut(
                stage_number=stage.stage_number,
                stage_type=stage.stage_type,
                title=stage.title,
                status=progress_by_number[stage.stage_number].status,
                is_current=(
                    enrollment.status != "completed"
                    and stage.stage_number == enrollment.current_stage_number
                ),
            )
            for stage in stages
        ],
    )


def _coaching_checkpoint(
    content: dict,
    course_completed: bool = False,
    *,
    enabled: bool = False,
    stage_number: int | None = None,
) -> CoachingCheckpointOut:
    checkpoint = content.get("coaching_checkpoint") if isinstance(content, dict) else None
    prompt = "مسیر را کامل کردی؛ درباره جمع‌بندی سوالی داری؟" if course_completed else "درباره این مرحله سوالی داری؟"
    if isinstance(checkpoint, dict) and checkpoint.get("prompt"):
        prompt = str(checkpoint["prompt"])
    return CoachingCheckpointOut(
        prompt=prompt,
        enabled=enabled,
        mode="live" if enabled else "preview",
        stage_number=stage_number,
    )


def _resolve_coaching_stage(
    db: Session,
    enrollment: UserCourseEnrollment,
    requested_stage_number: int | None,
) -> tuple[CourseModuleStageContent, list[CourseModuleStageContent]]:
    """Map a user-visible stage number to the user's pinned module content.

    The client cannot select a course, course version, module, or KB. It may
    ask about the current stage or a stage it has already reached.
    """
    if not _uses_module_structure(db, enrollment.course_version_id):
        raise HTTPException(
            status_code=409,
            detail="کوچینگ هوشمند فقط برای نسخه جدید دوره فعال است.",
        )
    stages = _approved_module_stages(db, enrollment.course_version_id)
    max_stage_number = (
        len(stages)
        if enrollment.status in ("completed", "awaiting_final_exam")
        else enrollment.current_stage_number
    )
    stage_number = requested_stage_number or max_stage_number
    if stage_number < 1 or stage_number > max_stage_number:
        raise HTTPException(
            status_code=409,
            detail="فقط درباره مرحله جاری یا مرحله‌های طی‌شده می‌توانی سؤال بپرسی.",
        )
    return stages[stage_number - 1], stages


def _coach_message_out(
    message: CoachMessage,
    stage_numbers: dict[int, int],
) -> CoachMessageOut:
    metadata = message.content_json if isinstance(message.content_json, dict) else {}
    citations: list[CoachCitationOut] = []
    raw_citations = metadata.get("citations") if isinstance(metadata, dict) else None
    if isinstance(raw_citations, list):
        for item in raw_citations:
            if not isinstance(item, dict):
                continue
            number = item.get("source_number")
            title = item.get("title")
            scope = item.get("scope")
            if isinstance(number, int) and isinstance(title, str) and isinstance(scope, str):
                citations.append(
                    CoachCitationOut(source_number=number, title=title, scope=scope)
                )
    return CoachMessageOut(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        stage_number=stage_numbers.get(message.module_stage_content_id),
        citations=citations,
    )


def _personalized_citations(raw_citations: object) -> list[CoachCitationOut]:
    if not isinstance(raw_citations, list):
        return []
    citations: list[CoachCitationOut] = []
    for item in raw_citations:
        if not isinstance(item, dict):
            continue
        number = item.get("source_number")
        title = item.get("title")
        scope = item.get("scope")
        if isinstance(number, int) and isinstance(title, str) and isinstance(scope, str):
            citations.append(CoachCitationOut(source_number=number, title=title, scope=scope))
    return citations


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
    existing_user = db.scalars(select(User).where(User.phone == phone).limit(1)).first()
    if existing_user and existing_user.blocked_at is not None:
        raise HTTPException(status_code=403, detail="این حساب توسط مدیریت مسدود شده است.")
    requires_display_name = existing_user is None
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
        requires_display_name=requires_display_name,
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> PhoneLoginOut:
    phone = _normalize_phone(payload.phone)
    display_name = payload.display_name.strip() if payload.display_name else None
    existing_user = db.scalars(select(User).where(User.phone == phone).limit(1)).first()
    if existing_user and existing_user.blocked_at is not None:
        raise HTTPException(status_code=403, detail="این حساب توسط مدیریت مسدود شده است.")
    has_existing_user = existing_user is not None
    if not has_existing_user and not display_name:
        raise HTTPException(status_code=422, detail="برای ساخت حساب یک نام وارد کن.")
    if not verify_otp(db, phone, normalize_otp_code(payload.code)):
        raise HTTPException(status_code=401, detail="کد تایید اشتباه است یا منقضی شده.")
    user = _get_or_create_phone_user(db, phone, display_name)
    session_token = create_user_session(db, user, request)
    db.commit()
    db.refresh(user)
    set_user_cookie(response, session_token)
    if not has_existing_user:
        background_tasks.add_task(send_welcome_sms, phone, user.display_name)
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
    output = [_course_out(db, course) for course in courses]
    return [course for course in output if course]


@router.get("/api/courses/slug/{course_slug}", response_model=CourseOverviewOut)
def get_course_overview(course_slug: str, db: Session = Depends(get_db)) -> CourseOverviewOut:
    course = db.scalars(
        select(Course)
        .where(Course.slug == course_slug, Course.status == "published")
        .options(selectinload(Course.versions).selectinload(CourseVersion.stages))
        .limit(1)
    ).first()
    overview = _course_overview_out(db, course) if course else None
    if not overview:
        raise HTTPException(status_code=404, detail="دوره منتشرشده پیدا نشد.")
    return overview


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
    uses_modules = _uses_module_structure(db, version.id)
    if uses_modules:
        module_stages = _approved_module_stages(db, version.id)
    else:
        stages = _approved_stages(db, version.id)

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
        db.flush()

    if uses_modules:
        module_progress_rows = _ensure_module_stage_progress(db, enrollment, module_stages)
        _sync_module_enrollment_progress(
            enrollment,
            module_progress_rows,
            requires_final_exam=version.requires_final_exam,
        )
    else:
        progress_rows = _ensure_stage_progress(db, enrollment, stages)
        _sync_enrollment_progress(enrollment, progress_rows)
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


@router.get("/api/learning/enrollments/current", response_model=LearningPathOut)
def get_current_learning_path(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> LearningPathOut:
    enrollment = _current_enrollment(db, user.id)
    if _uses_module_structure(db, enrollment.course_version_id):
        stages = _approved_module_stages(db, enrollment.course_version_id)
        progress_rows = _ensure_module_stage_progress(db, enrollment, stages)
        _sync_module_enrollment_progress(
            enrollment,
            progress_rows,
            requires_final_exam=_requires_final_exam(db, enrollment),
        )
        db.commit()
        return _module_learning_path_out(db, enrollment, stages, progress_rows)
    stages = _approved_stages(db, enrollment.course_version_id)
    progress_rows = _ensure_stage_progress(db, enrollment, stages)
    _sync_enrollment_progress(enrollment, progress_rows)
    db.commit()
    return _learning_path_out(db, enrollment, stages, progress_rows)


@router.get("/api/learning/enrollments/{enrollment_id}", response_model=LearningPathOut)
def get_learning_path(
    enrollment_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> LearningPathOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id)
    if _uses_module_structure(db, enrollment.course_version_id):
        stages = _approved_module_stages(db, enrollment.course_version_id)
        progress_rows = _ensure_module_stage_progress(db, enrollment, stages)
        _sync_module_enrollment_progress(
            enrollment,
            progress_rows,
            requires_final_exam=_requires_final_exam(db, enrollment),
        )
        db.commit()
        return _module_learning_path_out(db, enrollment, stages, progress_rows)
    stages = _approved_stages(db, enrollment.course_version_id)
    progress_rows = _ensure_stage_progress(db, enrollment, stages)
    _sync_enrollment_progress(enrollment, progress_rows)
    db.commit()
    return _learning_path_out(db, enrollment, stages, progress_rows)


@router.get(
    "/api/learning/enrollments/{enrollment_id}/final-exam",
    response_model=FinalExamStateOut,
)
def get_final_exam_state(
    enrollment_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> FinalExamStateOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id)
    return _final_exam_state_out(db, enrollment)


@router.post(
    "/api/learning/enrollments/{enrollment_id}/final-exam/start",
    response_model=FinalExamAttemptOut,
)
async def begin_final_exam(
    enrollment_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> FinalExamAttemptOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id, for_update=True)
    try:
        session = await start_final_exam(db, user=user, enrollment=enrollment)
        db.commit()
        db.refresh(session.attempt)
    except FinalExamStateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _final_exam_attempt_out(db, attempt=session.attempt, exam=session.exam)


@router.post(
    "/api/learning/enrollments/{enrollment_id}/final-exam/attempts/{attempt_id}/submit",
    response_model=FinalExamResultOut,
)
async def submit_final_exam(
    enrollment_id: int,
    attempt_id: int,
    payload: FinalExamSubmitIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> FinalExamResultOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id, for_update=True)
    try:
        result = await grade_final_exam(
            db,
            user=user,
            enrollment=enrollment,
            attempt_id=attempt_id,
            raw_answers=payload.answers,
        )
        db.commit()
        db.refresh(result.attempt)
        if result.certificate:
            db.refresh(result.certificate)
    except FinalExamStateError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FinalExamAIError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    certificate = (
        _certificate_out(result.certificate)
        if result.certificate and result.certificate.status == "issued"
        else None
    )
    return FinalExamResultOut(
        attempt=_final_exam_attempt_out(db, attempt=result.attempt, exam=result.exam),
        score=result.score,
        passed=result.passed,
        feedback=result.feedback,
        question_feedback=result.question_feedback,
        certificate=certificate,
    )


@router.get(
    "/api/learning/enrollments/{enrollment_id}/certificate",
    response_model=CertificateOut,
)
def get_my_course_certificate(
    enrollment_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> CertificateOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id)
    certificate = issued_certificate(db, enrollment)
    if not certificate or certificate.status != "issued":
        raise HTTPException(status_code=404, detail="گواهی پایان دوره هنوز صادر نشده است.")
    return _certificate_out(certificate)


@router.get("/api/certificates/{certificate_number}", response_model=CertificateVerificationOut)
def verify_certificate(certificate_number: str, db: Session = Depends(get_db)) -> CertificateVerificationOut:
    certificate = db.scalars(
        select(Certificate).where(
            Certificate.certificate_number == certificate_number.strip(),
            Certificate.status == "issued",
        )
    ).first()
    if not certificate:
        raise HTTPException(status_code=404, detail="گواهی معتبر پیدا نشد.")
    data = _certificate_out(certificate)
    return CertificateVerificationOut(
        certificate_number=data.certificate_number,
        recipient_name=data.recipient_name,
        course_title=data.course_title,
        course_version_number=data.course_version_number,
        score=data.score,
        passing_score=data.passing_score,
        status=data.status,
        issued_at=data.issued_at,
        valid=True,
    )


@router.get(
    "/api/learning/enrollments/{enrollment_id}/coach/messages",
    response_model=CoachHistoryOut,
)
def get_coach_history(
    enrollment_id: int,
    limit: int = 20,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> CoachHistoryOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id)
    _, stages = _resolve_coaching_stage(db, enrollment, None)
    thread, messages = list_coach_messages(
        db,
        user=user,
        enrollment=enrollment,
        limit=limit,
    )
    stage_numbers = {stage.id: number for number, stage in enumerate(stages, start=1)}
    return CoachHistoryOut(
        thread_id=thread.id if thread else None,
        messages=[_coach_message_out(message, stage_numbers) for message in messages],
    )


@router.post(
    "/api/learning/enrollments/{enrollment_id}/coach/messages",
    response_model=CoachReplyOut,
)
async def ask_course_coach(
    enrollment_id: int,
    payload: CoachQuestionIn,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> CoachReplyOut:
    question = payload.message.strip()
    if len(question) < 2:
        raise HTTPException(status_code=422, detail="سؤال کوچینگ را کامل‌تر بنویس.")
    # A coach response can wait on the model provider; do not keep the
    # enrollment row locked for the duration of that external request.
    enrollment = _owned_enrollment(db, enrollment_id, user.id)
    stage, _ = _resolve_coaching_stage(db, enrollment, payload.stage_number)
    try:
        reply = await answer_course_question(
            db,
            user=user,
            enrollment=enrollment,
            stage=stage,
            stage_number=payload.stage_number or enrollment.current_stage_number,
            question=question,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="وضعیت کوچینگ این دوره معتبر نیست.") from exc

    return CoachReplyOut(
        thread_id=reply.thread.id,
        answer=reply.assistant_message.content,
        grounded=reply.grounded,
        citations=[CoachCitationOut(**citation) for citation in reply.citations],
        retrieval_method=reply.retrieval_method,
        suggested_action=reply.suggested_action,
    )


@router.get(
    "/api/learning/enrollments/{enrollment_id}/stages/current",
    response_model=LearningStageOut,
)
def get_current_learning_stage(
    enrollment_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> LearningStageOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id)
    if _uses_module_structure(db, enrollment.course_version_id):
        stages = _approved_module_stages(db, enrollment.course_version_id)
        progress_rows = _ensure_module_stage_progress(db, enrollment, stages)
        _sync_module_enrollment_progress(
            enrollment,
            progress_rows,
            requires_final_exam=_requires_final_exam(db, enrollment),
        )
        db.commit()
        return _module_current_stage_out(db, enrollment, stages, progress_rows)
    stages = _approved_stages(db, enrollment.course_version_id)
    progress_rows = _ensure_stage_progress(db, enrollment, stages)
    _sync_enrollment_progress(enrollment, progress_rows)
    db.commit()

    stage_number = LEARNING_STAGE_COUNT if enrollment.status == "completed" else enrollment.current_stage_number
    stage = next(stage for stage in stages if stage.stage_number == stage_number)
    progress = next(row for row in progress_rows if row.stage_number == stage_number)
    course = db.get(Course, enrollment.course_id)
    if not course:
        raise HTTPException(status_code=409, detail="دوره این مسیر آموزشی پیدا نشد.")
    content = stage.content_json if isinstance(stage.content_json, dict) else {}
    return LearningStageOut(
        enrollment_id=enrollment.id,
        course_id=course.id,
        course_title=course.title,
        stage_number=stage.stage_number,
        stage_type=stage.stage_type,
        title=stage.title,
        progress_status=progress.status,
        progress_percentage=enrollment.progress_percentage,
        total_stage_count=LEARNING_STAGE_COUNT,
        course_completed=enrollment.status == "completed",
        content=content,
        coaching=_coaching_checkpoint(content, enrollment.status == "completed"),
    )


@router.post(
    "/api/learning/enrollments/{enrollment_id}/stages/{stage_number}/personalized-example",
    response_model=PersonalizedStageContentOut,
)
async def get_personalized_stage_example(
    enrollment_id: int,
    stage_number: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> PersonalizedStageContentOut:
    """Create one cached job-aware example only for the learner's reachable stage."""

    enrollment = _owned_enrollment(db, enrollment_id, user.id)
    if not _uses_module_structure(db, enrollment.course_version_id):
        raise HTTPException(status_code=409, detail="مثال شخصی‌سازی‌شده برای این نسخه دوره در دسترس نیست.")
    stages = _approved_module_stages(db, enrollment.course_version_id)
    if stage_number < 1 or stage_number > len(stages):
        raise HTTPException(status_code=404, detail="مرحله آموزشی پیدا نشد.")
    reachable_stage = (
        len(stages)
        if enrollment.status in ("completed", "awaiting_final_exam")
        else enrollment.current_stage_number
    )
    if stage_number > reachable_stage:
        raise HTTPException(status_code=409, detail="ابتدا به این مرحله از مسیر آموزشی برس.")

    stage = stages[stage_number - 1]
    if stage.template.code != "personalized_work_example":
        raise HTTPException(status_code=409, detail="این مرحله نمونه شخصی‌سازی‌شده ندارد.")
    progress_rows = _ensure_module_stage_progress(db, enrollment, stages)
    progress = progress_rows[stage_number - 1]
    cached_content = progress.generated_content_json
    if isinstance(cached_content, dict):
        citations = _personalized_citations(progress.generated_content_sources_json)
        return PersonalizedStageContentOut(
            cached=True,
            grounded=bool(citations),
            content=cached_content,
            citations=citations,
        )

    generated = await generate_personalized_work_example(
        db,
        user=user,
        enrollment=enrollment,
        stage=stage,
        stage_number=stage_number,
    )
    progress.generated_content_json = generated.content
    progress.generated_content_sources_json = generated.citations
    progress.generated_content_model = generated.model
    progress.generated_content_prompt_version = generated.prompt_version
    progress.generated_content_at = datetime.now(timezone.utc)
    db.commit()
    return PersonalizedStageContentOut(
        cached=False,
        grounded=generated.grounded,
        content=generated.content,
        citations=[CoachCitationOut(**citation) for citation in generated.citations],
    )


@router.post(
    "/api/learning/enrollments/{enrollment_id}/stages/{stage_number}/complete",
    response_model=StageCompleteOut,
)
def complete_learning_stage(
    enrollment_id: int,
    stage_number: int,
    payload: StageCompleteIn | None = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> StageCompleteOut:
    enrollment = _owned_enrollment(db, enrollment_id, user.id, for_update=True)
    if _uses_module_structure(db, enrollment.course_version_id):
        return _complete_module_learning_stage(db, enrollment, stage_number, payload)
    stages = _approved_stages(db, enrollment.course_version_id)
    stage = next((item for item in stages if item.stage_number == stage_number), None)
    if not stage:
        raise HTTPException(status_code=404, detail="مرحله آموزشی پیدا نشد.")

    progress_rows = _ensure_stage_progress(db, enrollment, stages)
    _sync_enrollment_progress(enrollment, progress_rows)
    progress = next(row for row in progress_rows if row.stage_number == stage_number)

    if progress.status != "completed" and stage_number != enrollment.current_stage_number:
        raise HTTPException(
            status_code=409,
            detail=f"ابتدا مرحله {enrollment.current_stage_number} را کامل کن.",
        )

    if progress.status != "completed":
        progress.status = "completed"
        progress.completed_at = datetime.now(timezone.utc)
        if payload and payload.response is not None:
            progress.response_json = payload.response
        if stage_number < LEARNING_STAGE_COUNT:
            next_progress = next(row for row in progress_rows if row.stage_number == stage_number + 1)
            if next_progress.status in ("locked", "not_started"):
                next_progress.status = "available"
        _sync_enrollment_progress(enrollment, progress_rows)
        db.commit()
        db.refresh(enrollment)

    path = _learning_path_out(db, enrollment, stages, progress_rows)
    course_completed = enrollment.status == "completed"
    content = stage.content_json if isinstance(stage.content_json, dict) else {}
    return StageCompleteOut(
        enrollment_id=enrollment.id,
        completed_stage_number=stage_number,
        next_stage_number=None if course_completed else enrollment.current_stage_number,
        course_completed=course_completed,
        progress_percentage=enrollment.progress_percentage,
        coaching=_coaching_checkpoint(content, course_completed),
        path=path,
    )


@router.post("/api/onboarding/start", include_in_schema=False)
def start_onboarding() -> None:
    raise HTTPException(status_code=410, detail="Use OTP login and /api/me/profile.")


@router.get("/api/admin/users", response_model=list[UserOut], dependencies=[Depends(require_admin)])
def list_users(include_deleted: bool = False, db: Session = Depends(get_db)) -> list[UserOut]:
    query = select(User).options(selectinload(User.profile))
    if not include_deleted:
        query = query.where(User.deleted_at.is_(None))
    users = db.scalars(query.order_by(User.id.desc())).all()
    return [_user_out(user) for user in users]


@router.get("/api/admin/users/{user_id}", response_model=UserOut, dependencies=[Depends(require_admin)])
def get_user(user_id: int, db: Session = Depends(get_db)) -> UserOut:
    user = db.get(
        User,
        user_id,
        options=[selectinload(User.profile)],
    )
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_out(user)


@router.delete("/api/admin/users/{user_id}", dependencies=[Depends(require_admin)])
def delete_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.deleted_at is None:
        user.deleted_at = datetime.now(timezone.utc)
        revoke_user_sessions(db, user.id)
    db.commit()
    return {"deleted": True, "soft_deleted": True, "reactivates_after_phone_otp": True}


@router.post("/api/admin/users/{user_id}/restore", dependencies=[Depends(require_admin)])
def restore_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.deleted_at = None
    db.commit()
    return {"restored": True}


@router.post("/api/admin/users/{user_id}/block", dependencies=[Depends(require_admin)])
def block_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.blocked_at is None:
        user.blocked_at = datetime.now(timezone.utc)
        revoke_user_sessions(db, user.id)
    db.commit()
    return {"blocked": True}


@router.post("/api/admin/users/{user_id}/unblock", dependencies=[Depends(require_admin)])
def unblock_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.blocked_at = None
    db.commit()
    return {"unblocked": True}

