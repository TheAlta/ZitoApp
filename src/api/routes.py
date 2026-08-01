import re

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from src.db import get_db
from src.models import (
    Course,
    CourseStageContent,
    CourseVersion,
    User,
    UserCourseEnrollment,
    UserProfile,
    UserStageProgress,
)
from src.schemas import (
    AdminLoginIn,
    AdminLoginOut,
    CoachingCheckpointOut,
    CourseOut,
    EnrollmentOut,
    LearningPathOut,
    LearningStageOut,
    LearningStageSummaryOut,
    OtpRequestIn,
    OtpRequestOut,
    OtpVerifyIn,
    PhoneLoginOut,
    ProfileOut,
    ProfilePatchIn,
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
from src.services.otp import OtpError, OtpRateLimitError, normalize_otp_code, request_otp, verify_otp

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
        created_at=user.created_at,
        work_or_study_field=profile.work_or_study_field if profile else None,
        education_level=profile.education_level if profile else None,
        learning_goal_interests=profile.learning_goal_interests if profile else None,
        ai_familiarity_level=profile.ai_familiarity_level if profile else None,
        daily_learning_minutes=profile.daily_learning_minutes if profile else None,
        preferred_career_path=profile.preferred_career_path if profile else None,
        referral_source=profile.referral_source if profile else None,
        profile_completed=bool(profile and _profile_is_complete(profile)),
    )


def _get_or_create_phone_user(db: Session, phone: str, display_name: str | None) -> User:
    now = datetime.now(timezone.utc)
    user = db.scalars(select(User).where(User.phone == phone).limit(1)).first()
    if user:
        if user.deleted_at is not None:
            raise HTTPException(
                status_code=403,
                detail="این حساب غیرفعال شده است. برای بازیابی با پشتیبانی تماس بگیر.",
            )
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
            UserCourseEnrollment.status.in_(("active", "completed")),
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


def _coaching_checkpoint(content: dict, course_completed: bool = False) -> CoachingCheckpointOut:
    checkpoint = content.get("coaching_checkpoint") if isinstance(content, dict) else None
    prompt = "مسیر را کامل کردی؛ درباره جمع‌بندی سوالی داری؟" if course_completed else "درباره این مرحله سوالی داری؟"
    if isinstance(checkpoint, dict) and checkpoint.get("prompt"):
        prompt = str(checkpoint["prompt"])
    return CoachingCheckpointOut(prompt=prompt, enabled=False, mode="preview")


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
    requires_display_name = db.scalar(
        select(User.id).where(User.phone == phone).limit(1)
    ) is None
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
    db: Session = Depends(get_db),
) -> PhoneLoginOut:
    phone = _normalize_phone(payload.phone)
    display_name = payload.display_name.strip() if payload.display_name else None
    has_existing_user = db.scalar(select(User.id).where(User.phone == phone).limit(1)) is not None
    if not has_existing_user and not display_name:
        raise HTTPException(status_code=422, detail="برای ساخت حساب یک نام وارد کن.")
    if not verify_otp(db, phone, normalize_otp_code(payload.code)):
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
    stages = _approved_stages(db, enrollment.course_version_id)
    progress_rows = _ensure_stage_progress(db, enrollment, stages)
    _sync_enrollment_progress(enrollment, progress_rows)
    db.commit()
    return _learning_path_out(db, enrollment, stages, progress_rows)


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
    return {"deleted": True, "soft_deleted": True}


@router.post("/api/admin/users/{user_id}/restore", dependencies=[Depends(require_admin)])
def restore_user(user_id: int, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.deleted_at = None
    db.commit()
    return {"restored": True}

