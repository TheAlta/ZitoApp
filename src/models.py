from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    username: Mapped[str] = mapped_column(String(100), nullable=True)
    profession: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    answers: Mapped[list["Answer"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    progress: Mapped["UserProgress"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    answers: Mapped[list["Answer"]] = relationship(back_populates="question")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_reason: Mapped[str] = mapped_column(Text, nullable=True)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="answers")
    question: Mapped[Question] = relationship(back_populates="answers")


class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    current_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_lesson: Mapped[str] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="progress")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    versions: Mapped[list["CourseVersion"]] = relationship(back_populates="course", cascade="all, delete-orphan")
    kb_documents: Mapped[list["CourseKbDocument"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class CourseVersion(Base):
    __tablename__ = "course_versions"
    __table_args__ = (UniqueConstraint("course_id", "version_number", name="uq_course_versions_course_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="draft", nullable=False)
    source: Mapped[str] = mapped_column(String(40), default="seed", nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    course: Mapped[Course] = relationship(back_populates="versions")
    stages: Mapped[list["CourseStageContent"]] = relationship(back_populates="course_version", cascade="all, delete-orphan")
    exams: Mapped[list["Exam"]] = relationship(back_populates="course_version", cascade="all, delete-orphan")


class CourseStageContent(Base):
    __tablename__ = "course_stage_contents"
    __table_args__ = (UniqueConstraint("course_version_id", "stage_number", name="uq_course_stage_version_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_version_id: Mapped[int] = mapped_column(ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False)
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False)
    stage_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="approved", nullable=False)
    ai_generation_status: Mapped[str] = mapped_column(String(40), default="seeded", nullable=False)
    review_status: Mapped[str] = mapped_column(String(40), default="approved", nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(100), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    course_version: Mapped[CourseVersion] = relationship(back_populates="stages")


class CourseKbDocument(Base):
    __tablename__ = "course_kb_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[str] = mapped_column(String(255), nullable=True)
    source_type: Mapped[str] = mapped_column(String(40), default="seed", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    course: Mapped[Course] = relationship(back_populates="kb_documents")


class UserProfileV2(Base):
    __tablename__ = "user_profiles_v2"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=True)
    age_range: Mapped[str] = mapped_column(String(80), nullable=True)
    work_status: Mapped[str] = mapped_column(String(120), nullable=True)
    work_domain: Mapped[str] = mapped_column(String(255), nullable=True)
    referral_source: Mapped[str] = mapped_column(String(120), nullable=True)
    daily_study_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    learning_goal: Mapped[str] = mapped_column(String(255), nullable=True)
    experience_level: Mapped[str] = mapped_column(String(80), nullable=True)
    preferred_learning_style: Mapped[str] = mapped_column(String(120), nullable=True)
    learning_blocker: Mapped[str] = mapped_column(String(255), nullable=True)
    commitment_level: Mapped[str] = mapped_column(String(80), nullable=True)
    target_skill: Mapped[str] = mapped_column(String(255), nullable=True)
    interested_domains: Mapped[list] = mapped_column(JSON, nullable=True)
    decision_factors: Mapped[list] = mapped_column(JSON, nullable=True)
    notification_channel: Mapped[str] = mapped_column(String(80), nullable=True)
    reminder_frequency: Mapped[str] = mapped_column(String(80), nullable=True)
    recommended_course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="SET NULL"), nullable=True)
    recommended_track_label: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProfileBuilderAnswer(Base):
    __tablename__ = "profile_builder_answers"
    __table_args__ = (UniqueConstraint("user_id", "step_key", name="uq_profile_builder_user_step"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    step_key: Mapped[str] = mapped_column(String(120), nullable=False)
    answer_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserCourseEnrollment(Base):
    __tablename__ = "user_course_enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_version_id", name="uq_user_course_version_enrollment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    course_version_id: Mapped[int] = mapped_column(ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    current_stage_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    stage_progress: Mapped[list["UserStageProgress"]] = relationship(back_populates="enrollment", cascade="all, delete-orphan")


class UserStageProgress(Base):
    __tablename__ = "user_stage_progress"
    __table_args__ = (UniqueConstraint("enrollment_id", "stage_number", name="uq_user_stage_progress_enrollment_stage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("user_course_enrollments.id", ondelete="CASCADE"), nullable=False)
    stage_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="not_started", nullable=False)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    enrollment: Mapped[UserCourseEnrollment] = relationship(back_populates="stage_progress")


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_version_id: Mapped[int] = mapped_column(ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    questions_json: Mapped[list] = mapped_column(JSON, nullable=False)
    passing_score: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="published", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    course_version: Mapped[CourseVersion] = relationship(back_populates="exams")


class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    enrollment_id: Mapped[int] = mapped_column(ForeignKey("user_course_enrollments.id", ondelete="CASCADE"), nullable=True)
    answers_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    grading_feedback: Mapped[str] = mapped_column(Text, nullable=True)
    graded_by_ai_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    course_version_id: Mapped[int] = mapped_column(ForeignKey("course_versions.id", ondelete="CASCADE"), nullable=False)
    exam_attempt_id: Mapped[int] = mapped_column(ForeignKey("exam_attempts.id", ondelete="SET NULL"), nullable=True)
    certificate_number: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="issued", nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
