# گزارش خام ممیزی وضعیت واقعی پروژه Zito

تاریخ ممیزی: 2026-07-27  
ریشه پروژه بررسی‌شده: `C:\Users\ASUS\Desktop\ZitoApp`  
commit مبنا در زمان ممیزی: `6fb0d46d274b64990a7066d763c33e58211c65ad`  
روش تهیه: خواندن مستقیم فایل‌های tracked، اجرای تست‌ها، اجرای Alembic روی PostgreSQL محلی، بررسی Routeهای FastAPI و جست‌وجوی ایستای کد.  

محدوده قطعیت:

- اطلاعات کد، Git محلی و PostgreSQL محلی مستقیماً بررسی شده‌اند.
- وضعیت لحظه‌ای production، Nginx، systemd، DNS، SSL، سرویس واقعی Arvan و ارسال زنده sms.ir در این ممیزی بررسی مستقیم نشده است؛ وضعیت فعلی آن‌ها `نامشخص` است.
- هیچ مقدار واقعی secret، API key، رمز دیتابیس یا رمز سرور در این فایل نوشته نشده است.

## ۱. ساختار پوشه‌ها

درخت زیر فایل‌های اصلی repository و artifactهای محلی مهم را نشان می‌دهد. محتوای `.git/`، `.venv/` و `.secrets/` عمداً باز نشده است.

```text
ZitoApp/
|-- .agents/                              # پوشه محلی agent؛ در زمان ممیزی فایل tracked مهمی در آن دیده نشد.
|-- .github/
|   `-- workflows/
|       `-- tests.yml                     # اجرای unittest روی push و pull_request با Python 3.12.
|-- .secrets/                             # vault محلی ignored؛ شامل inventory/vault محلی، بدون ورود محتوا به Git.
|-- .venv/                                # virtual environment محلی Python؛ ignored.
|-- landing/
|   |-- logo-z.png                        # تصویر اصلی لوگوی Z.
|   |-- logo-z-transparent.png            # نسخه transparent لوگوی Z.
|   |-- rocket-svgrepo-com.svg            # asset قدیمی/کمکی لندینگ؛ مصرف فعلی در HTML نیازمند بررسی بصری است.
|   |-- zito-avatar.png                   # تصویر اصلی آواتار Zito.
|   |-- zito-avatar-transparent.png       # نسخه transparent آواتار.
|   `-- zito.html                         # لندینگ، دریافت نام/شماره، درخواست و تایید OTP و انتقال به /app/.
|-- migrations/
|   |-- env.py                            # اتصال Alembic به Settings و metadata واقعی SQLAlchemy.
|   `-- versions/
|       |-- 20260707_0001_initial.py       # schema قدیمی users/questions/answers/progress/knowledge.
|       |-- 20260714_0002_admins.py        # جدول admins.
|       |-- 20260723_0003_phase2_schema.py # قرارداد دوره، 20 مرحله، KB دوره، پروفایل، آزمون و مدرک.
|       |-- 20260726_0004_phone_otp_codes.py
|       |                                      # جدول کدهای OTP.
|       `-- 20260727_0005_user_phone_identity.py
|                                              # ستون phone یکتا در users و migration داده‌های قدیمی.
|-- src/
|   |-- __init__.py                       # package marker.
|   |-- api/
|   |   |-- __init__.py                   # package marker.
|   |   `-- routes.py                     # تمام API routeهای health/admin/OTP/profile/course/onboarding/training.
|   |-- lib/
|   |   |-- __init__.py                   # package marker.
|   |   `-- arvan_client.py               # تنها client شبکه‌ای AI برای Arvan AIaaS و mock AI.
|   |-- prompts/
|   |   |-- __init__.py                   # load_prompt از فایل UTF-8.
|   |   |-- initial_answer_validation.md  # prompt مسیر onboarding قدیمی.
|   |   |-- training_answer_evaluation.md # prompt ارزیابی تمرین.
|   |   |-- training_lesson_generation.md # prompt تولید درس.
|   |   `-- training_question_validation.md
|   |                                          # prompt اعتبارسنجی سوال آموزشی.
|   |-- services/
|   |   |-- __init__.py                   # package marker.
|   |   |-- json_utils.py                 # استخراج JSON object از خروجی AI.
|   |   |-- otp.py                        # تولید/hash/verify OTP و adapter سرویس sms.ir.
|   |   |-- rag.py                        # retrieval واژگانی ILIKE از knowledge_documents.
|   |   |-- training.py                   # تولید درس، پاسخ سوال و fallbackهای آموزشی.
|   |   `-- validation.py                 # validation و evaluation با AI و fallback.
|   |-- templates/
|   |   |-- admin.html                    # UI فهرست/ویرایش پاسخ/حذف user قدیمی.
|   |   |-- admin_login.html              # UI ورود مدیر.
|   |   `-- chat.html                     # UI کاربر: پروفایل چتی، سیاره، lesson و پیام آموزشی.
|   |-- config.py                         # Pydantic Settings و validation تنظیمات production.
|   |-- db.py                             # engine، SessionLocal و dependency دیتابیس.
|   |-- main.py                           # ساخت FastAPI، startup seed، static mount و HTML routeها.
|   |-- models.py                         # تمام 18 مدل SQLAlchemy.
|   |-- schemas.py                        # request/response modelهای Pydantic.
|   |-- security.py                       # hash رمز مدیر، cookie امضاشده و admin guard.
|   `-- seed.py                           # seed قدیمی، مدیر اولیه و Fake CMS شامل 20 مرحله.
|-- tests/
|   |-- __init__.py                       # package marker.
|   |-- _env.py                           # تنظیم SQLite/mock environment قبل از import برنامه.
|   |-- test_arvan_client.py              # یک تست mock client.
|   |-- test_health.py                    # یک تست health.
|   |-- test_otp.py                       # هفت تست flow OTP و adapter sms.ir.
|   |-- test_phase2_seed.py               # یک تست Fake CMS seed.
|   |-- test_profile_courses.py           # سه تست profile/course/enrollment.
|   |-- test_ui_contract.py               # دو تست قراردادی رشته‌های HTML/JS.
|   `-- test_validation.py                # دو تست validation onboarding قدیمی.
|-- tools/
|   `-- zito-secrets.ps1                  # vault محلی مبتنی بر Windows DPAPI و inventory متغیرها.
|-- .env                                  # تنظیمات واقعی محلی؛ ignored و در Git tracked نیست.
|-- .env.example                          # فهرست متغیرها با placeholder؛ tracked.
|-- .gitignore                            # حذف env، vault، DB، log، key و artifactها از Git.
|-- alembic.ini                           # تنظیم Alembic؛ URL placeholder با env.py override می‌شود.
|-- LICENSE                               # مجوز proprietary داخلی.
|-- PROJECT_CONTEXT.md                    # context معماری؛ بخش‌هایی از آن با کد فعلی ناسازگار است.
|-- PROJECT_REPORT.md                     # گزارش تاریخی/ترکیبی؛ منبع حقیقت این ممیزی نیست.
|-- PROJECT_RAW_AUDIT.md                  # همین گزارش.
|-- README.md                             # معرفی کوتاه؛ بخشی از flow آن قدیمی است.
|-- requirements.txt                      # هشت dependency مستقیم pinned.
|-- SECURITY.md                           # قواعد نگهداری secret و vault محلی.
`-- SETUP.md                              # راه‌اندازی local/PostgreSQL/Arvan/sms.ir.
```

artifactهای محلی ignored که هنگام ممیزی وجود داشتند:

- `local_test.db`، `local_test_ui.db` و `test_ci.db`: SQLiteهای محلی؛ tracked نیستند (`.gitignore:24-29`).
- `uvicorn-*.log`: logهای اجرای محلی؛ tracked نیستند (`.gitignore:29`).
- `.env`: وجود دارد ولی tracked نیست (`.gitignore:1-5`).
- `.secrets/zito-inventory.local.json` و `.secrets/zito-vault.local.json`: ignored؛ مقدارهایشان بررسی یا در این گزارش افشا نشده است.

فایل‌های راه‌اندازی اصلی:

- ساخت برنامه و HTML routeها: `src/main.py:13-64`.
- اتصال دیتابیس: `src/db.py:10-24`.
- ثبت router اصلی: `src/main.py:15`.
- mount assetهای landing روی `/landing-static`: `src/main.py:20-22`.
- startup اختیاری `create_all + seed_defaults`: `src/main.py:25-30`.
- اتصال Alembic به همان `DATABASE_URL`: `migrations/env.py:15-17`.

## ۲. تمام Route های واقعی

### Routeهای HTML و static

| Method | Path | محل تعریف | ورودی | خروجی | احراز هویت/مجوز |
|---|---|---|---|---|---|
| GET | `/` | `src/main.py:37-42` | ندارد | `HTMLResponse` از `landing/zito.html`؛ fallback به `chat.html` | ندارد |
| GET | `/chat` | `src/main.py:45-48` | query string اختیاری | `303 Redirect` به `/app/` با همان query | ندارد |
| GET | `/app/` | `src/main.py:51-53` | ندارد | `HTMLResponse` از `src/templates/chat.html` | ندارد |
| GET | `/admin/login` | `src/main.py:56-58` | ندارد | `HTMLResponse` از `admin_login.html` | ندارد |
| GET | `/admin` | `src/main.py:61-65` | cookie و DB dependency | HTML پنل یا `303` به `/admin/login` | بله؛ `get_admin_from_request` |
| STATIC | `/landing-static/*` | `src/main.py:20-22` | path asset | فایل‌های `landing/` | ندارد |

FastAPI به‌صورت خودکار `/docs`، `/redoc` و `/openapi.json` را نیز به‌علت ساخت `FastAPI(...)` در `src/main.py:14` فعال می‌کند؛ decorator صریح برای آن‌ها در پروژه وجود ندارد.

### Health و مدیریت

| Method | Path | محل تعریف | ورودی | response model/خروجی | احراز هویت/مجوز |
|---|---|---|---|---|---|
| GET | `/health` | `src/api/routes.py:167-170` | DB dependency | `dict {"status":"ok","database":"ok"}` | ندارد |
| POST | `/api/admin/login` | `src/api/routes.py:173-179` | body: `AdminLoginIn` (`src/schemas.py:130-132`) | `AdminLoginOut` (`src/schemas.py:135-137`) + cookie | عمومی؛ خودش credential را بررسی می‌کند |
| POST | `/api/admin/logout` | `src/api/routes.py:182-185` | response | `dict {"ok":true}` | guard ندارد؛ فقط cookie را حذف می‌کند |
| GET | `/api/admin/me` | `src/api/routes.py:188-190` | cookie | `dict {"ok":true}` | بله؛ `Depends(require_admin)` |
| GET | `/api/admin/users` | `src/api/routes.py:430-433` | DB | `list[UserOut]` (`src/schemas.py:116-123`) | بله؛ admin |
| GET | `/api/admin/users/{user_id}` | `src/api/routes.py:436-441` | path `user_id:int` | `UserOut` | بله؛ admin |
| PUT | `/api/admin/answers/{answer_id}` | `src/api/routes.py:444-453` | path + `AdminAnswerUpdate` (`src/schemas.py:126-127`) | `AnswerOut` (`src/schemas.py:106-113`) | بله؛ admin |
| DELETE | `/api/admin/users/{user_id}` | `src/api/routes.py:456-463` | path `user_id:int` | `dict {"deleted":true}` | بله؛ admin |

مکانیزم واقعی admin، HTTP Basic نیست. login از جدول `admins` استفاده می‌کند (`src/security.py:104-108`) و cookie امضاشده `zito_admin_session` را می‌سازد (`src/security.py:16`, `src/security.py:55-71`).

### OTP و پروفایل فاز ۲

| Method | Path | محل تعریف | ورودی | response model/خروجی | احراز هویت/مجوز |
|---|---|---|---|---|---|
| POST | `/api/auth/otp/request` | `src/api/routes.py:193-214` | `OtpRequestIn {phone}` (`src/schemas.py:27-28`) | `OtpRequestOut` (`src/schemas.py:31-37`) | عمومی؛ rate limit فقط بر مبنای phone |
| POST | `/api/auth/otp/verify` | `src/api/routes.py:217-230` | `OtpVerifyIn {phone,code,full_name}` (`src/schemas.py:40-43`) | `PhoneLoginOut` (`src/schemas.py:20-24`) | عمومی؛ OTP را بررسی می‌کند ولی session کاربر صادر نمی‌کند |
| GET | `/api/profile/{user_id}` | `src/api/routes.py:233-239` | path `user_id:int` | `ProfileV2Out` (`src/schemas.py:55-64`) | ندارد |
| POST | `/api/profile/{user_id}` | `src/api/routes.py:242-291` | path + `ProfileV2In` (`src/schemas.py:46-53`) | `ProfileV2Out` | ندارد |

واقعیت flow ذخیره identity:

- OTP request فقط `phone_otp_codes` را می‌سازد (`src/services/otp.py:141-177`).
- بعد از verify موفق، `users.phone/full_name/username` ایجاد یا update می‌شود (`src/api/routes.py:218-230`).
- profile تکمیلی در `user_profiles_v2` و `profile_builder_answers` ذخیره می‌شود و `users.profession` نیز sync می‌شود (`src/api/routes.py:248-291`).
- هیچ bearer token، session cookie یا ownership check برای routeهای profile وجود ندارد.

### دوره و ثبت‌نام Fake CMS

| Method | Path | محل تعریف | ورودی | response model/خروجی | احراز هویت/مجوز |
|---|---|---|---|---|---|
| GET | `/api/courses` | `src/api/routes.py:294-305` | ندارد | `list[CourseOut]` (`src/schemas.py:67-74`) | ندارد |
| POST | `/api/courses/{course_id}/enroll` | `src/api/routes.py:308-352` | path `course_id:int` + query `user_id:int` | `EnrollmentOut` (`src/schemas.py:77-84`) | ندارد |

این Routeها فقط metadata دوره published و enrollment را می‌دهند. Route واقعی برای دریافت `course_stage_contents`، تغییر `user_stage_progress`، آزمون یا certificate وجود ندارد.

### Onboarding قدیمی

| Method | Path | محل تعریف | ورودی | response model/خروجی | احراز هویت/مجوز |
|---|---|---|---|---|---|
| POST | `/api/onboarding/start` | `src/api/routes.py:355-365` | ندارد | `OnboardingStartOut` (`src/schemas.py:15-17`) | ندارد |
| GET | `/api/onboarding/{user_id}/state` | `src/api/routes.py:368-379` | path `user_id:int` | `OnboardingStateOut` (`src/schemas.py:87-90`) | ندارد |
| POST | `/api/onboarding/{user_id}/answer` | `src/api/routes.py:382-427` | path + `AnswerIn` (`src/schemas.py:93-95`) | `OnboardingAnswerOut` (`src/schemas.py:98-103`) | ندارد |

این flow هنوز فعال و قابل فراخوانی است. `start` یک `User()` بدون phone می‌سازد (`src/api/routes.py:356-361`) و پاسخ‌ها را با AI validation در `answers` ذخیره می‌کند. UI جدید در حالت session گم‌شده هنوز می‌تواند به این flow fallback کند (`src/templates/chat.html:1069-1089`).

### Training قدیمی/MVP

| Method | Path | محل تعریف | ورودی | response model/خروجی | احراز هویت/مجوز |
|---|---|---|---|---|---|
| POST | `/api/training/knowledge` | `src/api/routes.py:466-472` | `KnowledgeIn` (`src/schemas.py:140-143`) | `KnowledgeOut` (`src/schemas.py:146-147`) | بله؛ admin |
| POST | `/api/training/{user_id}/lesson` | `src/api/routes.py:475-508` | path `user_id:int` | `TrainingLessonOut` (`src/schemas.py:166-172`) | ندارد |
| POST | `/api/training/{user_id}/question` | `src/api/routes.py:511-534` | `TrainingQuestionIn` (`src/schemas.py:150-151`) | untyped `dict` | ندارد |
| POST | `/api/training/{user_id}/answer` | `src/api/routes.py:537-565` | `TrainingAnswerIn` (`src/schemas.py:154-157`) | untyped `dict` | ندارد |
| POST | `/api/training/{user_id}/message` | `src/api/routes.py:568-655` | `TrainingMessageIn` (`src/schemas.py:160-163`) | untyped `dict` با kindهای `retry/answer/complete/next_lesson` | ندارد |

این training از `user_progress` و `knowledge_documents` قدیمی استفاده می‌کند، نه engine بیست‌مرحله‌ای فاز ۲. هر پاسخ موفق 25 درصد اضافه می‌کند (`src/api/routes.py:554-557`, `src/api/routes.py:624-625`)، بنابراین مسیر عملی فعلی چهار جهش دارد.

## ۳. مدل‌های دیتابیس واقعی

تمام مدل‌ها در `src/models.py` هستند. وضعیت local هنگام ممیزی: PostgreSQL روی `localhost:5432` با database `zito_app`؛ مقدار password گزارش نشده است.

### `User` -> `users` (`src/models.py:9-25`)

| ستون | نوع | nullable | unique/index | default/FK |
|---|---|---:|---|---|
| `id` | Integer | false | PK | auto |
| `phone` | String(20) | true | unique + index | ندارد |
| `full_name` | String(255) | true | no | ندارد |
| `username` | String(100) | true | no | ندارد |
| `profession` | String(255) | true | no | ندارد |
| `created_at` | DateTime(timezone=True) | false | no | `server_default=now()` |
| `updated_at` | DateTime(timezone=True) | false | no | `server_default=now()`, `onupdate=now()` |

relationshipها:

- `answers` به `Answer.user`، با `cascade="all, delete-orphan"` (`src/models.py:20`).
- `progress` یک‌به‌یک به `UserProgress.user`، با delete-orphan (`src/models.py:21-25`).
- relationship ORM به profile/course enrollment/exam/certificate تعریف نشده است؛ فقط FK در مدل‌های دیگر وجود دارد.

### `Admin` -> `admins` (`src/models.py:28-36`)

| ستون | نوع | nullable | unique | default |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `username` | String(100) | false | yes | - |
| `password_hash` | String(255) | false | no | - |
| `is_active` | Boolean | false | no | Python `True` |
| `created_at` | DateTime(tz) | false | no | server `now()` |
| `updated_at` | DateTime(tz) | false | no | server `now()`, onupdate |

relationship تعریف نشده است.

### `Question` -> `questions` (`src/models.py:39-49`)

| ستون | نوع | nullable | unique | default |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `key` | String(80) | false | yes | - |
| `text` | Text | false | no | - |
| `sort_order` | Integer | false | yes | - |
| `is_active` | Boolean | false | no | Python `True` |
| `created_at` | DateTime(tz) | false | no | server `now()` |

relationship: `answers` به `Answer.question` (`src/models.py:49`).

### `Answer` -> `answers` (`src/models.py:52-64`)

| ستون | نوع | nullable | unique | default/FK |
|---|---|---:|---|---|
| `id` | Integer | false | PK | auto |
| `user_id` | Integer | false | no | FK `users.id`, `ON DELETE CASCADE` |
| `question_id` | Integer | false | no | FK `questions.id`, `ON DELETE CASCADE` |
| `answer_text` | Text | false | no | - |
| `is_valid` | Boolean | false | no | Python `True` |
| `validation_reason` | Text | true | no | - |
| `validated_at` | DateTime(tz) | false | no | server `now()` |

relationshipها: `user` و `question` با `back_populates` (`src/models.py:63-64`).

### `UserProgress` -> `user_progress` (`src/models.py:67-77`)

| ستون | نوع | nullable | unique | default/FK |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `user_id` | Integer | false | yes | FK `users.id`, CASCADE |
| `current_step` | Integer | false | no | Python `1` |
| `percentage` | Integer | false | no | Python `0` |
| `last_lesson` | Text | true | no | - |
| `updated_at` | DateTime(tz) | false | no | server `now()`, onupdate |

relationship: `user` به `User.progress` (`src/models.py:77`).

### `KnowledgeDocument` -> `knowledge_documents` (`src/models.py:80-87`)

| ستون | نوع | nullable | unique | default |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `title` | String(255) | false | no | - |
| `content` | Text | false | no | - |
| `tags` | String(255) | true | no | - |
| `created_at` | DateTime(tz) | false | no | server `now()` |

این جدول منبع RAG عملی فعلی است (`src/services/rag.py:21-37`).

### `Course` -> `courses` (`src/models.py:90-102`)

| ستون | نوع | nullable | unique | default |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `title` | String(255) | false | no | - |
| `slug` | String(120) | false | yes | - |
| `domain` | String(120) | false | no | - |
| `status` | String(40) | false | no | Python `"draft"` |
| `created_at` | DateTime(tz) | false | no | server `now()` |
| `updated_at` | DateTime(tz) | false | no | server `now()`, onupdate |

relationshipها: `versions` و `kb_documents` با cascade delete-orphan (`src/models.py:101-102`).

### `CourseVersion` -> `course_versions` (`src/models.py:105-120`)

قید یکتا: `(course_id, version_number)` با نام `uq_course_versions_course_version` (`src/models.py:107`).

| ستون | نوع | nullable | unique | default/FK |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `course_id` | Integer | false | composite | FK `courses.id`, CASCADE |
| `version_number` | Integer | false | composite | - |
| `status` | String(40) | false | no | Python `"draft"` |
| `source` | String(40) | false | no | Python `"seed"` |
| `published_at` | DateTime(tz) | true | no | - |
| `created_at` | DateTime(tz) | false | no | server `now()` |
| `updated_at` | DateTime(tz) | false | no | server `now()`, onupdate |

relationshipها: `course`، `stages` و `exams` (`src/models.py:118-120`).

### `CourseStageContent` -> `course_stage_contents` (`src/models.py:123-143`)

قید یکتا: `(course_version_id, stage_number)` (`src/models.py:125`).

| ستون | نوع | nullable | default/FK |
|---|---|---:|---|
| `id` | Integer | false | PK |
| `course_version_id` | Integer | false | FK `course_versions.id`, CASCADE |
| `stage_number` | Integer | false | - |
| `stage_type` | String(80) | false | - |
| `title` | String(255) | false | - |
| `content_json` | JSON | false | - |
| `status` | String(40) | false | Python `"approved"` |
| `ai_generation_status` | String(40) | false | Python `"seeded"` |
| `review_status` | String(40) | false | Python `"approved"` |
| `reviewed_by` | String(100) | true | - |
| `generated_at` | DateTime(tz) | true | - |
| `reviewed_at` | DateTime(tz) | true | - |
| `content_version` | Integer | false | Python `1` |
| `created_at` | DateTime(tz) | false | server `now()` |
| `updated_at` | DateTime(tz) | false | server `now()`, onupdate |

relationship: `course_version` (`src/models.py:143`).

### `CourseKbDocument` -> `course_kb_documents` (`src/models.py:146-157`)

| ستون | نوع | nullable | default/FK |
|---|---|---:|---|
| `id` | Integer | false | PK |
| `course_id` | Integer | false | FK `courses.id`, CASCADE |
| `title` | String(255) | false | - |
| `content` | Text | false | - |
| `tags` | String(255) | true | - |
| `source_type` | String(40) | false | Python `"seed"` |
| `created_at` | DateTime(tz) | false | server `now()` |

relationship: `course` (`src/models.py:157`). این جدول در RAG فعلی query نمی‌شود.

### `UserProfileV2` -> `user_profiles_v2` (`src/models.py:160-184`)

| ستون | نوع | nullable | unique | default/FK |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `user_id` | Integer | false | yes | FK `users.id`, CASCADE |
| `full_name` | String(255) | true | no | - |
| `age_range` | String(80) | true | no | - |
| `work_status` | String(120) | true | no | - |
| `work_domain` | String(255) | true | no | - |
| `referral_source` | String(120) | true | no | - |
| `daily_study_minutes` | Integer | true | no | - |
| `learning_goal` | String(255) | true | no | - |
| `experience_level` | String(80) | true | no | - |
| `preferred_learning_style` | String(120) | true | no | - |
| `learning_blocker` | String(255) | true | no | - |
| `commitment_level` | String(80) | true | no | - |
| `target_skill` | String(255) | true | no | - |
| `interested_domains` | JSON/list | true | no | - |
| `decision_factors` | JSON/list | true | no | - |
| `notification_channel` | String(80) | true | no | - |
| `reminder_frequency` | String(80) | true | no | - |
| `recommended_course_id` | Integer | true | no | FK `courses.id`, `ON DELETE SET NULL` |
| `recommended_track_label` | String(255) | true | no | - |
| `created_at` | DateTime(tz) | false | no | server `now()` |
| `updated_at` | DateTime(tz) | false | no | server `now()`, onupdate |

relationship ORM تعریف نشده است.

### `ProfileBuilderAnswer` -> `profile_builder_answers` (`src/models.py:187-195`)

قید یکتا: `(user_id, step_key)` (`src/models.py:189`).

| ستون | نوع | nullable | default/FK |
|---|---|---:|---|
| `id` | Integer | false | PK |
| `user_id` | Integer | false | FK `users.id`, CASCADE |
| `step_key` | String(120) | false | - |
| `answer_json` | JSON/dict | false | - |
| `created_at` | DateTime(tz) | false | server `now()` |

relationship ORM تعریف نشده است.

### `UserCourseEnrollment` -> `user_course_enrollments` (`src/models.py:198-213`)

قید یکتا: `(user_id, course_version_id)` (`src/models.py:200`).

| ستون | نوع | nullable | default/FK |
|---|---|---:|---|
| `id` | Integer | false | PK |
| `user_id` | Integer | false | FK `users.id`, CASCADE |
| `course_id` | Integer | false | FK `courses.id`, CASCADE |
| `course_version_id` | Integer | false | FK `course_versions.id`, CASCADE |
| `status` | String(40) | false | Python `"active"` |
| `current_stage_number` | Integer | false | Python `1` |
| `progress_percentage` | Integer | false | Python `0` |
| `enrolled_at` | DateTime(tz) | false | server `now()` |
| `completed_at` | DateTime(tz) | true | - |
| `updated_at` | DateTime(tz) | false | server `now()`, onupdate |

relationship: `stage_progress` با delete-orphan (`src/models.py:213`).

### `UserStageProgress` -> `user_stage_progress` (`src/models.py:216-229`)

قید یکتا: `(enrollment_id, stage_number)` (`src/models.py:218`).

| ستون | نوع | nullable | default/FK |
|---|---|---:|---|
| `id` | Integer | false | PK |
| `enrollment_id` | Integer | false | FK `user_course_enrollments.id`, CASCADE |
| `stage_number` | Integer | false | - |
| `status` | String(40) | false | Python `"not_started"` |
| `response_json` | JSON/dict | true | - |
| `started_at` | DateTime(tz) | true | - |
| `completed_at` | DateTime(tz) | true | - |
| `updated_at` | DateTime(tz) | false | server `now()`, onupdate |

relationship: `enrollment` (`src/models.py:229`).

### `Exam` -> `exams` (`src/models.py:232-243`)

| ستون | نوع | nullable | default/FK |
|---|---|---:|---|
| `id` | Integer | false | PK |
| `course_version_id` | Integer | false | FK `course_versions.id`, CASCADE |
| `title` | String(255) | false | - |
| `questions_json` | JSON/list | false | - |
| `passing_score` | Integer | false | Python `70` |
| `status` | String(40) | false | Python `"published"` |
| `created_at` | DateTime(tz) | false | server `now()` |

relationship: `course_version` (`src/models.py:243`).

### `ExamAttempt` -> `exam_attempts` (`src/models.py:246-258`)

| ستون | نوع | nullable | default/FK |
|---|---|---:|---|
| `id` | Integer | false | PK |
| `exam_id` | Integer | false | FK `exams.id`, CASCADE |
| `user_id` | Integer | false | FK `users.id`, CASCADE |
| `enrollment_id` | Integer | true | FK `user_course_enrollments.id`, CASCADE |
| `answers_json` | JSON/dict | false | - |
| `score` | Integer | true | - |
| `passed` | Boolean | false | Python `False` |
| `grading_feedback` | Text | true | - |
| `graded_by_ai_at` | DateTime(tz) | true | - |
| `created_at` | DateTime(tz) | false | server `now()` |

relationship ORM تعریف نشده است.

### `Certificate` -> `certificates` (`src/models.py:261-271`)

| ستون | نوع | nullable | unique | default/FK |
|---|---|---:|---:|---|
| `id` | Integer | false | PK | auto |
| `user_id` | Integer | false | no | FK `users.id`, CASCADE |
| `course_id` | Integer | false | no | FK `courses.id`, CASCADE |
| `course_version_id` | Integer | false | no | FK `course_versions.id`, CASCADE |
| `exam_attempt_id` | Integer | true | no | FK `exam_attempts.id`, SET NULL |
| `certificate_number` | String(120) | false | yes | - |
| `status` | String(40) | false | no | Python `"issued"` |
| `issued_at` | DateTime(tz) | false | no | server `now()` |

relationship ORM تعریف نشده است.

### `PhoneOtpCode` -> `phone_otp_codes` (`src/models.py:274-285`)

| ستون | نوع | nullable | unique/index | default |
|---|---|---:|---|---|
| `id` | Integer | false | PK | auto |
| `phone` | String(20) | false | index، نه unique | - |
| `code_hash` | String(128) | false | no | - |
| `provider` | String(40) | false | no | Python `"mock"` |
| `expires_at` | DateTime(tz) | false | no | - |
| `consumed_at` | DateTime(tz) | true | no | - |
| `attempt_count` | Integer | false | no | Python `0` |
| `last_sent_at` | DateTime(tz) | false | no | - |
| `created_at` | DateTime(tz) | false | no | server `now()` |

هیچ FK به `users` ندارد؛ اتصال فقط از طریق مقدار متنی phone است.

### وضعیت داده PostgreSQL محلی در لحظه ممیزی

این اعداد با query مستقیم `COUNT(*)` از database محلی `zito_app` به دست آمده‌اند:

| جدول | تعداد رکورد |
|---|---:|
| `admins` | 1 |
| `questions` | 2 |
| `knowledge_documents` | 6 |
| `courses` | 1 |
| `course_versions` | 1 |
| `course_stage_contents` | 20 |
| `course_kb_documents` | 3 |
| `exams` | 1 |
| `phone_otp_codes` | 8 |
| `users` | 0 |
| `answers` | 0 |
| `user_progress` | 0 |
| `user_profiles_v2` | 0 |
| `profile_builder_answers` | 0 |
| `user_course_enrollments` | 0 |
| `user_stage_progress` | 0 |
| `exam_attempts` | 0 |
| `certificates` | 0 |

## ۴. تاریخچه Migration های Alembic

زنجیره واقعی linear است:

```text
20260707_0001
  -> 20260714_0002
    -> 20260723_0003
      -> 20260726_0004
        -> 20260727_0005 (head)
```

1. `migrations/versions/20260707_0001_initial.py:13-14`
   - revision اولیه.
   - ساخت `users`, `questions`, `knowledge_documents`, `answers`, `user_progress` در `:19-64`.
   - downgrade معکوس در `:67-72`.

2. `migrations/versions/20260714_0002_admins.py:13-14`
   - وابسته به `20260707_0001`.
   - ساخت جدول `admins` در `:19-28`.

3. `migrations/versions/20260723_0003_phase2_schema.py:13-14`
   - وابسته به `20260714_0002`.
   - ساخت 11 جدول فاز ۲ در `:19-164`: `courses`, `course_versions`, `course_kb_documents`, `course_stage_contents`, `user_profiles_v2`, `profile_builder_answers`, `user_course_enrollments`, `user_stage_progress`, `exams`, `exam_attempts`, `certificates`.
   - downgrade به ترتیب معکوس در `:167-178`.

4. `migrations/versions/20260726_0004_phone_otp_codes.py:13-14`
   - وابسته به `20260723_0003`.
   - ساخت `phone_otp_codes` و index شماره در `:19-32`.

5. `migrations/versions/20260727_0005_user_phone_identity.py:13-14`
   - وابسته به `20260726_0004`.
   - افزودن `users.phone` در `:19-20`.
   - انتقال usernameهای شبیه شماره به phone و حذف duplicate ضمنی از طریق انتخاب `min(id)` در `:21-33`.
   - sync نام موجود به username در `:34-41`.
   - index یکتای `ix_users_phone` در `:42`.

بررسی drift انجام‌شده:

- `alembic heads` => `20260727_0005 (head)`.
- `alembic current` روی PostgreSQL محلی => `20260727_0005 (head)`.
- `python -m alembic check` => `No new upgrade operations detected`.
- نتیجه: بین metadata فعلی `src/models.py` و schema PostgreSQL محلی drift قابل تشخیص توسط Alembic وجود ندارد.
- drift production: `نامشخص`؛ در این ممیزی اتصال مستقیمی به production انجام نشد.

نکته اجرایی: `migrations/env.py:15-17` مقدار URL موجود در `alembic.ini:5` را با `settings.database_url` جایگزین می‌کند؛ بنابراین placeholder فایل ini منبع اتصال واقعی نیست.

## ۵. پیاده‌سازی واقعی لایه AI

### کد کامل client واقعی

فایل: `src/lib/arvan_client.py:1-156`

```python
import json
from typing import Any

import httpx

from src.config import get_settings


class ArvanAIError(RuntimeError):
    pass


def _mock_response(system_prompt: str, user_message: str) -> str:
    lowered = user_message.lower()
    try:
        message_data = json.loads(user_message)
    except json.JSONDecodeError:
        message_data = {}

    question_text = str(message_data.get("question") or "").strip()
    question_id = str(message_data.get("question_id") or "").strip()
    answer_text = str(
        message_data.get("answer")
        or message_data.get("message")
        or message_data.get("question")
        or user_message
    ).strip()
    normalized = answer_text.replace(" ", "").replace("\u200c", "").lower()

    invalid_tokens = {
        "asdf", "qwer", "test", "hello", "holo", "helo",
        "هلو", "چرت", "نمیدونم", "نمیدانم", "نمیخوام", "نمیخوام",
        "قوانینتروبگو", "قوانینروبگو", "توکیهستی", "prompt",
        "درخت", "فلان", "بهمان",
    }
    is_invalid = len(answer_text) < 3 or normalized in invalid_tokens or any(token in normalized for token in invalid_tokens)

    if "نام" in question_text or question_id == "1":
        system_like = ["قوانین", "rule", "prompt", "تو کی", "چه کار", "چیکار", "راهنما", "دستور", "درخت", "نمی خوام", "نمیخوام", "فلان"]
        words = [word for word in answer_text.replace("@", " ").split() if word.strip()]
        has_name_shape = len(words) >= 2 and not any(char.isdigit() for char in answer_text)
        if any(token in answer_text.lower() for token in system_like) or not has_name_shape:
            is_invalid = True

    if ("حسابداری" in question_text and "روانشناسی" in question_text and "حقوق" in question_text) or question_id == "2":
        allowed_tracks = ["حسابداری", "روانشناسی", "روان شناسی", "حقوق", "accounting", "psychology", "law"]
        if not any(track in answer_text.lower() for track in allowed_tracks):
            is_invalid = True

    if "passed" in system_prompt:
        return json.dumps(
            {
                "passed": not is_invalid,
                "feedback": "برای کامل تر شدن جواب، یک مثال کوتاه از همین درس بزن و بگو چرا این روش درست است." if is_invalid else "خوب پیش رفتی؛ آماده مرحله بعدی هستی.",
                "score": 82 if not is_invalid else 35,
            },
            ensure_ascii=False,
        )

    if "title" in system_prompt and "lesson" in system_prompt:
        user_context = str(message_data.get("user_context", ""))
        profession_context = user_context.lower()
        for line in user_context.splitlines():
            if line.lower().startswith("profession:"):
                profession_context = line.lower()
                break

        if "حقوق" in profession_context or "law" in profession_context:
            title = "هوش مصنوعی در بررسی اولیه قرارداد"
            lesson = "در این مرحله یاد می گیری از AI برای پیدا کردن ریسک های احتمالی یک بند قراردادی استفاده کنی، بدون اینکه خروجی را مشاوره حقوقی قطعی بدانی."
            exercise = "در دو جمله توضیح بده چرا خروجی AI در حقوق باید توسط متخصص انسانی بررسی شود."
        elif "روان" in profession_context or "psych" in profession_context:
            title = "هوش مصنوعی به عنوان دستیار یادگیری روانشناسی"
            lesson = "در این مرحله تمرین می کنی از AI برای ساخت سوال های باز و پاسخ همدلانه استفاده کنی، بدون تشخیص قطعی یا جایگزین کردن درمانگر."
            exercise = "در دو جمله توضیح بده چرا AI نباید تشخیص روانشناختی قطعی بدهد."
        else:
            title = "هوش مصنوعی در تحلیل اولیه حسابداری"
            lesson = "در این مرحله یاد می گیری از AI برای دسته بندی اولیه تراکنش ها و پیدا کردن ناهنجاری استفاده کنی، اما نتیجه را با سند و کنترل انسانی بررسی کنی."
            exercise = "در دو جمله توضیح بده چرا خروجی AI در حسابداری باید با سند مالی کنترل شود."

        return json.dumps(
            {
                "title": title,
                "lesson": lesson,
                "key_points": [
                    "AI دستیار تحلیل است، نه مرجع نهایی.",
                    "خروجی باید با منبع معتبر و قضاوت انسانی بررسی شود.",
                    "داده حساس را بدون مجوز وارد ابزار عمومی نکن.",
                ],
                "exercise": exercise,
                "check_question": exercise,
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "valid": not is_invalid,
            "reason": "پاسخ قابل بررسی است." if not is_invalid else "جواب به سوال فعلی مرتبط نیست. لطفا همان چیزی را که زیتو پرسیده وارد کن.",
            "normalized_answer": answer_text if not is_invalid else None,
        },
        ensure_ascii=False,
    )


async def ask_ai(
    system_prompt: str,
    user_message: str,
    *,
    temperature: float = 0.2,
    response_format: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()

    if settings.arvan_mock_ai:
        return _mock_response(system_prompt, user_message)

    if not settings.arvan_api_base_url or not settings.arvan_api_key:
        raise ArvanAIError("Arvan AIaaS is not configured. Set ARVAN_API_BASE_URL and ARVAN_API_KEY.")

    url = f"{settings.arvan_api_base_url.rstrip('/')}/chat/completions"
    payload: dict[str, Any] = {
        "model": settings.arvan_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    headers = {
        "Authorization": f"Bearer {settings.arvan_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.arvan_timeout_seconds, trust_env=False) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response is not None else ""
        raise ArvanAIError(f"Arvan AIaaS returned HTTP {exc.response.status_code}: {body}") from exc
    except (httpx.RequestError, ValueError) as exc:
        raise ArvanAIError(f"Could not call Arvan AIaaS ({type(exc).__name__}): {exc}") from exc

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ArvanAIError(f"Unexpected Arvan AIaaS response shape: {data}") from exc

    if not isinstance(content, str) or not content.strip():
        raise ArvanAIError("Arvan AIaaS returned an empty response.")
    return content.strip()
```

نکته: متغیر `lowered` در `src/lib/arvan_client.py:14` ساخته می‌شود ولی هیچ‌جا استفاده نمی‌شود.

### قرارداد شبکه Arvan

- URL نهایی: `{ARVAN_API_BASE_URL.rstrip('/')}/chat/completions` (`src/lib/arvan_client.py:121`).
- Method: `POST` (`:140`).
- Headerها: `Authorization: Bearer ...` و `Content-Type: application/json` (`:133-136`).
- payload پایه (`:122-129`):
  - `model`
  - `messages[0] = system`
  - `messages[1] = user`
  - `temperature`
  - `response_format` فقط در صورت ارسال caller (`:130-131`).
- استخراج پاسخ: `choices[0].message.content` (`:149-156`).
- timeout: از `ARVAN_TIMEOUT_SECONDS` و روی کل `AsyncClient` (`:139`).
- proxyهای محیطی: با `trust_env=False` غیرفعال شده‌اند (`:139`).
- retry: وجود ندارد.
- backoff/circuit breaker: وجود ندارد.
- logging/metrics: وجود ندارد.
- HTTP error: status و حداکثر 500 کاراکتر body را در `ArvanAIError` می‌گذارد (`:143-147`).
- response shape و empty content جداگانه بررسی می‌شوند (`:149-155`).

### محل‌های واقعی فراخوانی `ask_ai`

| هدف | محل |
|---|---|
| اعتبارسنجی پاسخ onboarding قدیمی | `src/services/validation.py:52-64`، call در `:58` |
| اعتبارسنجی سوال آموزشی | `src/services/validation.py:67-82`، call در `:74` |
| ارزیابی پاسخ تمرین | `src/services/validation.py:85-100`، call در `:92` |
| تولید lesson با user/RAG context | `src/services/training.py:134-161`، call در `:151` |
| پاسخ به سوال آموزشی با RAG | `src/services/training.py:164-180`، call در `:178` |

جست‌وجوی مستقیم شبکه نشان داد:

- تنها import/use از `httpx.AsyncClient` برای AI در `src/lib/arvan_client.py:4,139-140` است.
- تماس مستقیم دیگری با OpenAI/Anthropic/Arvan در فایل‌های Python یا HTML وجود ندارد.
- تماس خارجی مستقل sms.ir در `src/services/otp.py:78-138` است و AI محسوب نمی‌شود.
- نتیجه: همه تماس‌های AI موجود از `ask_ai` رد می‌شوند.

### رفتار fallback و RAG واقعی

- `validate_initial_answer` fallback ندارد؛ خطا به route و سپس HTTP 503 می‌رسد (`src/api/routes.py:393-396`).
- `validate_training_question` تمام Exceptionها را می‌گیرد و heuristic محلی اجرا می‌کند (`src/services/validation.py:73-81`).
- `evaluate_training_answer` تمام Exceptionها را می‌گیرد و heuristic محلی اجرا می‌کند (`src/services/validation.py:91-95`).
- `generate_lesson` تمام Exceptionها را می‌گیرد و fallback lesson می‌دهد (`src/services/training.py:150-160`).
- `answer_training_question` تمام Exceptionها را می‌گیرد و fallback متنی می‌دهد (`src/services/training.py:177-180`).
- بنابراین routeهای training معمولاً خرابی AI را به caller نشان نمی‌دهند.

RAG واقعی:

- query فقط روی `KnowledgeDocument` است (`src/services/rag.py:4,21-37`).
- termها از split ساده متن ساخته می‌شوند و حداکثر پنج term به `ILIKE` روی title/content/tags تبدیل می‌شوند (`:22-32`).
- حداکثر سه سند بازگردانده می‌شود و از هر سند 1600 کاراکتر ارسال می‌شود (`:21,37`).
- embedding، vector database، reranking، chunking و course scoping وجود ندارد.
- `course_kb_documents` فاز ۲ در RAG فعلی مصرف نمی‌شود.

سلامت واقعی endpoint Arvan در زمان این ممیزی: `نامشخص`؛ تست‌ها با `ARVAN_MOCK_AI=true` اجرا شدند.

## ۶. متغیرهای Config/.env

منبع تعریف همه متغیرها `src/config.py:8-41` است. Pydantic فایل `.env` را با UTF-8 می‌خواند (`src/config.py:39`).

| نام متغیر | تعریف | محل استفاده واقعی |
|---|---|---|
| `APP_NAME` | `src/config.py:9` | title برنامه در `src/main.py:13-14` |
| `APP_ENV` | `src/config.py:10` | validation production و propertyها در `src/config.py:41-63`؛ seed admin در `src/seed.py:175-177` |
| `AUTO_CREATE_TABLES` | `src/config.py:11` | startup `create_all + seed` در `src/main.py:25-30` |
| `DATABASE_URL` | `src/config.py:13` | engine در `src/db.py:13-15`؛ Alembic در `migrations/env.py:15-23` |
| `ARVAN_API_BASE_URL` | `src/config.py:15` | ساخت URL و config guard در `src/lib/arvan_client.py:118-121` |
| `ARVAN_API_KEY` | `src/config.py:16` | Bearer header در `src/lib/arvan_client.py:118-135` |
| `ARVAN_MODEL` | `src/config.py:17` | payload model در `src/lib/arvan_client.py:123` |
| `ARVAN_TIMEOUT_SECONDS` | `src/config.py:18` | timeout HTTP در `src/lib/arvan_client.py:139` |
| `ARVAN_MOCK_AI` | `src/config.py:19` | انتخاب mock/real در `src/lib/arvan_client.py:115-116` و production guard `src/config.py:49` |
| `ADMIN_USERNAME` | `src/config.py:21` | فقط seed اولین admin در `src/seed.py:171-179` |
| `ADMIN_PASSWORD` | `src/config.py:22` | فقط seed اولین admin و safe-password check در `src/config.py:61-63`, `src/seed.py:175-179` |
| `ADMIN_SESSION_SECRET` | `src/config.py:23` | امضای cookie admin `src/security.py:49-52` و HMAC کد OTP `src/services/otp.py:47-51` |
| `ADMIN_SESSION_DAYS` | `src/config.py:24` | expiration و max_age cookie در `src/security.py:55-70` |
| `OTP_MOCK` | `src/config.py:26` | provider/send/mock_code در `src/services/otp.py:152-176` |
| `OTP_CODE_DIGITS` | `src/config.py:27` | طول کد، clamp بین 4 و 8 در `src/services/otp.py:54-58` |
| `OTP_EXPIRE_MINUTES` | `src/config.py:28` | expires_at و response در `src/services/otp.py:157,173` |
| `OTP_MAX_ATTEMPTS` | `src/config.py:29` | توقف verify در `src/services/otp.py:188-195` |
| `OTP_RESEND_SECONDS` | `src/config.py:30` | rate limit و response در `src/services/otp.py:145-149,174` |
| `SMSIR_API_URL` | `src/config.py:32` | URL `/send/verify` در `src/services/otp.py:99` |
| `SMSIR_API_KEY` | `src/config.py:33` | header `X-API-KEY` در `src/services/otp.py:94-98` |
| `SMSIR_TEMPLATE_ID` | `src/config.py:34` | payload templateId در `src/services/otp.py:80-87` |
| `SMSIR_CODE_PARAMETER` | `src/config.py:35` | نام parameter در `src/services/otp.py:87-91` |
| `SMSIR_TIMEOUT_SECONDS` | `src/config.py:36` | timeout HTTPSConnection در `src/services/otp.py:101-107,124-131` |

production validator فقط این شرایط را enforce می‌کند (`src/config.py:41-56`):

- `ADMIN_SESSION_SECRET` placeholder نباشد.
- اگر Arvan mock نیست، URL و key موجود باشند.
- اگر OTP mock نیست، sms.ir key و template موجود باشند.

مقدار `ADMIN_PASSWORD` در validator اصلی reject نمی‌شود؛ فقط هنگام seed اولین admin در production کنترل می‌شود (`src/seed.py:176-177`).

بررسی tracked secrets:

- `.env` tracked نیست و توسط `.gitignore:2` ignore شده است.
- `.secrets/` tracked نیست (`.gitignore:5`).
- فایل‌های DB/log/key/certificate نیز ignore شده‌اند (`.gitignore:6-10`, `:24-29`).
- scan فایل‌های tracked مقدار واضحی شبیه secret واقعی نشان نداد؛ موارد موجود placeholder یا test value بودند.
- بررسی کامل همه objectهای تاریخچه Git برای secretهای قبلاً حذف‌شده در این ممیزی انجام نشد؛ وضعیت تاریخچه عمیق secretها `نامشخص` است.

## ۷. وضعیت تست‌ها

فرمان اجراشده:

```text
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

نتیجه واقعی در 2026-07-27:

```text
Ran 17 tests in 2.592s
OK
```

هشدارها:

- `DeprecationWarning` مربوط به `asyncio.iscoroutinefunction` در Starlette روی Python 3.14.
- `ResourceWarning: unclosed database` برای یک connection SQLite پس از پایان suite.

### فایل‌ها و پوشش واقعی

| فایل | تعداد test | پوشش واقعی |
|---|---:|---|
| `tests/test_arvan_client.py` | 1 | فقط مسیر mock `ask_ai` و JSON identity معتبر (`:12-34`)؛ شبکه واقعی/timeout/error shape تست نمی‌شود |
| `tests/test_health.py` | 1 | `GET /health` با SQLite و پاسخ database ok (`:14-24`) |
| `tests/test_otp.py` | 7 | request/verify mock، hash نشدن plain code، ساخت فوری user، ورود تکراری، رد route قدیمی، رد OTP غلط/reuse، قرارداد adapter sms.ir و خطاهای logical/non-ASCII (`:19-232`) |
| `tests/test_phase2_seed.py` | 1 | idempotent seed، یک course/version، 20 stage، سه KB و exam (`:14-58`) |
| `tests/test_profile_courses.py` | 3 | ذخیره profile+builder answer، پذیرش نام تک‌بخشی، list course و idempotent enroll (`:17-113`) |
| `tests/test_ui_contract.py` | 2 | assert رشته‌ای روی ترتیب input، autofill، payload full_name و welcome copy (`:12-38`) |
| `tests/test_validation.py` | 2 | identity معتبر/نامرتبط در mock AI flow قدیمی (`:11-33`) |
| **جمع** | **17** | - |

زیرساخت تست:

- `tests/_env.py:5-27` تمام suite را به SQLite file و mock AI/OTP هدایت می‌کند.
- CI در `.github/workflows/tests.yml:1-40` روی Ubuntu و Python 3.12 همین unittestها را اجرا می‌کند.
- وضعیت آخرین اجرای آنلاین GitHub Actions در زمان این ممیزی: `نامشخص`.

### بخش‌های مهم بدون تست مستقیم

- تمام routeهای admin: login/logout/me/list/get/update/delete.
- `src/security.py`: password hashing/verification، امضای cookie، expiration، inactive admin، tamper.
- HTML routeهای `/chat` redirect، `/admin` redirect و static assets.
- onboarding routeهای `/api/onboarding/start|state|answer` در سطح HTTP.
- training routeهای `lesson/question/answer/message`.
- `src/services/training.py`: fallback lesson، تشخیص question، RAG answer.
- `src/services/rag.py`: retrieval و query behavior.
- Arvan واقعی: HTTP 4xx/5xx، timeout، malformed JSON، response shape و retry.
- sms.ir واقعی روی شبکه؛ تست adapter با patch است، نه provider live.
- rate limit/resend/expiry/max-attempt OTP در edge caseهای زمانی و concurrency.
- PostgreSQL در CI؛ همه unit/integration testهای خودکار از SQLite استفاده می‌کنند.
- اجرای migration upgrade/downgrade در CI.
- cascade behavior PostgreSQL، unique conflict concurrent و transaction rollback.
- route یا engine برای 20 stage، `UserStageProgress`, exam grading و certificate؛ چون implementation route وجود ندارد.
- authorization/IDOR user؛ چون user auth وجود ندارد.
- CSRF و cookie flags.
- accessibility و تست مرورگر واقعی؛ UI tests فقط string assertion هستند.

## ۸. وابستگی‌ها (Dependencies)

فایل `requirements.txt:1-8` به‌صورت کامل:

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
SQLAlchemy==2.0.36
psycopg[binary]==3.2.13
alembic==1.14.0
pydantic-settings==2.7.0
httpx==0.28.1
python-dotenv==1.0.1
```

- `pyproject.toml`: وجود ندارد.
- `requirements-dev.txt`: وجود ندارد.
- local interpreter واقعی: Python `3.14.4`.
- CI interpreter: Python `3.12` (`.github/workflows/tests.yml:15-18`).
- PostgreSQL client محلی: `18.4`.
- نسخه production PostgreSQL: `نامشخص` در این ممیزی؛ مقدار موجود در `PROJECT_REPORT.md` تاریخی است و مستقیم بررسی نشد.

## ۹. مغایرت با اسناد قبلی پروژه

### `PROJECT_CONTEXT.md`

1. `PROJECT_CONTEXT.md:4` می‌گوید هر پاسخ profile با Arvan validate می‌شود. flow واقعی فاز ۲ در `src/api/routes.py:217-291` هیچ AI validation برای نام/پروفایل ندارد. خود سند در `PROJECT_CONTEXT.md:9` و `:35-44` خلاف جمله خط 4 را بیان می‌کند.

2. `PROJECT_CONTEXT.md:65-77` flow جاری را `/chat` + دو سوال AI + training قدیمی معرفی می‌کند. واقعیت:
   - `/chat` فقط redirect به `/app/` است (`src/main.py:45-48`).
   - ورودی اصلی از landing نام/phone/OTP است (`landing/zito.html:1153-1200`).
   - سوال‌های profile جدید بدون AI در chat جمع می‌شوند (`src/templates/chat.html:893-997`).
   - flow onboarding قدیمی هنوز در کد هست، اما flow اصلی اعلام‌شده landing نیست.

3. `PROJECT_CONTEXT.md:84-86` می‌گوید admin با HTTP Basic و env username/password محافظت می‌شود. واقعیت login دیتابیس‌محور + password hash + cookie signed است (`src/api/routes.py:173-179`, `src/security.py:55-108`). env admin فقط seed اولیه است (`src/seed.py:171-179`).

4. نمودار `PROJECT_CONTEXT.md:55-63`، `users -> phone_otp_codes` را به شکل رابطه نشان می‌دهد. مدل `PhoneOtpCode` هیچ `user_id` یا FK ندارد (`src/models.py:274-285`).

5. `PROJECT_CONTEXT.md:108` می‌گوید محتوای واقعی بعداً می‌تواند وارد `knowledge_documents` شود، اما contract فاز ۲ در همان سند `course_kb_documents` را تعریف کرده (`:49-53`). RAG فعلی همچنان old table را مصرف می‌کند (`src/services/rag.py:4,21-37`)؛ اتصال KB دوره هنوز پیاده نشده است.

6. `PROJECT_CONTEXT.md:128-146` فهرست کامل route نیست. موارد `/`, `/app/`, `/admin/login`, admin login/logout/me/get user، onboarding state، training knowledge و routeهای auto docs را ندارد.

7. `PROJECT_CONTEXT.md:46-63` contract 20-stage را درست توصیف می‌کند، اما در کد فقط schema/seed/enrollment وجود دارد؛ route خواندن stage، stage progression، exam و certificate وجود ندارد.

### `README.md`

1. `README.md:6-9` می‌گوید onboarding پاسخ‌ها را با AI بررسی و مستقیماً وارد training می‌کند. این فقط flow قدیمی است؛ flow اصلی OTP/profile جدید AI validation ندارد.
2. `README.md:15` Chat را `/chat` معرفی می‌کند، در حالی که route canonical فعلی `/app/` است و `/chat` redirect می‌شود.
3. `README.md:11` درباره RAG ساده درست است، اما مشخص نمی‌کند RAG از KB قدیمی global استفاده می‌کند، نه KB اختصاصی course.

### `SETUP.md`

1. flow browser در `SETUP.md:33-42` با UI جدید و OTP همخوان است.
2. دستور SQLite در `SETUP.md:8-16` `AUTO_CREATE_TABLES=false` می‌گذارد و سپس Alembic اجرا می‌کند؛ برای DB تازه قابل اجرا است، اما برای SQLite قدیمی بدون `alembic_version` ممکن است خطای «table already exists» ایجاد کند. سند روش stamp/recreate را توضیح نمی‌دهد.
3. credentialهای admin خطوط `29-31` فقط وقتی درست‌اند که seed اولیه با همان env انجام شده باشد؛ تغییر env رمز admin موجود را تغییر نمی‌دهد (`src/seed.py:171-179`).

### `PROJECT_REPORT.md`

موارد عمدتاً همخوان:

- flow OTP/profile در `PROJECT_REPORT.md:17,52`.
- RAG واژگانی old table در `:25,786-798`.
- schema فاز ۲ و seed 20 مرحله در `:48-52`.
- ریسک cookie و progress چهارمرحله‌ای در `:1219-1240`.

موارد قدیمی یا اثبات‌نشده:

- درصد تکمیل و deploy در `PROJECT_REPORT.md:35-48` تخمینی/تاریخی است و از کد قابل اثبات نیست.
- production IP/Nginx/systemd/SSL در `PROJECT_REPORT.md:960-1073` در این ممیزی مستقیم بررسی نشد؛ وضعیت فعلی `نامشخص`.
- Git status/remote head ذکرشده در `PROJECT_REPORT.md:960-963` قدیمی‌تر از commit فعلی `6fb0d46` است.
- فهرست dependencyهای transitive در `PROJECT_REPORT.md:267-312` از `requirements.txt` مستقیم استخراج نشده است؛ قرارداد dependency رسمی فعلی فقط هشت مورد section 8 است.
- خود `PROJECT_REPORT.md:1263` مغایرت HTTP Basic در `PROJECT_CONTEXT.md` را قبلاً ثبت کرده، اما `PROJECT_CONTEXT.md` هنوز اصلاح نشده است.

## ۱۰. TODO / FIXME / کد نیمه‌کاره

نتیجه جست‌وجوی `TODO|FIXME|HACK|XXX|NotImplemented`:

- marker واقعی TODO/FIXME/HACK در source/migration/test پیدا نشد.
- block بزرگ commented-out پیدا نشد.

موارد `pass` عمدی و نه TODO:

- `src/db.py:10`: بدنه خالی `Base`.
- `src/lib/arvan_client.py:10`: exception class `ArvanAIError`.
- `src/services/otp.py:19`: exception class `OtpError`.

کد یا contract نیمه‌فعال:

1. `openProfileModal` در `src/templates/chat.html:998-1009` تعریف شده ولی هیچ call site ندارد. modal قدیمی profile در `:674-714` و submit handler آن در `:1206-1230` باقی مانده، در حالی که flow فعال از profile chat استفاده می‌کند (`:932-997`).

2. `CourseStageContent` در `src/api/routes.py:12` import شده ولی خود class مستقیماً در routeها مصرف نمی‌شود؛ stage count فقط از relationship loadشده محاسبه می‌شود (`:147-164`).

3. مدل‌های `UserStageProgress`, `ExamAttempt`, `Certificate` فقط schema هستند و route/service عملی ندارند (`src/models.py:216-271`).

4. `CourseKbDocument` فقط seed و relationship دارد (`src/seed.py:280-291`)؛ RAG آن را نمی‌خواند.

5. `CourseStageContent`های 20گانه فقط seed می‌شوند (`src/seed.py:242-278`)؛ UI/API engine مرحله‌ای برای مصرف `content_json` وجود ندارد.

6. `Exam` seed می‌شود (`src/seed.py:293-320`) ولی endpoint اجرای exam/grading وجود ندارد.

7. `fallback_training_answer(user, question)` در `src/services/training.py:102-119` پارامتر `question` را مصرف نمی‌کند.

8. متغیر `lowered` در `src/lib/arvan_client.py:14` استفاده نمی‌شود.

9. مسیر onboarding قدیمی و مسیر OTP/profile جدید هر دو فعال‌اند؛ قدیمی را نمی‌توان dead نامید چون routeها و fallback UI هنوز آن را صدا می‌زنند.

## ۱۱. آخرین وضعیت Git

وضعیت زمان ممیزی:

- branch: `main`.
- HEAD: `6fb0d46d274b64990a7066d763c33e58211c65ad`.
- working tree قبل از ساخت همین فایل: clean.
- author config: `TheAlta` با noreply GitHub email.
- `origin` fetch: `TheAlta/ZitoApp`.
- `origin` دو push URL دارد: `TheAlta/ZitoApp` و `elmsaz/elmsazZito`.
- remote جداگانه `elmsaz` نیز به `elmsaz/elmsazZito` اشاره می‌کند.
- هر دو remote main پیش از ساخت این گزارش روی `6fb0d46` بودند.

خروجی کامل `git log --oneline -30`:

```text
6fb0d46 Save user identity immediately after OTP
87a13df Polish Sprint 1 entry experience
a97b62d Track SMS credentials in local vault inventory
6bb0805 Complete Sprint 1 user identity flow
e24fecf Collect learner name during OTP entry
1a6473d Move phase 2 profile setup into chat flow
bee46c5 Validate smsir API key header value
1c4e3f2 Handle non JSON API errors in UI
eb57db3 Add Sprint 1 OTP profile enrollment flow
e07a365 Use standard HTTPS client for smsir OTP
c4fc72e Validate smsir OTP response contract
daae9da Add OTP foundation with smsir adapter
161459c Recover chat when saved user is deleted
cceb2fd Add phase 2 schema and fake course seed
0e5ea6f Add tests CI and proprietary license
cab3ab8 Update report for phase 2 architecture
5c0ab1c Add technical project report
aab3cbf Merge elmsaz repository history
76091ee Initial commit
4b02592 Add local secrets manager
660ab15 Relax production admin env guard
9946fde Harden environment and secret handling
558867b Unify Persian frontend font
0c3a37d Use landing artwork in chat UI
cf55c97 Unify UI typography with Yekan
2aa6841 Redesign training chat flow with planet stage
a7a9461 Use clean app URL for chat entry
c28e85d Add resilient training fallback flow
964e902 Use transparent landing artwork
655db1f Blend landing image backgrounds
```

بیشترین churn در همین 30 commit:

| فایل | تعداد commit درگیر | added | deleted | churn |
|---|---:|---:|---:|---:|
| `PROJECT_REPORT.md` | 6 | 1300 | 36 | 1336 |
| `src/templates/chat.html` | 13 | 775 | 58 | 833 |
| `landing/zito.html` | 11 | 293 | 84 | 377 |
| `tests/test_otp.py` | 6 | 275 | 43 | 318 |
| `src/api/routes.py` | 5 | 246 | 26 | 272 |
| `src/services/otp.py` | 4 | 210 | 11 | 221 |
| `src/seed.py` | 2 | 214 | 2 | 216 |
| `src/models.py` | 3 | 200 | 1 | 201 |
| `migrations/versions/20260723_0003_phase2_schema.py` | 1 | 178 | 0 | 178 |
| `tools/zito-secrets.ps1` | 2 | 173 | 1 | 174 |
| `src/services/training.py` | 1 | 125 | 3 | 128 |
| `tests/test_profile_courses.py` | 3 | 117 | 4 | 121 |
| `src/schemas.py` | 4 | 76 | 18 | 94 |
| `PROJECT_CONTEXT.md` | 5 | 73 | 5 | 78 |
| `SECURITY.md` | 3 | 71 | 0 | 71 |

تفسیر خام: بیشترین تغییر اجرایی روی دو frontend بزرگ و سپس OTP/API بوده است. `PROJECT_REPORT.md` به‌تنهایی بیشترین churn را دارد و نباید به‌عنوان source of truth جایگزین کد شود.

## ۱۲. نقاط ریسک/ناسازگاری فنی که خودت در کد می‌بینی

### ریسک بحرانی: نبود session/authorization کاربر

OTP فقط `user_id` برمی‌گرداند (`src/api/routes.py:217-230`) و frontend آن را در `localStorage` می‌گذارد (`landing/zito.html:1194-1196`). بعد از آن، routeهای profile/course/training فقط `user_id` قابل حدس را می‌گیرند و هیچ token/cookie/ownership check ندارند (`src/api/routes.py:233-352`, `:475-655`). نتیجه:

- خواندن profile هر user با ID ممکن است.
- تغییر profile، enroll کردن و اجرای training برای user دیگر ممکن است.
- این یک IDOR/authorization gap واقعی است، حتی اگر URL ظاهری `/app/` query نداشته باشد.

### دو معماری رقیب هم‌زمان

نسل قدیمی:

```text
questions -> answers
knowledge_documents
user_progress (25% increments)
AI onboarding
```

نسل فاز ۲:

```text
user_profiles_v2
courses -> course_versions -> course_stage_contents
course_kb_documents
user_course_enrollments -> user_stage_progress
exams -> exam_attempts -> certificates
```

UI فعلی identity/profile/enrollment را از نسل جدید می‌گیرد، ولی lesson/RAG/progress را از نسل قدیمی اجرا می‌کند (`src/templates/chat.html:1120-1155`). این ترکیب باعث می‌شود:

- course دارای 20 stage باشد ولی آموزش عملی چهار گام 25درصدی باشد.
- KB دوره seed شده باشد ولی AI از KB global قدیمی بخواند.
- enrollment progress و `user_progress` از هم جدا و ناسازگار شوند.

### RAG بدون course isolation

`retrieve_context` فقط `knowledge_documents` را query می‌کند (`src/services/rag.py:21-37`). هیچ `course_id`, `course_version_id` یا published-version filter ندارد. در نتیجه ناظر دوره فاز ۲ هنوز واقعاً course-scoped نیست و می‌تواند context حوزه دیگر را بگیرد.

### swallow شدن خطاهای AI

`except Exception` در `src/services/validation.py:73-81,91-95` و `src/services/training.py:150-154,177-180` timeout، auth error، malformed response و bug برنامه را یکسان می‌گیرد و fallback می‌دهد. بدون log/metric، ممکن است Arvan مدت طولانی خراب باشد ولی UI ظاهراً ادامه دهد. این رفتار برای availability مفید است، اما monitoring و صحت الزام «AI ناظر» را تضعیف می‌کند.

### نبود retry و observability در client

`ask_ai` فقط یک POST دارد (`src/lib/arvan_client.py:138-147`). retry/backoff، request ID، structured logging، latency metric، token usage و circuit breaker وجود ندارد. خطای provider body تا 500 کاراکتر وارد exception می‌شود؛ اگر بعداً log شود ممکن است داده حساس response وارد log گردد.

### admin cookie برای HTTPS ناامن تنظیم شده

`secure=False` به‌صورت ثابت در `src/security.py:62-71` است؛ حتی `APP_ENV=production` آن را تغییر نمی‌دهد. در production باید cookie فقط روی HTTPS ارسال شود. همچنین:

- default عمر session برابر 3650 روز است (`src/config.py:24`).
- CSRF token برای PUT/DELETE/POST admin وجود ندارد.
- login admin rate limit ندارد.
- session server-side قابل revoke نیست، جز disable/delete admin یا تغییر secret.

### استفاده مشترک از یک secret برای دو هدف

`ADMIN_SESSION_SECRET` هم cookie admin را امضا می‌کند (`src/security.py:49-52`) و هم OTP را hash می‌کند (`src/services/otp.py:47-51`). تفکیک `OTP_HASH_SECRET` و `ADMIN_SESSION_SECRET` blast radius و rotation را بهتر می‌کند.

### duplication و امکان ناسازگاری profile

نام در سه محل ذخیره می‌شود:

- `users.full_name/username`
- `user_profiles_v2.full_name`
- `profile_builder_answers["full_name"]`

حوزه نیز در `users.profession`, `user_profiles_v2.work_domain` و builder answer تکرار می‌شود (`src/api/routes.py:253-287`). OTP login نام جدید را فقط روی `users` می‌نویسد (`:225-229`)؛ اگر profile قبلی وجود داشته باشد، `_profile_out` نام profile را بر نام users ترجیح می‌دهد (`:129-143`). بنابراین کاربر قدیمی ممکن است نام جدید OTP را در UI نبیند.

### admin panel داده فاز ۲ را کامل نشان نمی‌دهد

`UserOut` فقط users و legacy answers را خروجی می‌دهد (`src/schemas.py:116-123`, `src/api/routes.py:81-90`). پنل admin profile v2، phone OTP status، enrollment، stage progress، exam و certificate را نمایش/ویرایش نمی‌کند. پس «کاربران موجود ولی اطلاعات ناقص در پنل» از contract فعلی قابل انتظار است.

### CMS/20-stage فقط schema و seed است

هیچ CRUD واقعی CMS، review/publish endpoint، async generation job، stage retrieval API یا operator workflow وجود ندارد. فیلدهای status/review در DB هستند (`src/models.py:123-141`) ولی منطق transition ندارند. داده فعلی در seed مستقیماً approved/published می‌شود (`src/seed.py:207-320`).

### آزمون و مدرک فقط مدل هستند

`ExamAttempt` و `Certificate` model/migration دارند (`src/models.py:246-271`) ولی:

- route شروع/submit exam وجود ندارد.
- AI grading service وجود ندارد.
- certificate number generation/issuance وجود ندارد.
- authorization دانلود/مشاهده certificate وجود ندارد.

### انتخاب course در UI deterministic محصولی نیست

UI اولین course برگشتی را انتخاب می‌کند (`src/templates/chat.html:1120-1128`) و API بر اساس `Course.id` sort می‌کند (`src/api/routes.py:296-303`). profile domain/recommendation برای انتخاب course مصرف نمی‌شود. با اضافه شدن دوره دوم، کاربر الزاماً دوره مناسب خود را نمی‌گیرد.

### مسیر fallback می‌تواند user بدون phone بسازد

اگر localStorage session وجود نداشته باشد، UI می‌تواند `/api/onboarding/start` را صدا بزند (`src/templates/chat.html:1069-1089`) و `User()` بدون phone ساخته می‌شود (`src/api/routes.py:355-361`). این با مدل جدید «phone هویت login» ناسازگار است و userهای بدون phone تولید می‌کند.

### rate limiting OTP محدود است

rate limit فقط آخرین OTP همان phone را بررسی می‌کند (`src/services/otp.py:141-149`):

- per-IP/device/global limit ندارد.
- cleanup کدهای expired/consumed ندارد.
- uniqueness یا lock برای requestهای concurrent ندارد.
- تعداد attempt فقط در verify غلط commit می‌شود (`:180-199`).

### `create_all` در کنار Alembic

اگر `AUTO_CREATE_TABLES=true` باشد، startup مستقیماً `Base.metadata.create_all` اجرا می‌کند (`src/main.py:25-30`). هم‌زمان پروژه Alembic دارد. این دو مسیر schema management می‌توانند در DBهای قدیمی یا production رفتار متفاوت بسازند. production باید migration-controlled و `AUTO_CREATE_TABLES=false` باشد.

### تفاوت محیط تست و اجرا

- local interpreter فعلی Python 3.14.4 است.
- CI Python 3.12 است.
- suite از SQLite استفاده می‌کند، ولی اجرای جدی PostgreSQL است.
- warning فعلی Starlette روی 3.14 و connection بسته‌نشده SQLite نشان می‌دهد سازگاری/cleanup کاملاً تمیز نیست.
- constraintها، JSON، timezone، cascade و concurrency PostgreSQL در CI پوشش داده نمی‌شوند.

### front-end بزرگ و بدون build/module boundary

`landing/zito.html` و به‌خصوص `src/templates/chat.html` HTML/CSS/JS یکپارچه و بزرگ هستند. chat طی 13 commit اخیر بیشترین تغییر اجرایی را داشته است. پیامد:

- stateهای onboarding/profile/planet/training/modal در یک فایل مشترک‌اند.
- کد modal قدیمی unreachable باقی مانده است.
- تست UI فقط string matching است و regression رفتاری مرورگر را نمی‌گیرد.
- refactor بعدی باید با browser E2E انجام شود تا رفتار فعلی شکسته نشود.

### وضعیت secretها

در snapshot tracked فعلی secret واضح hardcode نشده و ignore ruleها درست‌اند. با این حال:

- secretهایی که قبلاً در chat یا بیرون Git منتشر شده‌اند باید rotate شوند؛ کد نمی‌تواند این را تضمین کند.
- scan کامل Git history و provider dashboard در این ممیزی انجام نشده است.
- وضعیت rotation واقعی Arvan/sms.ir/server: `نامشخص`.

### وضعیت production و deploy

کد repository فایل deploy declarative مانند Dockerfile، compose، Ansible/Terraform، unit file یا Nginx config tracked ندارد. اطلاعات deployment فقط در `PROJECT_REPORT.md` تاریخی است. بنابراین از روی repository نمی‌توان تضمین کرد:

- production روی کدام commit است.
- migration `20260727_0005` روی production اجرا شده یا نه.
- `.env` production کامل و امن است یا نه.
- service و SSL اکنون سالم‌اند یا نه.

وضعیت production در این ممیزی: `نامشخص`.
