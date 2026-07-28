from datetime import datetime

from pydantic import BaseModel, Field


class QuestionOut(BaseModel):
    id: int
    key: str
    text: str
    sort_order: int

    model_config = {"from_attributes": True}


class OnboardingStartOut(BaseModel):
    user_id: int
    question: QuestionOut


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
    expires_in_seconds: int
    resend_after_seconds: int
    provider: str
    mock_code: str | None = None


class OtpVerifyIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=4, max_length=8)
    display_name: str = Field(min_length=1, max_length=100)


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


class OnboardingStateOut(BaseModel):
    user_id: int
    completed: bool = False
    question: QuestionOut | None = None


class AnswerIn(BaseModel):
    question_id: int
    answer_text: str = Field(min_length=1, max_length=2000)


class OnboardingAnswerOut(BaseModel):
    valid: bool
    reason: str
    guidance: str | None = None
    completed: bool = False
    next_question: QuestionOut | None = None


class AnswerOut(BaseModel):
    id: int
    question_id: int
    question_text: str
    answer_text: str
    is_valid: bool
    validation_reason: str | None
    validated_at: datetime


class UserOut(BaseModel):
    id: int
    phone: str | None
    display_name: str
    work_or_study_field: str | None = None
    deleted_at: datetime | None = None
    created_at: datetime
    answers: list[AnswerOut] = []


class AdminAnswerUpdate(BaseModel):
    answer_text: str = Field(min_length=1, max_length=2000)


class AdminLoginIn(BaseModel):
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class AdminLoginOut(BaseModel):
    ok: bool = True
    username: str


class KnowledgeIn(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    content: str = Field(min_length=10)
    tags: str | None = Field(default=None, max_length=255)


class KnowledgeOut(KnowledgeIn):
    id: int


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
