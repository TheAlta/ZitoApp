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


class PhoneLoginIn(BaseModel):
    phone: str = Field(min_length=8, max_length=20)


class PhoneLoginOut(BaseModel):
    user_id: int
    username: str
    redirect_url: str


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
    full_name: str | None
    username: str | None
    profession: str | None
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
