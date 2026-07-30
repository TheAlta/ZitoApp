from datetime import datetime

from pydantic import BaseModel, Field


class PhoneLoginOut(BaseModel):
    user_id: int
    phone: str
    display_name: str
    redirect_url: str


class OtpRequestIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)


class OtpRequestOut(BaseModel):
    ok: bool = True
    phone: str
    requires_display_name: bool
    expires_in_seconds: int
    resend_after_seconds: int
    provider: str
    mock_code: str | None = None


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    display_name: str | None = Field(default=None, max_length=100)


class ProfilePatchIn(BaseModel):
    work_or_study_field: str | None = Field(default=None, min_length=1, max_length=255)
    education_level: str | None = Field(default=None, min_length=1, max_length=80)
    learning_goal_interests: str | None = Field(default=None, min_length=1, max_length=2000)
    ai_familiarity_level: str | None = Field(default=None, min_length=1, max_length=50)
    daily_learning_minutes: int | None = Field(default=None, ge=0, le=1440)
    preferred_career_path: str | None = Field(default=None, min_length=1, max_length=255)
    referral_source: str | None = Field(default=None, max_length=120)


class ProfileOut(BaseModel):
    user_id: int
    display_name: str
    completed: bool
    work_or_study_field: str | None = None
    education_level: str | None = None
    learning_goal_interests: str | None = None
    ai_familiarity_level: str | None = None
    daily_learning_minutes: int | None = None
    preferred_career_path: str | None = None
    referral_source: str | None = None
    completed_at: datetime | None = None


class UserMeOut(BaseModel):
    id: int
    phone: str
    display_name: str


class CourseOut(BaseModel):
    id: int
    title: str
    slug: str
    domain: str
    version_id: int
    version_number: int
    stage_count: int


class EnrollmentOut(BaseModel):
    id: int
    user_id: int
    course_id: int
    course_version_id: int
    status: str
    current_stage_number: int
    progress_percentage: int


class UserOut(BaseModel):
    id: int
    phone: str
    display_name: str
    deleted_at: datetime | None = None
    created_at: datetime
    work_or_study_field: str | None = None
    education_level: str | None = None
    learning_goal_interests: str | None = None
    ai_familiarity_level: str | None = None
    daily_learning_minutes: int | None = None
    preferred_career_path: str | None = None
    referral_source: str | None = None
    profile_completed: bool = False


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class AdminLoginOut(BaseModel):
    ok: bool = True
    username: str


class TrainingQuestionIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class TrainingAnswerIn(BaseModel):
    lesson: str = Field(min_length=2)
    check_question: str = Field(min_length=2)
    answer_text: str = Field(min_length=1, max_length=2000)


class TrainingMessageIn(BaseModel):
    lesson: str = Field(min_length=2)
    check_question: str = Field(min_length=2)
    message: str = Field(min_length=1, max_length=2000)


class TrainingLessonOut(BaseModel):
    title: str
    lesson: str
    key_points: list[str]
    exercise: str
    check_question: str
    percentage: int
