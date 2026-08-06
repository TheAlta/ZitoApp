from datetime import datetime
from typing import Any

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
    daily_learning_time_text: str | None = Field(default=None, min_length=1, max_length=120)
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
    daily_learning_time_text: str | None = None
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
    module_count: int = 0


class EnrollmentOut(BaseModel):
    id: int
    user_id: int
    course_id: int
    course_version_id: int
    status: str
    current_stage_number: int
    progress_percentage: int


class LearningStageSummaryOut(BaseModel):
    stage_number: int
    stage_type: str
    title: str
    status: str
    is_current: bool
    module_id: int | None = None
    module_number: int | None = None
    module_title: str | None = None
    module_stage_number: int | None = None


class LearningModuleOut(BaseModel):
    module_id: int
    module_number: int
    title: str
    description: str | None = None
    status: str
    is_current: bool
    completed_stage_count: int
    total_stage_count: int


class LearningPathOut(BaseModel):
    enrollment_id: int
    course_id: int
    course_title: str
    course_slug: str
    course_domain: str
    course_version_id: int
    course_version_number: int
    status: str
    current_stage_number: int
    completed_stage_count: int
    total_stage_count: int
    progress_percentage: int
    stages: list[LearningStageSummaryOut]
    module_count: int = 0
    modules: list[LearningModuleOut] = Field(default_factory=list)


class CoachingCheckpointOut(BaseModel):
    prompt: str
    enabled: bool = False
    mode: str = "preview"


class LearningStageOut(BaseModel):
    enrollment_id: int
    course_id: int
    course_title: str
    stage_number: int
    stage_type: str
    title: str
    progress_status: str
    progress_percentage: int
    total_stage_count: int
    course_completed: bool
    content: dict[str, Any]
    coaching: CoachingCheckpointOut
    module_id: int | None = None
    module_number: int | None = None
    module_title: str | None = None
    module_stage_number: int | None = None
    total_module_count: int = 0


class StageCompleteIn(BaseModel):
    response: dict[str, Any] | None = None


class StageCompleteOut(BaseModel):
    enrollment_id: int
    completed_stage_number: int
    next_stage_number: int | None
    course_completed: bool
    progress_percentage: int
    coaching: CoachingCheckpointOut
    path: LearningPathOut


class UserOut(BaseModel):
    id: int
    phone: str
    display_name: str
    deleted_at: datetime | None = None
    blocked_at: datetime | None = None
    created_at: datetime
    work_or_study_field: str | None = None
    education_level: str | None = None
    learning_goal_interests: str | None = None
    ai_familiarity_level: str | None = None
    daily_learning_time_text: str | None = None
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
