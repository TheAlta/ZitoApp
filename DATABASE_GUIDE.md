# راهنمای فنی دیتابیس و مدل داده زیتو

> وضعیت سند: بر اساس کد موجود در درخت کاری پروژه و migration head با revision `20260819_0014` تهیه شده است.
>
> این سند «قرارداد فنی برنامه» را توضیح می‌دهد؛ یعنی آنچه `src/models.py` و migrationهای Alembic تعریف می‌کنند. تعداد واقعی رکوردهای یک محیط محلی یا production از روی کد قابل تشخیص نیست و باید مستقیماً از همان دیتابیس خوانده شود.

## 1. هدف و محدوده

دیتابیس زیتو فقط محل نگهداری نام و شماره کاربر نیست. چهار دامنه اصلی را پشتیبانی می‌کند:

1. **هویت و دسترسی:** ورود OTP، جلسه کاربر، حساب مدیر، حذف نرم و مسدودسازی.
2. **محتوای آموزشی:** دوره، نسخه دوره، سرفصل، 20 قالب آموزشی و محتوای تاییدشده هر قالب.
3. **مسیر یادگیری:** ثبت‌نام کاربر در یک نسخه مشخص از دوره و پیشرفت او در مراحل.
4. **RAG و AI Coach:** سندهای پایگاه دانش، chunkها، embeddingها، صف ایندکس، گفت‌وگوها و ردپای retrieval.

منبع حقیقت مدل داده [src/models.py](src/models.py) است. migrationها در [migrations/versions](migrations/versions) تاریخچه تبدیل schema را نگه می‌دارند. سند قدیمی `DATABASE_V2_DESIGN.md` طرح تاریخی/پیشنهادی است و نباید به جای مدل‌های فعلی مبنای پیاده‌سازی قرار گیرد.

## 2. معماری لایه داده

```text
FastAPI route / service
        |
        |  SQLAlchemy 2 ORM model + Session
        v
src/db.py
        |
        |  psycopg 3 driver
        v
PostgreSQL + pgvector extension
        |
        +-- Alembic: تغییر ساختار database به شکل نسخه‌دار
        +-- pgvector/HNSW: جست‌وجوی برداری RAG
```

فایل‌های محوری:

| فایل | مسئولیت |
|---|---|
| [src/config.py](src/config.py#L8-L96) | خواندن تنظیمات، از جمله `DATABASE_URL` و تنظیمات RAG. |
| [src/db.py](src/db.py#L11-L34) | ساخت SQLAlchemy engine، session factory و ثبت نوع pgvector روی اتصال‌های PostgreSQL. |
| [src/models.py](src/models.py#L24-L759) | همه modelهای ORM، ستون‌ها، constraintها، indexها و relationshipها. |
| [migrations/env.py](migrations/env.py#L15-L49) | اتصال Alembic به `DATABASE_URL` و `Base.metadata`. |
| [src/seed.py](src/seed.py#L32-L731) | ایجاد داده نمونه fake-CMS و دوره آزمایشی قابل اجرا. |
| [src/services/rag.py](src/services/rag.py#L201-L626) | chunking، صف index، embedding و retrieval با pgvector. |
| [src/services/coach.py](src/services/coach.py) | ذخیره پیام‌های Coach و رخدادهای retrieval. |

### 2.1 مفاهیم پایه برای عضو جدید تیم

| مفهوم | معنی در زیتو |
|---|---|
| **Relational database** | داده در جدول‌های مستقل نگهداری می‌شود و با کلیدهای خارجی به هم وصل می‌شوند. |
| **Primary key یا PK** | شناسه یکتای هر ردیف. تقریباً همه جدول‌های عملیاتی یک `id` عددی دارند. استثنای مهم `user_profiles` است که `user_id` خودش PK است. |
| **Foreign key یا FK** | ستونی که به PK جدول دیگر اشاره می‌کند؛ مثلاً `user_sessions.user_id -> users.id`. |
| **One-to-one** | هر کاربر فقط یک پروفایل دارد؛ با PK بودن `user_profiles.user_id` تضمین شده است. |
| **One-to-many** | یک دوره چند نسخه، یک نسخه چند سرفصل و یک سرفصل چند محتوای مرحله دارد. |
| **Many-to-many** | یک سند KB می‌تواند برای چند سرفصل قابل استفاده باشد؛ جدول واسط `course_kb_document_modules` این رابطه را نگه می‌دارد. |
| **Normalization** | هویت پایه کاربر در `users` و پاسخ‌های پروفایل در `user_profiles` جدا شده‌اند تا یک داده در چند جا منبع حقیقت نباشد. |
| **ORM** | SQLAlchemy کلاس Python را به جدول تبدیل می‌کند. مثلاً `User` معادل جدول `users` است. |
| **Migration** | تغییر نسخه‌دار و قابل تکرار schema. به جای ساخت دستی جدول در pgAdmin، migration اجرا می‌شود. |
| **Index** | ساختار کمکی برای سریع‌تر شدن query. هزینه‌اش فضای بیشتر و نوشتن کمی کندتر است. |
| **Constraint** | قاعده‌ای که خود دیتابیس enforce می‌کند، مانند unique phone یا FK. |
| **Transaction** | چند تغییر مرتبط یا همگی commit می‌شوند یا در صورت خطا rollback. برای OTP، پیشرفت و index job حیاتی است. |
| **Soft delete** | ردیف کاربر حذف فیزیکی نمی‌شود؛ `deleted_at` پر می‌شود تا داده و تاریخچه باقی بماند. |
| **pgvector / embedding** | متن KB به بردار 3072 بعدی تبدیل و در PostgreSQL ذخیره می‌شود تا سوال مشابه، محتوای مرتبط را پیدا کند. |

## 3. اتصال و چرخه عمر دیتابیس

### 3.1 تنظیم اتصال

- برنامه `DATABASE_URL` را از environment می‌خواند: [src/config.py:13](src/config.py#L13).
- فرمت production مورد انتظار در `.env.example`، `postgresql+psycopg://...` است.
- engine با `pool_pre_ping=True` ایجاد می‌شود تا اتصال‌های مرده در pool پیش از استفاده تشخیص داده شوند: [src/db.py:15-16](src/db.py#L15-L16).
- `SessionLocal` با `autoflush=False` و `autocommit=False` ساخته می‌شود: [src/db.py:26](src/db.py#L26). بنابراین هر مسیر یا service باید مشخصاً `commit()` یا `rollback()` مناسب داشته باشد.
- برای PostgreSQL، روی هر اتصال `register_vector` اجرا می‌شود تا Psycopg بتواند مقدارهای `vector/halfvec` را bind کند: [src/db.py:19-23](src/db.py#L19-L23).

### 3.2 تفاوت `create_all` و migration

در startup، اگر `AUTO_CREATE_TABLES=true` باشد، برنامه `Base.metadata.create_all()` و سپس seed را اجرا می‌کند: [src/main.py:25-30](src/main.py#L25-L30).

- `create_all()` فقط جدولِ وجودنداشته را می‌سازد؛ **تغییر ستون، حذف constraint، تبدیل داده یا ارتقای schema انجام نمی‌دهد**.
- Alembic migrationها تغییر واقعی schema را با ترتیب مشخص اجرا می‌کنند.
- در production باید `AUTO_CREATE_TABLES=false` باشد و ارتقا فقط با `alembic upgrade head` انجام شود.
- دستور محلی امنی که vault را بارگذاری می‌کند:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\tools\zito-secrets.ps1 migrate-db
```

`alembic_version` جدولی است که Alembic خودش نگه می‌دارد و revision اعمال‌شده را ثبت می‌کند. این جدول model کسب‌وکاری نیست، اما برای دانستن نسخه schema ضروری است.

### 3.3 timestampها

اغلب جدول‌ها `created_at` و `updated_at` دارند.

- `server_default=func.now()` زمان ساخت ردیف را در database ثبت می‌کند.
- `onupdate=func.now()` هنگام update از مسیر ORM مقدار `updated_at` را تغییر می‌دهد.
- این پروژه trigger دیتابیسی برای `updated_at` ندارد؛ پس اگر تیم مستقیماً با SQL خام update بزند، باید خودش timestamp را مدیریت کند یا از ORM استفاده کند.

## 4. نقشه کلی موجودیت‌ها و روابط

### 4.1 نمودار سطح بالا

```text
                    +------------------+
                    |      admins      |
                    | مستقل از users   |
                    +------------------+

+---------+ 1--1 +---------------+       +--------------------+
|  users  |------| user_profiles |       |  phone_otp_codes   |
+----+----+      +---------------+       +--------------------+
     |
     | 1--N
     +----------------------+     +--------------------------+
     |    user_sessions     |     | user_course_enrollments  |
     +----------------------+     +------------+-------------+
                                                |
                                                | 1--N
                       +------------------------+------------------------+
                       |                                                 |
                       v                                                 v
       +------------------------------+               +-------------------------+
       | user_module_stage_progress   |               | user_stage_progress     |
       | canonical module-based path  |               | legacy flat fallback    |
       +---------------+--------------+               +-------------------------+
                       |
                       v
       +-------------------------------+       +-------------------------+
       | course_module_stage_contents  |---N--1| learning_stage_templates|
       +---------------+---------------+       +-------------------------+
                       |
                       v
               +---------------+  N--1  +-----------------+  N--1 +---------+
               | course_modules|--------| course_versions |------| courses |
               +---------------+        +-----------------+      +---------+
                       ^
                       | N--N via course_kb_document_modules
                       |
    +------------------+------------------+
    | course_kb_documents -> chunks/jobs  |
    +------------------+------------------+
                       |
                       v
       +-------------------------------+
       | course_rag_configs (1/version) |
       +-------------------------------+
                       |
                       v
 coach_threads -> coach_messages -> coach_retrieval_events
```

### 4.2 دو مدل آموزشی هم‌زمان

وجود این دو جفت جدول عمدی است و نباید اشتباه گرفته شود:

| مدل | جدول محتوا | جدول پیشرفت | وضعیت فعلی |
|---|---|---|---|
| **نسخه قدیمی flat** | `course_stage_contents` | `user_stage_progress` | برای course versionهای بدون سرفصل و سازگاری با داده قدیمی نگه داشته شده است. |
| **مدل canonical فعلی** | `course_modules` + `course_module_stage_contents` | `user_module_stage_progress` | مسیر فعال fake-CMS و پایه CMS واقعی آینده است. |

کد در [src/api/routes.py:176-294](src/api/routes.py#L176-L294) اول نسخه منتشرشده با بزرگ‌ترین `version_number` را انتخاب می‌کند؛ اگر آن نسخه `course_modules` داشته باشد، موتور ماژول‌محور را استفاده می‌کند. در seed فعلی، دوره نمونه version 2 دارد، 5 سرفصل دارد و برای هر سرفصل 20 قالب منتشرشده ایجاد می‌شود؛ بنابراین مسیر فعال نمونه 100 واحد یادگیری دارد.

## 5. کاتالوگ کامل جدول‌ها

نوع‌ها در جدول‌های زیر نوع ORM هستند. در PostgreSQL، `DateTime(timezone=True)` به timestamp with time zone و `String(n)` به varchar با طول `n` تبدیل می‌شود.

### 5.1 هویت، حساب و دسترسی

#### `users`

مدل: [src/models.py:30-57](src/models.py#L30-L57). منبع حقیقت هویت کاربر است.

| ستون | نوع | قاعده | توضیح |
|---|---|---|---|
| `id` | Integer | PK | شناسه ترتیبی و پایدار کاربر. |
| `phone` | String(20) | NOT NULL, UNIQUE, indexed | شناسه ورود با OTP؛ شماره استانداردشده ایران. |
| `display_name` | String(100) | NOT NULL, indexed | نامی که کاربر می‌خواهد با آن خطاب شود؛ unique نیست. |
| `phone_verified_at` | DateTime(tz) | nullable | زمان آخرین تایید موفق شماره. |
| `last_login_at` | DateTime(tz) | nullable | زمان آخرین ورود موفق. |
| `deleted_at` | DateTime(tz) | nullable, indexed | soft delete. مقدار null یعنی حساب فعال است. |
| `blocked_at` | DateTime(tz) | nullable, indexed | مسدودسازی مدیریتی، مستقل از حذف نرم. |
| `created_at` | DateTime(tz) | server default now | زمان ایجاد. |
| `updated_at` | DateTime(tz) | default/onupdate | زمان آخرین تغییر از ORM. |

رفتار کلیدی:

- اولین login موفق OTP، کاربر جدید می‌سازد؛ برای کاربر جدید `display_name` لازم است: [src/api/routes.py:107-131](src/api/routes.py#L107-L131).
- login با شماره یک کاربر soft-deleted، `deleted_at` را null و همان هویت را فعال می‌کند.
- کاربر `blocked_at != null` اجازه ورود ندارد.
- `username`، `full_name` و `profession` در migration `20260728_0007` حذف شده‌اند و جزو schema فعلی نیستند.

#### `user_profiles`

مدل: [src/models.py:78-110](src/models.py#L78-L110). پاسخ‌های آنبوردینگ و داده امن شخصی‌سازی Coach را نگه می‌دارد.

| ستون | نوع | قاعده | توضیح |
|---|---|---|---|
| `user_id` | Integer | PK, FK -> `users.id`, CASCADE | PK مشترک، رابطه 1 به 1 را تضمین می‌کند. |
| `work_or_study_field` | String(255) | nullable | حوزه کاری یا رشته تحصیلی. |
| `education_level` | String(80) | nullable | سطح تحصیلات. |
| `learning_goal_interests` | Text | nullable | هدف‌ها و علاقه‌مندی‌های یادگیری. |
| `ai_familiarity_level` | String(50) | nullable | میزان آشنایی با AI. |
| `daily_learning_time_text` | String(120) | nullable | پاسخ خام کاربر درباره زمان روزانه. |
| `daily_learning_minutes` | Integer | nullable, check 0..1440 | مقدار نرمال‌شده، در صورت قابل‌تبدیل بودن پاسخ خام. |
| `preferred_career_path` | String(255) | nullable | مسیر شغلی مورد علاقه. |
| `referral_source` | String(120) | nullable | نحوه آشنایی با زیتو. |
| `completed_at` | DateTime(tz) | nullable | زمان کامل شدن هفت پاسخ پروفایل. |
| `created_at`, `updated_at` | DateTime(tz) | NOT NULL | audit timestamps. |

چرا `user_id` هم PK و هم FK است؟ چون نیازی به شناسه مصنوعی دوم ندارد و دیتابیس نمی‌تواند برای یک user بیش از یک profile بسازد. این همان طراحی درست برای موجودیت وابسته 1:1 است.

#### `user_sessions`

مدل: [src/models.py:59-75](src/models.py#L59-L75). session کاربر در database ذخیره می‌شود، اما خود token خام ذخیره نمی‌شود.

| ستون | نوع | قاعده | توضیح |
|---|---|---|---|
| `id` | Integer | PK | شناسه session. |
| `user_id` | Integer | NOT NULL, FK -> users, CASCADE | مالک session. |
| `token_hash` | String(64) | NOT NULL, UNIQUE | SHA-256 token cookie، نه token خام. |
| `created_at` | DateTime(tz) | NOT NULL | زمان ایجاد. |
| `expires_at` | DateTime(tz) | NOT NULL | پایان اعتبار. |
| `last_seen_at` | DateTime(tz) | nullable | برای استفاده آتی؛ در مسیرهای فعلی الزاماً به‌روز نمی‌شود. |
| `revoked_at` | DateTime(tz) | nullable | logout، delete یا block می‌تواند آن را پر کند. |
| `ip_hash` | String(64) | nullable | hash IP برای audit، نه IP خام. |
| `user_agent` | String(500) | nullable | مشخصات مرورگر، کوتاه‌شده تا 500 کاراکتر. |

index مرکب `ix_user_sessions_user_active(user_id, revoked_at, expires_at)` query session فعال یک کاربر را سریع می‌کند. منطق token و cookie در [src/security.py:112-207](src/security.py#L112-L207) قرار دارد.

#### `phone_otp_codes`

مدل: [src/models.py:743-759](src/models.py#L743-L759). رکوردهای OTP ارسال‌شده برای ورود.

| ستون | نوع | قاعده | توضیح |
|---|---|---|---|
| `id` | Integer | PK | شناسه OTP. |
| `phone` | String(20) | NOT NULL, indexed | شماره مقصد. |
| `code_hash` | String(128) | NOT NULL | hash کد؛ کد قابل‌بازیابی نیست. |
| `purpose` | String(30) | NOT NULL, default `login` | هدف OTP. |
| `provider` | String(40) | NOT NULL, default `mock` | تامین‌کننده ارسال، مانند SMS.ir یا mock. |
| `expires_at` | DateTime(tz) | NOT NULL | زمان انقضا. |
| `consumed_at` | DateTime(tz) | nullable | پس از مصرف موفق پر می‌شود. |
| `attempt_count` | Integer | NOT NULL, default 0 | تعداد تلاش‌های تایید. |
| `last_sent_at` | DateTime(tz) | NOT NULL | مبنای rate limit ارسال دوباره. |
| `created_at` | DateTime(tz) | server default now | زمان ایجاد. |

indexهای `ix_phone_otp_latest(phone, purpose, created_at)` و `ix_phone_otp_cleanup(expires_at, consumed_at)` برای یافتن کد آخر و پاک‌سازی به کار می‌روند.

#### `admins`

مدل: [src/models.py:113-121](src/models.py#L113-L121). حساب مدیر از `users` جداست، زیرا identity و مجوز مدیریتی متفاوت دارد.

| ستون | نوع | قاعده | توضیح |
|---|---|---|---|
| `id` | Integer | PK | شناسه مدیر. |
| `username` | String(100) | NOT NULL, UNIQUE | نام ورود مدیر. |
| `password_hash` | String(255) | NOT NULL | PBKDF2-SHA256، نه رمز خام. |
| `is_active` | Boolean | NOT NULL, default true | غیرفعال‌سازی مدیر. |
| `created_at`, `updated_at` | DateTime(tz) | server defaults | audit timestamps. |

برای admin جدول session وجود ندارد؛ session او cookie امضاشده است که اعتبار آن هنگام هر request با جدول `admins` چک می‌شود: [src/security.py:56-109](src/security.py#L56-L109).

### 5.2 کاتالوگ دوره و محتوای آموزشی

#### `courses`

مدل: [src/models.py:124-136](src/models.py#L124-L136). موجودیت پایدار دوره، فارغ از نسخه‌های محتوایی آن.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `title` | String(255) | NOT NULL |
| `slug` | String(120) | NOT NULL, UNIQUE |
| `domain` | String(120) | NOT NULL |
| `status` | String(40) | NOT NULL, default `draft` |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

#### `course_versions`

مدل: [src/models.py:139-167](src/models.py#L139-L167). snapshot نسخه‌دار یک دوره. کاربر به version ثبت‌نام می‌شود، نه به محتوای متغیرِ بدون نسخه.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `course_id` | Integer | NOT NULL, FK -> courses, CASCADE |
| `version_number` | Integer | NOT NULL; UNIQUE با `course_id` |
| `status` | String(40) | NOT NULL, default `draft` |
| `source` | String(40) | NOT NULL, default `seed`؛ در fake CMS مقدار `fake_cms` |
| `published_at` | DateTime(tz) | nullable |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

دو unique constraint دارد:

1. `uq_course_versions_course_version(course_id, version_number)` از نسخه تکراری جلوگیری می‌کند.
2. `uq_course_versions_id_course(id, course_id)` برای FKهای مرکب RAG استفاده می‌شود تا `course_id` و `course_version_id` ناسازگار نباشند.

#### `learning_stage_templates`

مدل: [src/models.py:193-217](src/models.py#L193-L217). فهرست reusable بیست قالب ارائه محتوا، مستقل از متن یک دوره.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `code` | String(80) | NOT NULL, UNIQUE؛ شناسه پایدار مثل `lesson_summary` |
| `title` | String(255) | NOT NULL |
| `description` | Text | nullable |
| `default_order` | Integer | NOT NULL، check `>= 1` |
| `is_active` | Boolean | NOT NULL, default true |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

کد قالب، نه title فارسی، برای اتصال UI و محتوا استفاده می‌شود تا تغییر متن یا طراحی ظاهری، داده و progress را نشکند.

#### `course_modules`

مدل: [src/models.py:220-259](src/models.py#L220-L259). سرفصل‌های یک version از دوره.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions, CASCADE |
| `module_number` | Integer | NOT NULL, check `>=1`, UNIQUE با version |
| `title` | String(255) | NOT NULL |
| `description` | Text | nullable |
| `learning_objectives_json` | JSON | NOT NULL, default list |
| `tags_json` | JSON | NOT NULL, default list |
| `status` | String(40) | NOT NULL, default `approved` |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

`uq_course_modules_id_version(id, course_version_id)` یک کلید یکتای مرکب کمکی برای جلوگیری از اتصال KB یک version به module version دیگر است.

#### `course_module_stage_contents`

مدل: [src/models.py:262-306](src/models.py#L262-L306). جدول canonical محتوا: «یک قالب از 20 قالب در یک سرفصل مشخص».

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `course_module_id` | Integer | NOT NULL, FK -> course_modules, CASCADE |
| `template_id` | Integer | NOT NULL, FK -> learning_stage_templates |
| `stage_number` | Integer | NOT NULL, check `>=1` |
| `title` | String(255) | NOT NULL |
| `content_json` | JSON | NOT NULL؛ payload قابل رندر در UI |
| `status` | String(40) | NOT NULL, default `approved` |
| `ai_generation_status` | String(40) | NOT NULL, default `seeded` |
| `review_status` | String(40) | NOT NULL, default `approved` |
| `reviewed_by` | String(100) | nullable |
| `generated_at`, `reviewed_at` | DateTime(tz) | nullable |
| `content_version` | Integer | NOT NULL, default 1 |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

دو constraint مهم دارد:

- `UNIQUE(course_module_id, stage_number)`: هر شماره مرحله فقط یک بار در هر سرفصل.
- `UNIQUE(course_module_id, template_id)`: یک قالب تکراری در یک سرفصل ثبت نمی‌شود.

برنامه قبل از ارائه دوره، دقیقاً 20 مرحله شماره 1 تا 20 را برای هر module بررسی می‌کند: [src/api/routes.py:248-294](src/api/routes.py#L248-L294).

#### جدول‌های compatibility قدیمی: `course_stage_contents`

مدل: [src/models.py:170-190](src/models.py#L170-L190). این جدول همان محتوای flat 20 مرحله‌ای برای course versionهای قدیمی است. ساختار ستون‌هایش شبیه `course_module_stage_contents` است، اما `course_module_id` و `template_id` ندارد و به جای آن `course_version_id`, `stage_number`, `stage_type` دارد.

این جدول در database واقعی وجود دارد و routeها هنوز برای version بدون module از آن fallback می‌خوانند: [src/api/routes.py:200-237](src/api/routes.py#L200-L237). بنابراین در حال حاضر نباید دستی حذف شود. CMS آینده باید فقط مدل module-based را بنویسد؛ پاک‌سازی این جدول بعد از مهاجرت همه دوره‌های قدیمی انجام می‌شود.

### 5.3 ثبت‌نام و پیشرفت یادگیرنده

#### `user_course_enrollments`

مدل: [src/models.py:544-569](src/models.py#L544-L569). اتصال یک user به یک version از course.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `user_id` | Integer | NOT NULL, FK -> users, CASCADE |
| `course_id` | Integer | NOT NULL, FK -> courses, CASCADE |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions, CASCADE |
| `status` | String(40) | NOT NULL, default `active` |
| `current_stage_number` | Integer | NOT NULL, default 1 |
| `progress_percentage` | Integer | NOT NULL, default 0 |
| `enrolled_at` | DateTime(tz) | server default now |
| `completed_at` | DateTime(tz) | nullable |
| `updated_at` | DateTime(tz) | audit timestamp |

`UNIQUE(user_id, course_version_id)` جلوی ثبت‌نام دوباره در همان version را می‌گیرد.

**نکته طراحی مهم:** `course_id` از `course_version_id` قابل استخراج است، پس افزونگی دارد. برای حفظ سازگاری API فعلی نگه داشته شده، اما از migration `20260819_0014` یک FK مرکب `course_version_id, course_id -> course_versions.id, course_versions.course_id` تضمین می‌کند که این دو به دو دوره متفاوت اشاره نکنند.

`current_stage_number` و `progress_percentage` در مدل فعال cache/denormalized state هستند که در [src/api/routes.py:324-344](src/api/routes.py#L324-L344) از progress rowها به‌روز می‌شوند. منبع جزئیات پیشرفت، جدول progress است.

#### `user_module_stage_progress`

مدل: [src/models.py:588-618](src/models.py#L588-L618). جدول canonical پیشرفت برای هر محتوای مرحله‌ای module-based.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `enrollment_id` | Integer | NOT NULL, FK -> user_course_enrollments, CASCADE |
| `module_stage_content_id` | Integer | NOT NULL, FK -> course_module_stage_contents, CASCADE |
| `status` | String(40) | NOT NULL, default `locked` |
| `response_json` | JSON | nullable؛ پاسخ/داده مرحله |
| `started_at`, `completed_at` | DateTime(tz) | nullable |
| `updated_at` | DateTime(tz) | NOT NULL |

constraint `UNIQUE(enrollment_id, module_stage_content_id)` تضمین می‌کند هر کاربر فقط یک progress row برای هر محتوای مشخص دارد. index `ix_user_module_stage_progress_enrollment_status` برای گرفتن مرحله بعدی کاربر استفاده می‌شود.

در ساخت enrollment برای مسیر module-based، برنامه ردیف اول را `available` و باقی را `locked` می‌سازد: [src/api/routes.py:297-321](src/api/routes.py#L297-L321).

#### جدول compatibility قدیمی: `user_stage_progress`

مدل: [src/models.py:572-585](src/models.py#L572-L585). progress flat بر اساس `stage_number` برای دوره‌های بدون module. هنوز fallback route دارد و با `user_module_stage_progress` یکی نیست. در دوره نمونه version 2 استفاده نمی‌شود.

### 5.4 RAG و Knowledge Base

#### `course_rag_configs`

مدل: [src/models.py:309-339](src/models.py#L309-L339). تنظیمات non-secret RAG برای یک course version.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `course_version_id` | Integer | NOT NULL, UNIQUE, FK -> course_versions, CASCADE |
| `provider` | String(50) | NOT NULL, default `zito_embedding` |
| `endpoint_config_ref` | String(120) | nullable؛ نام مرجع config، نه secret |
| `knowledge_base_ref` | String(160) | nullable؛ مرجع منبع KB |
| `status` | String(30) | NOT NULL, default `ready` |
| `supports_metadata_filters` | Boolean | NOT NULL, default false |
| `embedding_model` | String(120) | NOT NULL, default `Bge-m3` |
| `embedding_dimensions` | Integer | NOT NULL, default 3072 |
| `last_indexed_at` | DateTime(tz) | nullable |
| `last_error` | Text | nullable |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

کلید API یا URL واقعی در این جدول ذخیره نمی‌شود. فقط نام configuration مثل `ARVAN_EMBEDDING_API_BASE_URL` به عنوان reference می‌آید؛ secret در environment/vault باقی می‌ماند.

#### `course_kb_documents`

مدل: [src/models.py:342-396](src/models.py#L342-L396). سندهای تاییدشده KB که به یک course version پین شده‌اند.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `course_id` | Integer | NOT NULL, FK -> courses, CASCADE |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions, CASCADE |
| `title` | String(255) | NOT NULL |
| `content` | Text | NOT NULL |
| `content_checksum` | String(64) | NOT NULL؛ SHA-256 متن |
| `tags` | String(255) | nullable؛ metadata ساده فعلی |
| `source_type` | String(40) | NOT NULL, default `seed` |
| `source_reference` | String(500) | nullable؛ مسیر/مرجع منبع، بدون secret |
| `status` | String(30) | NOT NULL, default `approved` |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

FK مرکب `fk_course_kb_documents_version_course(course_version_id, course_id) -> course_versions(id, course_id)` تضمین می‌کند یک document نتواند به version یک دوره و ID دوره‌ای دیگر وصل شود.

#### `course_kb_document_modules`

مدل: [src/models.py:448-490](src/models.py#L448-L490). جدول واسط scope سند و سرفصل.

| ستون | نوع | قاعده |
|---|---|---|
| `document_id` | Integer | PK مرکب، FK -> course_kb_documents, CASCADE |
| `course_module_id` | Integer | PK مرکب، FK -> course_modules, CASCADE |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions, CASCADE |
| `created_at` | DateTime(tz) | NOT NULL |

اگر یک document هیچ ردیفی در این جدول نداشته باشد، برای تمام moduleهای همان course version **global** است. اگر ردیف داشته باشد، فقط moduleهای صریحاً وصل‌شده مجازند. این اصل در [src/services/rag.py:280-296](src/services/rag.py#L280-L296) اعمال می‌شود.

#### `course_kb_document_chunks`

مدل: [src/models.py:399-445](src/models.py#L399-L445). واحد واقعی retrieval. یک document به چند chunk تقسیم می‌شود.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `document_id` | Integer | NOT NULL, FK -> course_kb_documents, CASCADE |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions, CASCADE |
| `chunk_index` | Integer | NOT NULL; UNIQUE با document |
| `content` | Text | NOT NULL |
| `content_checksum` | String(64) | NOT NULL |
| `embedding` | `halfvec(3072)` در PostgreSQL | nullable؛ JSON در SQLite test |
| `embedding_input_checksum` | String(64) | NOT NULL؛ تطبیق embedding با متن |
| `embedding_model` | String(120) | nullable |
| `embedding_dimension` | Integer | nullable |
| `embedding_status` | String(30) | NOT NULL, default `pending` |
| `embedding_indexed_at` | DateTime(tz) | nullable |
| `embedding_error` | Text | nullable |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

در PostgreSQL، migration `20260816_0012` HNSW index نیمه‌برداری با operator `halfvec_cosine_ops` می‌سازد. این index فقط chunkهایی با embedding غیر-null را شامل می‌شود. SQLite صرفاً برای تست است و similarity را در Python محاسبه می‌کند؛ production نباید روی آن تکیه کند.

#### `course_kb_index_jobs`

مدل: [src/models.py:493-541](src/models.py#L493-L541). صف durable برای ساخت/rebuild embedding سند.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions |
| `document_id` | Integer | NOT NULL, FK -> course_kb_documents |
| `source_checksum` | String(64) | NOT NULL؛ snapshot متن هنگام queue شدن |
| `embedding_model` | String(120) | NOT NULL, default `Bge-m3` |
| `status` | String(30) | NOT NULL, default `queued` |
| `attempt_count` | Integer | NOT NULL, default 0, check `>=0` |
| `max_attempts` | Integer | NOT NULL, default 5, check `>=1` |
| `requested_at` | DateTime(tz) | NOT NULL |
| `started_at`, `finished_at`, `next_attempt_at` | DateTime(tz) | nullable |
| `error_message` | Text | nullable |
| `created_at`, `updated_at` | DateTime(tz) | audit timestamps |

در PostgreSQL یک partial unique index جلوی داشتن دو job فعال (`queued`, `running`, `retry`) برای یک document را می‌گیرد. worker از `FOR UPDATE SKIP LOCKED` استفاده می‌کند تا دو worker یک job را برندارند: [src/services/rag.py:402-475](src/services/rag.py#L402-L475).

### 5.5 Coach و Audit

#### `coach_threads`

مدل: [src/models.py:621-643](src/models.py#L621-L643). یک گفت‌وگوی پایدار Coach برای یک enrollment.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `user_id` | Integer | NOT NULL, FK -> users, CASCADE |
| `enrollment_id` | Integer | NOT NULL, UNIQUE, FK -> enrollments, CASCADE |
| `status` | String(30) | NOT NULL, default `active` |
| `created_at` | DateTime(tz) | NOT NULL |
| `last_message_at` | DateTime(tz) | nullable |

#### `coach_messages`

مدل: [src/models.py:646-670](src/models.py#L646-L670). هر پیام learner یا assistant با context مرحله جاری.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `thread_id` | Integer | NOT NULL, FK -> coach_threads, CASCADE |
| `module_stage_content_id` | Integer | nullable, FK -> module stage content, SET NULL |
| `role` | String(20) | NOT NULL؛ convention فعلی `user` یا `assistant` |
| `content` | Text | NOT NULL |
| `content_json` | JSON | nullable؛ metadata ساخت‌یافته پاسخ |
| `model` | String(120) | nullable |
| `prompt_version` | String(80) | nullable |
| `created_at` | DateTime(tz) | NOT NULL |

`ON DELETE SET NULL` در stage context باعث می‌شود در صورت حذف محتوای یک stage، تاریخچه متن پیام از بین نرود.

#### `coach_retrieval_events`

مدل: [src/models.py:673-698](src/models.py#L673-L698). audit trail برای یک پاسخ assistant.

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `assistant_message_id` | Integer | NOT NULL, UNIQUE, FK -> coach_messages, CASCADE |
| `rag_config_id` | Integer | nullable, FK -> course_rag_configs, SET NULL |
| `retrieval_method` | String(50) | NOT NULL |
| `source_chunks_json` | JSON | NOT NULL؛ citation metadata |
| `grounded` | Boolean | NOT NULL, default false |
| `latency_ms` | Integer | nullable |
| `status` | String(30) | NOT NULL, default `ok` |
| `error_message` | Text | nullable |
| `created_at` | DateTime(tz) | NOT NULL |

هر assistant message حداکثر یک retrieval event دارد. این داده برای پاسخ‌گویی، تحلیل کیفیت RAG و بررسی خطا استفاده می‌شود؛ نه برای ساخت profile کاربر.

### 5.6 آزمون و مدرک

مدل‌های زیر در schema وجود دارند اما UI/API کامل Sprint آزمون و مدرک هنوز پیاده‌سازی نشده است.

#### `exams`

مدل: [src/models.py:701-712](src/models.py#L701-L712).

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions, CASCADE |
| `title` | String(255) | NOT NULL |
| `questions_json` | JSON | NOT NULL |
| `passing_score` | Integer | NOT NULL, default 70 |
| `status` | String(40) | NOT NULL, default `published` |
| `created_at` | DateTime(tz) | server default now |

#### `exam_attempts`

مدل: [src/models.py:715-728](src/models.py#L715-L728).

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `exam_id` | Integer | NOT NULL, FK -> exams, CASCADE |
| `user_id` | Integer | NOT NULL, FK -> users, CASCADE |
| `enrollment_id` | Integer | nullable, FK -> enrollments, CASCADE |
| `answers_json` | JSON | NOT NULL |
| `score` | Integer | nullable |
| `passed` | Boolean | NOT NULL, default false |
| `grading_feedback` | Text | nullable |
| `graded_by_ai_at` | DateTime(tz) | nullable |
| `created_at` | DateTime(tz) | server default now |

#### `certificates`

مدل: [src/models.py:730-741](src/models.py#L730-L741).

| ستون | نوع | قاعده |
|---|---|---|
| `id` | Integer | PK |
| `user_id` | Integer | NOT NULL, FK -> users, CASCADE |
| `course_id` | Integer | NOT NULL, FK -> courses, CASCADE |
| `course_version_id` | Integer | NOT NULL, FK -> course_versions, CASCADE |
| `exam_attempt_id` | Integer | nullable, FK -> exam_attempts, SET NULL |
| `certificate_number` | String(120) | NOT NULL, UNIQUE |
| `status` | String(40) | NOT NULL, default `issued` |
| `issued_at` | DateTime(tz) | server default now |

وجود `user_id`, `course_id` و `course_version_id` در certificate افزونگی ایجاد می‌کند، چون از exam attempt/enrollment قابل استنتاج هستند. فعلاً این schema را تغییر نمی‌دهیم؛ در Sprint آزمون باید ruleهای سازگاری یا بازطراحی migration-aware مشخص شود.

## 6. روابط، حذف‌ها و مالکیت داده

### 6.1 سیاست `ON DELETE`

| parent | child | رفتار database |
|---|---|---|
| `users` | profile, sessions, enrollments, coach threads | CASCADE فقط در حذف فیزیکی user |
| `courses` | versions, KB documents, enrollments, certificates | CASCADE در حذف فیزیکی course |
| `course_versions` | modules, legacy stages, exams, RAG config, KB records | CASCADE |
| `course_modules` | module stage contents, KB module mapping | CASCADE |
| `course_module_stage_contents` | module progress | CASCADE |
| module stage content | coach message context | SET NULL |
| `coach_messages` | retrieval event | CASCADE |
| RAG config | retrieval event | SET NULL |
| exam attempt | certificate reference | SET NULL |

**فرق مهم:** حذف از پنل مدیر برای user حذف فیزیکی نیست. route مدیریت `deleted_at` را پر و sessionها را revoke می‌کند؛ بنابراین cascade دیتابیسی اجرا نمی‌شود. login موفق OTP همان user را restore می‌کند. block یک وضعیت جداگانه است.

### 6.2 ماتریس منبع حقیقت

| داده | منبع حقیقت فعلی | نباید جای دیگر canonical تکرار شود |
|---|---|---|
| هویت کاربر | `users.id`, `users.phone`, `users.display_name` | localStorage یا profile name جدا |
| پاسخ‌های onboarding | `user_profiles` | ستون اضافی در users |
| session کاربر | `user_sessions` | token خام در database |
| دوره و slug | `courses` | نام دوره در enrollment به عنوان داده اصلی |
| نسخه محتوای تحویلی | `course_versions` | «آخرین محتوا» بدون version |
| قالب آموزشی | `learning_stage_templates` | stringهای پراکنده UI |
| محتوای هر قالب/سرفصل | `course_module_stage_contents.content_json` | تولید لحظه‌ای برای جایگزینی محتوای منتشرشده |
| پیشرفت canonical | `user_module_stage_progress` | فقط درصد در enrollment |
| KB قابل retrieval | `course_kb_documents` و `course_kb_document_chunks` | فایل markdown به تنهایی در runtime |
| embedding وضعیت‌دار | chunk + index job | حافظه process یا فایل موقت |
| گفت‌وگوی Coach | `coach_threads` و `coach_messages` | profile یا browser state |
| منبع پاسخ Coach | `coach_retrieval_events` | log غیرقابل query |

## 7. Indexها و عملکرد

### 7.1 indexهای مهم عملیاتی

| جدول | index/constraint | query یا قاعده‌ای که پشتیبانی می‌کند |
|---|---|---|
| `users` | phone unique/index | login و جلوگیری از دو حساب با یک شماره |
| `users` | display_name/deleted_at/blocked_at index | پنل مدیر، filtering account state |
| `user_sessions` | `(user_id, revoked_at, expires_at)` | پیدا کردن sessionهای فعال یک user |
| `phone_otp_codes` | `(phone, purpose, created_at)` | یافتن OTP آخر |
| `phone_otp_codes` | `(expires_at, consumed_at)` | cleanup کدهای منقضی/مصرف‌شده |
| `course_modules` | `(course_version_id, status, module_number)` | نمایش سرفصل‌های منتشرشده با ترتیب |
| `course_module_stage_contents` | `(course_module_id, status, stage_number)` | 20 مرحله تاییدشده هر module |
| `user_module_stage_progress` | `(enrollment_id, status)` | مرحله جاری/قفل‌شده کاربر |
| `course_kb_documents` | `(course_version_id, status, id)` | KB تاییدشده در یک version |
| `course_kb_document_chunks` | status indexes + HNSW embedding | retrieval RAG سریع و version-scoped |
| `course_kb_index_jobs` | status/next_attempt + partial active job unique | queue durable و جلوگیری از job تکراری |
| `coach_messages` | `(thread_id, created_at)` | history پیام‌ها |
| `coach_retrieval_events` | `(rag_config_id, created_at)` | audit/monitoring RAG |

### 7.2 چرا `halfvec(3072)`؟

مدل embedding فعلی Bge-m3، 3072 مقدار برای هر متن برمی‌گرداند. `vector` استاندارد pgvector در index HNSW محدودیت dimension کمتری دارد؛ بنابراین پروژه از `halfvec(3072)` استفاده کرده است: [src/models.py:24-27](src/models.py#L24-L27). halfvec حافظه کمتری می‌گیرد و امکان HNSW برای این dimension را فراهم می‌کند.

وقتی سوال کاربر می‌آید، برنامه:

1. خود سوال را embed می‌کند.
2. فقط chunkهای همان `course_version_id`، همان module یا documentهای global همان course را query می‌کند.
3. فاصله cosine را با pgvector محاسبه و نزدیک‌ترین `top_k` را برمی‌گرداند.
4. فقط context بازیابی‌شده و بخش مجاز profile را به AI Coach می‌دهد.

مسیر retrieval در [src/services/rag.py:299-391](src/services/rag.py#L299-L391) است. هیچ learner requestای نباید خودش chunking یا embedding document را اجرا کند؛ آن کار به job worker تعلق دارد.

## 8. جریان‌های داده کلیدی

### 8.1 ورود با OTP و ایجاد user

```text
شماره موبایل
  -> phone_otp_codes: hash + expiry + attempt count
  -> OTP موفق
  -> users: create یا restore
  -> user_sessions: فقط token_hash ذخیره می‌شود
  -> cookie امن مرورگر
```

کاربر جدید بعد از OTP، `display_name` می‌دهد. تکمیل profile بعدی، `user_profiles` را update می‌کند و فیلدها nullable هستند تا جریان چتی بتواند مرحله‌به‌مرحله پیش برود.

### 8.2 انتخاب دوره و پیمایش مسیر

```text
courses -> latest published course_version
        -> course_modules
        -> 20 course_module_stage_contents for every module
        -> user_course_enrollments
        -> user_module_stage_progress rows
```

برای course version ماژول‌محور، application فقط وقتی course را قابل ارائه می‌داند که هر module دقیقاً 20 content مرحله‌ای approved و پیوسته داشته باشد. این validation در application است، نه CHECK دیتابیسی.

### 8.3 ورود KB و index شدن

```text
منبع CMS یا Markdown mock
  -> course_kb_documents (approved, checksummed, version-pinned)
  -> split_document
  -> course_kb_document_chunks (pending)
  -> course_kb_index_jobs (queued)
  -> index worker / embedding endpoint
  -> chunk.embedding + status=indexed
  -> course_rag_configs.last_indexed_at
```

در حال حاضر منبع mock در [knowledge_base/personal-development-ai-mock-kb.md](knowledge_base/personal-development-ai-mock-kb.md) و import آن در [src/services/kb_import.py](src/services/kb_import.py) است. بعداً CMS باید همین قرارداد را رعایت کند، نه یک مسیر RAG موازی بسازد.

### 8.4 AI Coach و traceability

```text
سوال کاربر
  -> CoachThread برای enrollment
  -> CoachMessage(role=user)
  -> retrieve_course_chunks
  -> Arvan chat model
  -> CoachMessage(role=assistant)
  -> CoachRetrievalEvent(citations, grounded, latency, status)
```

این طراحی اجازه می‌دهد بعداً مشخص شود یک پاسخ با کدام source chunkها تولید شده، grounded بوده یا fallback، و خطا در کدام مرحله رخ داده است.

## 9. تاریخچه migrationها

| revision | فایل | اثر اصلی |
|---|---|---|
| `20260707_0001` | `20260707_0001_initial.py` | schema بسیار ابتدایی users/questions/answers/global KB/user progress را ساخت. |
| `20260714_0002` | `20260714_0002_admins.py` | جدول `admins` را اضافه کرد. |
| `20260723_0003` | `20260723_0003_phase2_schema.py` | course/version/content/enrollment/exam و profile v2 اولیه را ایجاد کرد. |
| `20260726_0004` | `20260726_0004_phone_otp_codes.py` | OTP persistence را افزود. |
| `20260727_0005` | `20260727_0005_user_phone_identity.py` | phone login identity را از username جدا کرد. |
| `20260728_0006` | `20260728_0006_canonical_identity_profile.py` | `display_name`، soft delete، user profile canonical و user sessions را اضافه و داده قبلی را backfill کرد. |
| `20260728_0007` | `20260728_0007_remove_legacy_user_schema.py` | answers/questions/global KB/profile v2 اولیه/user progress و ستون‌های قدیمی users را حذف کرد. |
| `20260805_0008` | `20260805_0008_module_learning_structure.py` | ساختار module + 20 template + module progress را به‌صورت additive ایجاد کرد. |
| `20260806_0009` | `20260806_0009_store_free_form_daily_learning_time.py` | متن خام زمان یادگیری روزانه را به profile افزود. |
| `20260806_0010` | `20260806_0010_separate_user_block_status.py` | block را از soft delete جدا کرد. |
| `20260808_0011` | `20260808_0011_course_coach_rag_foundation.py` | RAG config، chunk اولیه، Coach thread/message/retrieval audit را ایجاد کرد. |
| `20260816_0012` | `20260816_0012_native_pgvector_rag_contract.py` | RAG را version-safe کرد، `halfvec(3072)`، HNSW و durable index jobs را افزود. |
| `20260816_0013` | `20260816_0013_kb_markdown_source_reference.py` | `source_reference` و index provenance KB را افزود. |
| `20260819_0014` | `20260819_0014_enrollment_integrity_guards.py` | mismatch دوره/نسخه در enrollment را با FK مرکب منع، بازه progress را enforce و index خواندن enrollment فعال را اضافه کرد. |

در migration `20260816_0012`، وجود extension `vector` در PostgreSQL قبل از ارتقا بررسی می‌شود. اگر pgvector نصب/فعال نباشد، migration production متوقف می‌شود؛ این رفتار عمدی است تا schema نیمه‌کاره ساخته نشود.

## 10. قواعد توسعه امن schema

### 10.1 قانون تغییر model

برای هر تغییر داده‌ای جدید، این ترتیب لازم است:

1. نیاز و ownership data را مشخص کن: جدول موجود کافی است یا موجودیت جدید لازم است؟
2. model را در `src/models.py` تغییر بده.
3. migration Alembic بساز و **SQL تولیدشده را دستی review کن**.
4. migration را روی database خالی و نسخه قبلی تست کن.
5. test schema و service مرتبط را اضافه/به‌روز کن.
6. قبل از production، backup و `alembic current` بگیر.
7. در production migration را قبل از restart application اجرا کن.

هرگز فقط با `Base.metadata.create_all()` یا تغییر دستی pgAdmin schema production را عوض نکن. در آن صورت revision Alembic با database واقعی همگام نمی‌ماند و deploy بعدی غیرقابل‌پیش‌بینی می‌شود.

### 10.2 اصول CMS آینده

CMS واقعی باید:

- course و course version بسازد؛ محتوای منتشرشده یک version قدیمی را بی‌صدا overwrite نکند.
- برای هر `course_module` دقیقاً 20 `course_module_stage_contents` با templateهای یکتا بسازد.
- محتوای AI-generated را ابتدا `draft/review` نگه دارد و فقط پس از تایید اپراتور `approved` کند.
- هنگام تغییر document approved، checksum را به‌روز و فقط یک `course_kb_index_job` فعال ایجاد کند.
- secret API یا credential را در `course_rag_configs` ذخیره نکند.

### 10.3 اصول حذف

- حذف user از UI: soft delete + revoke session.
- block user: فقط `blocked_at` را تغییر بده؛ block جای delete نیست.
- حذف فیزیکی course/version/document: فقط با ابزار مدیریتی محدود، backup و بررسی cascade. این کار می‌تواند progress، KB و conversationهای وابسته را پاک کند.
- حذف legacy tableها: فقط بعد از migration تمامی course versionها و enrollmentهای فعال به مدل module-based و یک دوره مشاهده production.

## 11. تست‌های موجود برای قرارداد دیتابیس

| فایل تست | چه چیزی را نگه می‌دارد |
|---|---|
| [tests/test_schema_contract.py](tests/test_schema_contract.py#L13-L123) | نبودن column/tableهای user legacy، وجود profile canonical و ساختار module/RAG/Coach. |
| [tests/test_learning_engine.py](tests/test_learning_engine.py) | enrollment و advance مسیر یادگیری. |
| [tests/test_phase2_seed.py](tests/test_phase2_seed.py) | ساخت دوره نمونه و content مرحله‌ای. |
| [tests/test_rag_indexing.py](tests/test_rag_indexing.py#L28-L173) | chunk/job/index/retrieval scope و recovery lease job. |
| [tests/test_course_coach.py](tests/test_course_coach.py#L50-L213) | ذخیره Coach، isolation کاربر، citation و عدم ارسال phone به model. |
| [tests/test_otp.py](tests/test_otp.py) | OTP، rate limit و session flow. |
| [tests/test_profile_courses.py](tests/test_profile_courses.py) | profile و انتخاب/ثبت‌نام دوره. |

تست‌ها عمدتاً SQLite را برای سرعت استفاده می‌کنند. `halfvec` در SQLite به JSON تبدیل می‌شود، پس هر تغییر مربوط به pgvector باید علاوه بر suite معمول، روی PostgreSQL واقعی با extension `vector` تست شود.

## 12. دستورات عملی برای مشاهده و عیب‌یابی

### 12.1 بررسی revision فعلی

پس از بارگذاری environment امن، از root پروژه اجرا شود:

```powershell
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
```

خروجی production باید head `20260819_0014` را نشان دهد، مگر migration جدیدتری بعداً به پروژه افزوده شده باشد.

### 12.2 Queryهای read-only مفید در pgAdmin

```sql
-- فهرست جدول‌های business schema
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- ستون‌های یک جدول
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'users'
ORDER BY ordinal_position;

-- revision ثبت‌شده توسط Alembic
SELECT version_num FROM alembic_version;

-- تعداد ردیف‌ها در جدول‌های هویتی
SELECT
  (SELECT count(*) FROM users) AS users,
  (SELECT count(*) FROM user_profiles) AS profiles,
  (SELECT count(*) FROM user_sessions) AS sessions,
  (SELECT count(*) FROM phone_otp_codes) AS otp_codes;

-- وضعیت صف RAG
SELECT status, count(*)
FROM course_kb_index_jobs
GROUP BY status
ORDER BY status;

-- وضعیت embeddingها
SELECT embedding_status, count(*)
FROM course_kb_document_chunks
GROUP BY embedding_status
ORDER BY embedding_status;
```

این queryها فقط مشاهده می‌کنند. هیچ `DELETE`, `DROP`, `TRUNCATE` یا `UPDATE` را از pgAdmin روی production اجرا نکن مگر migration/runbook صریح و backup تاییدشده وجود داشته باشد.

## 13. محدودیت‌ها و بدهی فنی شناخته‌شده

این موارد باگ پنهان نیستند؛ باید پیش از تغییر Sprintهای آینده در نظر گرفته شوند:

1. **دو موتور پیشرفت وجود دارد:** module-based canonical و flat compatibility. حذف دومی هنوز زود است، اما CMS جدید نباید داده جدید در آن بنویسد.
2. **`user_course_enrollments.course_id` افزونه است، اما اکنون protected است:** FK مرکب migration `20260819_0014` تطابق آن با version را enforce می‌کند. حذف فیزیکی ستون فقط پس از بازطراحی API و migration جداگانه ممکن است.
3. **statusها enum دیتابیسی نیستند:** مقادیری مانند `approved`, `draft`, `active`, `locked` convention application هستند. CMS آینده باید validation مرکزی داشته باشد.
4. **tags دو شکل دارند:** `course_modules.tags_json` یک JSON list و `course_kb_documents.tags` یک string ساده است. تا نیاز واقعی filter/query پیچیده ایجاد نشده، migration پرهزینه برای نرمال‌سازی tags توجیه ندارد، ولی CMS باید قرارداد این دو را مستند کند.
5. **schema آزمون/مدرک از runtime جلوتر است:** جدول‌ها و seed وجود دارند، اما lifecycle کامل attempt/grading/certificate route هنوز Sprint بعدی است.
6. **حذف فیزیکی parentها پرریسک است:** CASCADE در course/version می‌تواند داده آموزشی، progress و KB را پاک کند. نقش‌های CMS باید این دسترسی را محدود کنند.
7. **worker دائمی RAG برای deploy آماده شده ولی هنوز باید نصب شود:** فایل systemd و runbook در `deploy/` هست؛ فعال‌سازی آن باید در یک deploy کنترل‌شده انجام شود.

## 14. واژه‌نامه کوتاه

| واژه | معنی |
|---|---|
| Course | عنوان ثابت یک دوره، مانند توسعه فردی با AI. |
| Course version | snapshot منتشرشده یک دوره که enrollment به آن پین می‌شود. |
| Module | سرفصل یک version دوره. |
| Template | یکی از 20 قالب تکرارشونده ارائه آموزشی. |
| Stage content | محتوای یک template در یک module. |
| Enrollment | عضویت یک کاربر در یک course version. |
| Progress row | وضعیت کاربر برای یک stage content مشخص. |
| KB document | سند تاییدشده دانشی در یک course version. |
| Chunk | بخش کوچک قابل بازیابی از یک KB document. |
| Embedding | بردار عددی معنی متن. |
| Index job | کار durable برای ساخت/rebuild embeddingها. |
| Grounded answer | پاسخ Coach که به chunkهای بازیابی‌شده استناد دارد. |

## 15. جمع‌بندی تصمیم‌های طراحی

- هویت کاربر با شماره تلفن و `users.id` پایدار است؛ display name شناسه login نیست.
- profile در جدول 1:1 جدا نگهداری می‌شود تا data model نرمال بماند.
- دوره versioned است تا تغییر CMS، تجربه ثبت‌نام‌شده کاربر را ناگهان عوض نکند.
- محتوای جدید باید فقط در hierarchy module/template وارد شود؛ flat tables فقط bridge سازگاری‌اند.
- RAG local و auditable است: document، chunk، vector، job و citation همگی در database قابل بررسی‌اند.
- کلیدها و credentialها هرگز داخل tableهای business یا Git ذخیره نمی‌شوند.
- migration تنها مسیر معتبر تغییر schema در محیط‌های پایدار است.
