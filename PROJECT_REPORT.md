# PROJECT_REPORT.md - مستندسازی فنی وضعیت فعلی Zito

تاریخ تهیه: 2026-07-20  
آخرین به‌روزرسانی: 2026-07-23
ریپازیتوری‌های GitHub:
- `https://github.com/TheAlta/ZitoApp`
- `https://github.com/elmsaz/elmsazZito`
دامنه production: `https://zito.ir`  
نکته امنیتی: هیچ مقدار واقعی secret، API key، رمز دیتابیس، رمز SSH یا token در این سند آورده نشده است.

---

## ۱. معرفی کلی پروژه

### پروژه چیست؟

Zito یک سرویس onboarding و آموزش هوش مصنوعی است که کاربر ابتدا از طریق یک رابط چت/لندینگ وارد می‌شود، با شماره موبایل به عنوان username شناسایی می‌شود، سپس به چند سوال اولیه پاسخ می‌دهد. پاسخ‌های اولیه با Arvancloud AIaaS بررسی می‌شوند تا مشخص شود مرتبط، معنادار و مطابق سوال هستند یا نه. اگر پاسخ تایید شود در دیتابیس ذخیره می‌شود و کاربر وارد مسیر آموزش می‌شود.

مسیر آموزشی فعلی روی سه حوزه متمرکز است:

- حسابداری و هوش مصنوعی
- روانشناسی و هوش مصنوعی
- حقوق و هوش مصنوعی

برای آموزش، یک Knowledge Base داخلی در دیتابیس وجود دارد و لایه RAG ساده از جدول `knowledge_documents` context بازیابی می‌کند و آن را همراه prompt به مدل Arvancloud AIaaS می‌فرستد.

### مسئله‌ای که حل می‌کند

- اعتبارسنجی پاسخ‌های کاربر بدون rule-based ساده و با کمک LLM.
- ذخیره پاسخ‌های تاییدشده برای مدیر.
- نمایش کاربران، جواب‌ها و امکان اصلاح/حذف از پنل ادمین.
- انتقال مستقیم کاربر از onboarding به آموزش، بدون توقف روی پیام «ارسال شد به مدیر».
- تولید درس و ارزیابی تمرین با کمک AI و context اختصاصی پروژه.

### وضعیت فعلی پروژه

وضعیت فعلی از نظر محصول: MVP نسخه ۲ فعال است.

تخمین تکمیل:

- فاز ۱، onboarding + validation + ذخیره دیتابیس: انجام شده.
- فاز ۲، UI/UX کاربر، لندینگ، ورود با شماره، مسیر `/app/`: انجام شده در سطح MVP.
- فاز ۳، پنل مدیریت با login و CRUD پایه: انجام شده در سطح MVP.
- فاز ۴، آموزش + RAG داخلی + تولید درس/ارزیابی تمرین: انجام شده در سطح MVP، اما Knowledge Base واقعی شرکت هنوز جایگزین seed پیش‌فرض نشده است.

درصد تخمینی تکمیل کل پروژه فعلی: حدود 65 تا 70 درصد. پروژه قابل اجرا و deploy شده است، اما این وضعیت مربوط به MVP/فاز ۱ است.

وضعیت فاز ۲: هنوز پیاده‌سازی نشده و در مرحله طراحی معماری و زمان‌بندی است. تصمیم فعلی این است که فاز ۲ با سه بخش `CMS`، `Core` و `UI` جلو برود. CMS واقعی در اسپرینت‌های پایانی ساخته می‌شود، اما از ابتدا یک Fake CMS/Seed CMS روی schema واقعی ساخته می‌شود تا Core از همان قرارداد دیتابیسی آینده بخواند و بعداً اتصال CMS واقعی باعث بازنویسی Core نشود.

به‌روزرسانی اسپرینت ۰ فاز ۲ در تاریخ 2026-07-23: قرارداد دیتابیسی واقعی فاز ۲ به پروژه اضافه شد. migration جدید با شناسه `20260723_0003_phase2_schema` جدول‌های دوره، نسخه دوره، محتوای ۲۰ مرحله، KB اختصاصی دوره، پروفایل فاز ۲، ثبت‌نام دوره، پیشرفت مرحله‌ای، آزمون، تلاش آزمون و مدرک را اضافه می‌کند. همچنین Fake CMS Seed در `src/seed.py` یک دوره نمونه published با slug `personal-development-ai`، نسخه published شماره ۱، ۲۰ stage تاییدشده، ۳ سند KB و یک آزمون نهایی نمونه می‌سازد. این کار باعث می‌شود Core فاز ۲ از همین ابتدا از جدول‌های واقعی CMS بخواند و بعداً CMS واقعی فقط producer همین contract شود.

---

## ۲. معماری کلی

### زیرسیستم‌ها

```text
                  +----------------------+
                  |      Landing UI      |
                  |   landing/zito.html  |
                  +----------+-----------+
                             |
                             | POST /api/auth/phone
                             v
+----------------------------+----------------------------+
|                         FastAPI                         |
| src/main.py + src/api/routes.py                         |
|                                                            |
|  UI Routes: /, /app/, /admin/login, /admin                |
|  API Routes: onboarding, training, admin                  |
+-------------+-------------------+------------------------+
              |                   |
              | SQLAlchemy ORM    | HTTPX/OpenAI-compatible call
              v                   v
    +------------------+     +----------------------------+
    |    PostgreSQL    |     |  Arvancloud AIaaS Gateway  |
    | users/admins/... |     |  GPT-5.4-Mini              |
    +------------------+     +----------------------------+
              ^
              |
              | RAG retrieval via SQL ILIKE
              |
    +----------------------+
    | knowledge_documents  |
    | internal KB seed     |
    +----------------------+

Production:
Browser -> Arvan CDN/DNS -> Nginx :443 -> Uvicorn 127.0.0.1:8000 -> FastAPI
```

### ارتباط اجزا

- `src/main.py:14` برنامه FastAPI را می‌سازد و router اصلی را اضافه می‌کند.
- `src/main.py:22` فایل‌های landing را با مسیر `/landing-static` mount می‌کند.
- `src/api/routes.py` تمام APIهای داخلی را تعریف می‌کند.
- `src/db.py:12` اتصال SQLAlchemy را با `DATABASE_URL` می‌سازد.
- `src/models.py` مدل‌های دیتابیس را تعریف می‌کند.
- `src/lib/arvan_client.py:106` تابع `ask_ai` را به عنوان تنها نقطه تماس با Arvancloud AIaaS پیاده‌سازی می‌کند.
- `src/services/rag.py:21` context را از جدول `knowledge_documents` بازیابی می‌کند.
- `src/services/training.py` تولید درس و پاسخ آموزشی را با RAG + AI انجام می‌دهد.
- `src/services/validation.py` اعتبارسنجی پاسخ اولیه، سوال آموزشی و جواب تمرین را انجام می‌دهد.

### دلیل انتخاب معماری

- FastAPI انتخاب شده چون برای API سریع، ساده و async مناسب است.
- SQLAlchemy + Alembic انتخاب شده تا schema و migration قابل کنترل باشد.
- PostgreSQL برای production انتخاب شده چون پایدار، استاندارد و مناسب relationهای کاربران/پاسخ‌ها/پیشرفت است.
- تماس LLM در یک wrapper واحد متمرکز شده تا اگر endpoint یا فرمت Arvan تغییر کرد فقط `src/lib/arvan_client.py` تغییر کند.
- RAG فعلاً داخلی و SQL-based است چون هنوز Knowledge Base رسمی شرکت وجود ندارد؛ این مسیر برای MVP ساده، قابل فهم و کم‌هزینه است.
- UI به صورت HTML/CSS/JS server-rendered از FastAPI سرو می‌شود تا پیچیدگی build frontend در MVP کم بماند.

### معماری پیشنهادی فاز ۲

فاز ۲ باید از فاز فعلی جدا دیده شود. اصل اصلی طراحی:

```text
CMS تولید و تایید محتوا را مدیریت می‌کند.
Core فقط محتوای approved/published را مصرف می‌کند.
UI هر قالب آموزشی را با تجربه بصری اختصاصی نمایش می‌دهد.
```

در فاز ۲ کاربر دیگر پاسخ‌های فرم اولیه را با AI validation نمی‌فرستد. ورود با شماره موبایل و OTP انجام می‌شود، سپس فرم اطلاعات کاربر بدون AI check ذخیره می‌شود:

- نام و نام خانوادگی
- حوزه کاری
- منبع آشنایی با Zito
- زمان روزانه مطالعه

بعد کاربر دوره منتشرشده را انتخاب می‌کند و مسیر آموزشی را طی می‌کند.

#### Fake CMS در ابتدای فاز ۲

با توجه به تصمیم جدید پروژه، CMS اصلی در اسپرینت ۵ ساخته می‌شود. برای اینکه Core از ابتدا روی مسیر درست توسعه پیدا کند، در اسپرینت ۰ باید یک Fake CMS/Seed CMS ساخته شود:

```text
Fake CMS = UI ادمین و تولید AI ندارد،
ولی schema واقعی CMS را دارد و دیتابیس را با یک دوره نمونه published پر می‌کند.
```

کار اشتباه:

```text
Core از فایل hardcode یا mock جدا بخواند
بعداً CMS واقعی اضافه شود
بعد Core دوباره سیم‌کشی شود
```

کار درست:

```text
Core از جدول‌های واقعی CMS بخواند
اما محتوا فعلاً با seed ساخته شده باشد
```

قرارداد اصلی داده برای فاز ۲:

```text
courses
  ↓
course_versions
  ↓
course_stage_contents
  ↓
published version
  ↓
Core training engine
```

این versioning مهم است چون اگر اپراتور بعداً دوره را ویرایش کند، کاربری که وسط نسخه قبلی دوره است نباید ناگهان محتوای متفاوت ببیند.

#### ۲۰ قالب آموزشی فاز ۲

مسیر آموزشی فاز ۲ شامل ۲۰ قالب/مرحله است. لیست اولیه اعلام‌شده ۱۹ مورد داشت؛ تصمیم پیشنهادی این است که مورد ۲۰ به عنوان «پروژه نهایی / جمع‌بندی شخصی‌سازی‌شده» اضافه شود و بعد از آن آزمون نهایی و مدرک بیاید.

```text
01. خلاصه درس
02. فلش‌کارت‌ها و مرور سریع مفاهیم
03. پرسش و پاسخ
04. نمایش مسیر یادگیری
05. آزمون کوچک برای تثبیت یادگیری
06. سوال‌های چهارگزینه‌ای
07. مثال‌های واقعی
08. سناریوهای تعاملی
09. چک‌لیست اجرایی
10. تمرین عملی
11. ماموریت روزانه و چالش کوچک
12. گفت‌وگو با آواتار
13. مرور هوشمند
14. خلاصه صوتی درس
15. اینفوگرافیک مفاهیم مهم
16. نقشه ذهنی
17. کارت‌های نکات طلایی
18. اشتباهات رایج
19. مسیر شخصی‌سازی‌شده
20. پروژه نهایی / جمع‌بندی شخصی‌سازی‌شده
Final. آزمون نهایی و صدور مدرک
```

#### نقش‌های AI در فاز ۲

دو نقش AI باید جدا بمانند:

```text
AI شماره ۱: Content Generator
فقط در CMS واقعی استفاده می‌شود.
برای هر دوره و هر stage محتوای خام تولید می‌کند.
خروجی باید توسط اپراتور انسانی بازبینی/تایید شود.

AI شماره ۲: Avatar Tutor / Controller
در Core با کاربر تعامل دارد.
فقط روی RAG/KB نسخه منتشرشده دوره grounded می‌شود.
سوال کاربر، کنترل مسیر، آزمون نهایی و نمره‌دهی را مدیریت می‌کند.
```

#### زمان‌بندی پیشنهادی فاز ۲ با Fake CMS

| اسپرینت | بازه | تمرکز | خروجی |
|---|---:|---|---|
| ۰ - مدل داده + Fake CMS Seed | روز ۱ تا ۳ | schema واقعی فاز ۲، stage types، seed یک دوره نمونه با ۲۰ مرحله | دیتابیس آماده + یک دوره fake published |
| ۱ - Core ورود | روز ۴ تا ۸ | OTP، فرم اطلاعات بدون AI، انتخاب/ثبت‌نام دوره | کاربر وارد می‌شود و دوره fake را انتخاب می‌کند |
| ۲ - موتور ۲۰ مرحله | روز ۹ تا ۱۸ | خواندن از `course_stage_contents`، پیشروی، progress | کاربر ۲۰ مرحله را با محتوای seed طی می‌کند |
| ۳ - آواتار زنده + UI قالب‌ها | روز ۱۹ تا ۳۰ | RAG از KB همان دوره، avatar chat، UI اختصاصی ۲۰ قالب | تجربه آموزشی کامل با محتوای fake |
| ۴ - آزمون و مدرک | روز ۳۱ تا ۳۹ | آزمون، grading AI، certificate | مسیر کامل تا مدرک با course نمونه |
| ۵ - CMS واقعی | روز ۴۰ تا ۵۲ | CRUD دوره، آپلود KB، تولید AI، review/approve/publish | course واقعی جایگزین fake می‌شود |
| ۶ - تست نهایی | روز ۵۳ تا ۶۰ | تست با course واقعی، رفع باگ، deploy | فاز ۲ آماده ارائه |

---

## ۳. Stack فنی

### زبان و runtime

- Python production: `Python 3.12.3`
- سیستم production: `Ubuntu 24.04.1 LTS (Noble Numbat)`
- Git production: `git version 2.43.0`

### Backend framework

- FastAPI: `0.115.6`
- Uvicorn: `0.34.0`
- Starlette: `0.41.3`

### دیتابیس

- Production database: PostgreSQL
- نسخه production: `PostgreSQL 16.14 (Ubuntu 16.14-0ubuntu0.24.04.1)`
- Local quick test: SQLite با `sqlite:///./local_test.db`
- ORM: SQLAlchemy `2.0.36`
- Migration: Alembic `1.14.0`
- PostgreSQL driver: `psycopg` / `psycopg-binary` نسخه `3.2.13`

### Web server / deployment

- Nginx production: `nginx/1.24.0 (Ubuntu)`
- systemd service: `zito`
- TLS/SSL: Certbot + Let's Encrypt paths under `/etc/letsencrypt/live/zito.ir/`

### requirements.txt

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

### pip freeze فعلی local venv

```text
alembic==1.14.0
annotated-types==0.7.0
anyio==4.14.1
bcrypt==5.0.0
certifi==2026.6.17
cffi==2.1.0
click==8.4.2
colorama==0.4.6
cryptography==49.0.0
fastapi==0.115.6
h11==0.16.0
httpcore==1.0.9
httptools==0.8.0
httpx==0.28.1
idna==3.18
invoke==3.0.3
Mako==1.3.12
MarkupSafe==3.0.3
paramiko==5.0.0
psycopg==3.2.13
psycopg-binary==3.2.13
pycparser==3.0
pydantic==2.13.4
pydantic-settings==2.7.0
pydantic_core==2.46.4
PyNaCl==1.6.2
python-dotenv==1.0.1
PyYAML==6.0.3
SQLAlchemy==2.0.36
starlette==0.41.3
typing-inspection==0.4.2
typing_extensions==4.16.0
tzdata==2026.2
uvicorn==0.34.0
watchfiles==1.2.0
websockets==16.0
```

---

## ۴. ساختار پوشه‌ها و فایل‌ها

### درخت پروژه

```text
ZitoApp/
|-- .agents/
|-- landing/
|   |-- logo-z-transparent.png
|   |-- logo-z.png
|   |-- rocket-svgrepo-com.svg
|   |-- zito-avatar-transparent.png
|   |-- zito-avatar.png
|   +-- zito.html
|-- migrations/
|   |-- versions/
|   |   |-- 20260707_0001_initial.py
|   |   +-- 20260714_0002_admins.py
|   +-- env.py
|-- src/
|   |-- api/
|   |   |-- __init__.py
|   |   +-- routes.py
|   |-- lib/
|   |   |-- __init__.py
|   |   +-- arvan_client.py
|   |-- prompts/
|   |   |-- __init__.py
|   |   |-- initial_answer_validation.md
|   |   |-- training_answer_evaluation.md
|   |   |-- training_lesson_generation.md
|   |   +-- training_question_validation.md
|   |-- services/
|   |   |-- __init__.py
|   |   |-- json_utils.py
|   |   |-- rag.py
|   |   |-- training.py
|   |   +-- validation.py
|   |-- templates/
|   |   |-- admin.html
|   |   |-- admin_login.html
|   |   +-- chat.html
|   |-- __init__.py
|   |-- config.py
|   |-- db.py
|   |-- main.py
|   |-- models.py
|   |-- schemas.py
|   |-- security.py
|   +-- seed.py
|-- tools/
|   +-- zito-secrets.ps1
|-- .env
|-- .env.example
|-- .gitignore
|-- alembic.ini
|-- PROJECT_CONTEXT.md
|-- README.md
|-- requirements.txt
|-- SECURITY.md
+-- SETUP.md
```

نکته: `.env` در local وجود دارد، ولی طبق `.gitignore` وارد Git نمی‌شود. `.secrets/` نیز وجود دارد اما در tree بالا نمایش داده نشده چون عمداً ignore و محرمانه است.

### نقش فایل‌ها و پوشه‌های مهم

- `.env`: تنظیمات واقعی local، شامل DB URL، Arvan endpoint/key و secretهای ادمین. نباید commit شود.
- `.env.example`: نمونه امن env برای اعضای تیم، بدون secret واقعی.
- `.gitignore`: جلوگیری از commit شدن `.env`، `.secrets/`، دیتابیس local، venv و فایل‌های build/cache.
- `PROJECT_CONTEXT.md`: خلاصه معماری و قوانین پروژه برای sessionهای بعدی agent.
- `README.md`: معرفی کوتاه پروژه و مسیرهای اصلی.
- `SECURITY.md`: سیاست نگهداری secretها و استفاده از password manager محلی.
- `SETUP.md`: راه‌اندازی local، PostgreSQL، Arvan mode و تست دستی.
- `alembic.ini`: تنظیم Alembic؛ مقدار واقعی DB در runtime از `.env` خوانده می‌شود.
- `landing/zito.html`: لندینگ اصلی با UI کهکشانی، ورود شماره موبایل و redirect به `/app/`.
- `landing/logo-z*.png` و `landing/zito-avatar*.png`: assets لوگو و آواتار مشترک landing/chat.
- `migrations/env.py`: اتصال Alembic به `DATABASE_URL` از `src.config`.
- `migrations/versions/20260707_0001_initial.py`: migration اولیه برای users/questions/answers/progress/knowledge.
- `migrations/versions/20260714_0002_admins.py`: migration جدول admins.
- `src/main.py`: ساخت FastAPI app، mount assets، UI routes و startup seed.
- `src/api/routes.py`: تمام APIهای داخلی برای admin، onboarding، auth phone و training.
- `src/config.py`: بارگذاری env با Pydantic Settings و guardهای production.
- `src/db.py`: ساخت engine و session SQLAlchemy.
- `src/models.py`: مدل‌های ORM و relationهای دیتابیس.
- `src/schemas.py`: مدل‌های ورودی/خروجی Pydantic برای APIها.
- `src/security.py`: hash رمز ادمین، login session cookie و guard admin.
- `src/seed.py`: seed سوال‌های اولیه و Knowledge Base پیش‌فرض.
- `src/lib/arvan_client.py`: تنها client مستقیم برای Arvancloud AIaaS.
- `src/prompts/*.md`: system promptهای قابل ویرایش برای validation/training.
- `src/services/rag.py`: retrieval ساده از جدول `knowledge_documents`.
- `src/services/training.py`: تولید درس، تشخیص سوال، fallback درس/پاسخ و استفاده از RAG.
- `src/services/validation.py`: validation پاسخ اولیه، سوال آموزشی و تمرین.
- `src/services/json_utils.py`: استخراج JSON معتبر از پاسخ AI.
- `src/templates/chat.html`: UI اصلی `/app/` شامل onboarding، سیاره آموزشی، درس و modal پاسخ تمرین.
- `src/templates/admin_login.html`: صفحه login مدیر.
- `src/templates/admin.html`: پنل مدیریت کاربران/پاسخ‌ها.
- `tools/zito-secrets.ps1`: password manager محلی با DPAPI برای secretهای local؛ خودش secret ندارد.

---

## ۵. دیتابیس

### منبع schema

- مدل ORM: `src/models.py`
- migrations:
  - `migrations/versions/20260707_0001_initial.py`
  - `migrations/versions/20260714_0002_admins.py`
  - `migrations/versions/20260723_0003_phase2_schema.py`

### جدول `users`

تعریف مدل: `src/models.py:9`

| فیلد | نوع | nullable | توضیح |
|---|---|---:|---|
| `id` | integer | no | primary key |
| `full_name` | varchar(255) | yes | نام و نام خانوادگی تاییدشده |
| `username` | varchar(100) | yes | در v2 معمولاً شماره موبایل کاربر |
| `profession` | varchar(255) | yes | مسیر/حوزه آموزشی کاربر |
| `created_at` | timestamptz | no | زمان ساخت |
| `updated_at` | timestamptz | no | زمان آخرین تغییر |

روابط:

- یک کاربر چند `answers` دارد.
- یک کاربر حداکثر یک `user_progress` دارد.
- حذف کاربر باعث حذف cascade پاسخ‌ها و progress می‌شود.

### جدول `admins`

تعریف مدل: `src/models.py:27`

| فیلد | نوع | nullable | توضیح |
|---|---|---:|---|
| `id` | integer | no | primary key |
| `username` | varchar(100) | no | unique |
| `password_hash` | varchar(255) | no | hash شده با PBKDF2-SHA256 |
| `is_active` | boolean | no | فعال/غیرفعال |
| `created_at` | timestamptz | no | زمان ساخت |
| `updated_at` | timestamptz | no | زمان تغییر |

### جدول `questions`

تعریف مدل: `src/models.py:38`

| فیلد | نوع | nullable | توضیح |
|---|---|---:|---|
| `id` | integer | no | primary key |
| `key` | varchar(80) | no | unique، مثل `identity` یا `profession` |
| `text` | text | no | متن سوال |
| `sort_order` | integer | no | ترتیب سوال، unique |
| `is_active` | boolean | no | فعال بودن سوال |
| `created_at` | timestamptz | no | زمان ساخت |

### جدول `answers`

تعریف مدل: `src/models.py:51`

| فیلد | نوع | nullable | توضیح |
|---|---|---:|---|
| `id` | integer | no | primary key |
| `user_id` | integer | no | FK به `users.id` با `ondelete=CASCADE` |
| `question_id` | integer | no | FK به `questions.id` با `ondelete=CASCADE` |
| `answer_text` | text | no | پاسخ تاییدشده کاربر |
| `is_valid` | boolean | no | نتیجه validation |
| `validation_reason` | text | yes | دلیل AI برای validation |
| `validated_at` | timestamptz | no | زمان تایید |

### جدول `user_progress`

تعریف مدل: `src/models.py:66`

| فیلد | نوع | nullable | توضیح |
|---|---|---:|---|
| `id` | integer | no | primary key |
| `user_id` | integer | no | FK unique به `users.id` |
| `current_step` | integer | no | مرحله فعلی آموزش |
| `percentage` | integer | no | درصد پیشرفت |
| `last_lesson` | text | yes | آخرین lesson تولیدشده، فعلاً به صورت string |
| `updated_at` | timestamptz | no | زمان آخرین تغییر |

### جدول `knowledge_documents`

تعریف مدل: `src/models.py:79`

| فیلد | نوع | nullable | توضیح |
|---|---|---:|---|
| `id` | integer | no | primary key |
| `title` | varchar(255) | no | عنوان سند دانشی |
| `content` | text | no | محتوای آموزشی |
| `tags` | varchar(255) | yes | tagهای ساده برای جستجو |
| `created_at` | timestamptz | no | زمان ساخت |

### جدول‌های فاز ۲ / Fake CMS

Migration مرجع: `migrations/versions/20260723_0003_phase2_schema.py`

این جدول‌ها فعلاً برای Sprint 0 اضافه شده‌اند و توسط `seed_phase2_fake_course` در `src/seed.py` با داده نمونه پر می‌شوند. هنوز APIهای Core فاز ۲ و CMS واقعی روی آن‌ها کامل نشده‌اند.

| جدول | نقش | وضعیت فعلی |
|---|---|---|
| `courses` | تعریف دوره؛ شامل `title`, `slug`, `domain`, `status` | یک دوره sample با slug `personal-development-ai` و status `published` seed می‌شود |
| `course_versions` | نسخه‌بندی محتوای دوره برای جلوگیری از تغییر ناگهانی مسیر کاربر | نسخه `1` دوره sample با status `published` seed می‌شود |
| `course_stage_contents` | محتوای ۲۰ قالب آموزشی هر نسخه دوره در `content_json` | ۲۰ stage تاییدشده با `review_status=approved` seed می‌شود |
| `course_kb_documents` | KB اختصاصی هر دوره برای RAG آواتار و کنترل مسیر | ۳ سند sample برای دوره فاز ۲ seed می‌شود |
| `user_profiles_v2` | پروفایل جدید فاز ۲ بعد از OTP؛ فرم بدون AI validation | schema آماده، هنوز Core API فاز ۲ روی آن کامل نشده |
| `profile_builder_answers` | پاسخ خام/ساختاریافته هر قدم فرم پروفایل | schema آماده |
| `user_course_enrollments` | ثبت‌نام کاربر در یک course version مشخص | schema آماده |
| `user_stage_progress` | پیشرفت کاربر در هر stage از مسیر ۲۰ مرحله‌ای | schema آماده |
| `exams` | آزمون نهایی هر نسخه دوره، سوال‌ها در `questions_json` | یک آزمون sample با `passing_score=70` seed می‌شود |
| `exam_attempts` | پاسخ‌ها، نمره و feedback آزمون کاربر | schema آماده |
| `certificates` | مدرک صادرشده پس از قبولی آزمون | schema آماده |

قرارداد مرحله‌های آموزشی فاز ۲:

```text
01 lesson_summary
02 flashcards
03 qa
04 learning_path
05 mini_quiz
06 multiple_choice
07 real_examples
08 interactive_scenario
09 checklist
10 practical_exercise
11 daily_mission
12 avatar_dialog
13 smart_review
14 audio_summary
15 infographic
16 mind_map
17 golden_tips
18 common_mistakes
19 personalized_path
20 final_project
```

### جدول `alembic_version`

در production وجود دارد و نسخه migration جاری را نگه می‌دارد:

- `version_num`: varchar, primary tracking field

### وضعیت production data

گزارش مستقیم از production در تاریخ 2026-07-20:

| جدول | تعداد رکورد |
|---|---:|
| `users` | 16 |
| `admins` | 1 |
| `questions` | 2 |
| `answers` | 29 |
| `user_progress` | 12 |
| `knowledge_documents` | 6 |

جدول خالی وجود ندارد. اما `knowledge_documents` فعلاً Knowledge Base واقعی شرکت نیست و فقط seed پیش‌فرض دارد. همچنین `user_progress` برای همه کاربران وجود ندارد؛ 12 رکورد progress برای 16 کاربر ثبت شده، یعنی بعضی کاربران وارد آموزش نشده‌اند یا progress آن‌ها هنوز ساخته نشده است.

نکته فاز ۲: migration جدید `20260723_0003_phase2_schema` در local/test با موفقیت اجرا شده است. اجرای آن روی production باید در زمان deploy فاز ۲ با backup دیتابیس و دستور Alembic کنترل‌شده انجام شود.

### سوال‌های onboarding در production

```text
1 | identity   | sort_order=1 | سلام، من زیتو هستم. اول نام و نام خانوادگی واقعی خودت را بنویس.
2 | profession | sort_order=2 | حالا بگو می خواهی در کدام مسیر با کمک هوش مصنوعی یاد بگیری: حسابداری، روانشناسی یا حقوق؟
```

---

## ۶. اتصال به Arvancloud AIaaS

### Endpointهای Arvancloud

در پروژه فقط یک gateway/model اصلی استفاده می‌شود:

| نام منطقی | مدل | env | هدف |
|---|---|---|---|
| Arvan AIaaS Chat Gateway | `GPT-5.4-Mini` | `ARVAN_API_BASE_URL` + `/chat/completions` | validation پاسخ اولیه، validation سوال آموزشی، تولید درس، ارزیابی تمرین |

فرمت endpoint از `.env.example`:

```text
https://arvancloudai.ir/gateway/models/GPT-5.4-Mini/YOUR_ENDPOINT_TOKEN/v1
```

در runtime، `src/lib/arvan_client.py:121` به انتهای آن `/chat/completions` اضافه می‌کند. مقدار واقعی endpoint token و API key عمداً در گزارش redacted است و فقط در `.env`/vault local یا `.env` سرور نگهداری می‌شود.

### تابع تماس با Arvan

فایل کامل `src/lib/arvan_client.py`:

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

### Promptها و use-caseها

| فایل prompt | استفاده |
|---|---|
| `src/prompts/initial_answer_validation.md` | بررسی پاسخ onboarding؛ نام واقعی و مسیر آموزشی را strict چک می‌کند. |
| `src/prompts/training_question_validation.md` | بررسی معنی‌دار و مرتبط بودن سوال آموزشی کاربر. |
| `src/prompts/training_lesson_generation.md` | تولید درس مرحله فعلی با user context و RAG context. |
| `src/prompts/training_answer_evaluation.md` | ارزیابی جواب تمرین و تولید feedback/score. |

### Knowledge Base / RAG

Knowledge Base فعلی در Arvan bucket نیست؛ در جدول داخلی `knowledge_documents` قرار دارد. مسیر RAG:

```text
user profile + user question/current lesson
        |
        v
src/services/rag.py retrieve_context()
        |
        v
SELECT knowledge_documents WHERE title/content/tags ILIKE terms
        |
        v
rag_context inside user_message
        |
        v
Arvancloud AIaaS GPT-5.4-Mini /chat/completions
```

تابع retrieval:

- `src/services/rag.py:7`: `build_user_context`
- `src/services/rag.py:21`: `retrieve_context`
- جستجو با `ILIKE` روی `title`، `content` و `tags`
- محدودیت پیش‌فرض: `limit=3`

اسناد seed شده در production:

| id | title | tags | content length |
|---:|---|---|---:|
| 1 | حسابداری و هوش مصنوعی: شروع امن | `accounting,ai,حسابداری,هوش مصنوعی,finance` | 372 |
| 2 | حسابداری و هوش مصنوعی: تمرین مرحله ای | `accounting,ai,حسابداری,prompt,training` | 331 |
| 3 | روانشناسی و هوش مصنوعی: مرزهای حرفه ای | `psychology,ai,روانشناسی,ethics,mental health` | 353 |
| 4 | روانشناسی و هوش مصنوعی: تمرین یادگیری | `psychology,ai,روانشناسی,training,empathy` | 349 |
| 5 | حقوق و هوش مصنوعی: استفاده مسئولانه | `law,ai,حقوق,legal,contract` | 358 |
| 6 | حقوق و هوش مصنوعی: تمرین قرارداد | `law,ai,حقوق,contract,prompt,training` | 318 |

---

## ۷. API های داخلی پروژه

### UI routes

| متد | مسیر | ورودی | خروجی | کار |
|---|---|---|---|---|
| GET | `/` | ندارد | HTML | لندینگ `landing/zito.html` را برمی‌گرداند. |
| GET | `/chat` | query اختیاری | Redirect 303 | مسیر legacy را به `/app/` منتقل می‌کند. |
| GET | `/app/` | ندارد | HTML | رابط کاربری اصلی چت/آموزش. |
| GET | `/admin/login` | ندارد | HTML | صفحه login ادمین. |
| GET | `/admin` | cookie ادمین | HTML یا redirect | اگر login معتبر باشد پنل ادمین، وگرنه redirect به login. |

### System routes

| متد | مسیر | ورودی | خروجی | کار |
|---|---|---|---|---|
| GET | `/health` | ندارد | `{"status":"ok","database":"ok"}` | تست اتصال API و دیتابیس با `SELECT 1`. |
| GET | `/docs` | ندارد | Swagger UI | مستند خودکار FastAPI. |
| GET | `/redoc` | ندارد | ReDoc | مستند خودکار FastAPI. |
| GET | `/openapi.json` | ندارد | JSON schema | OpenAPI schema. |

### Auth / user entry

| متد | مسیر | ورودی | خروجی | کار |
|---|---|---|---|---|
| POST | `/api/auth/phone` | `PhoneLoginIn { phone: str }` | `PhoneLoginOut { user_id, username, redirect_url }` | شماره موبایل را normalize می‌کند، اگر user نبود می‌سازد، `redirect_url="/app/"` برمی‌گرداند. |

قانون شماره موبایل در `src/api/routes.py:39`: فقط فرمت `09xxxxxxxxx` معتبر است. `0098` و `98` به `0` تبدیل می‌شوند.

### Onboarding

| متد | مسیر | ورودی | خروجی | کار |
|---|---|---|---|---|
| POST | `/api/onboarding/start` | ندارد | `OnboardingStartOut` | سوال‌های seed را آماده می‌کند، user جدید می‌سازد و سوال اول را برمی‌گرداند. |
| GET | `/api/onboarding/{user_id}/state` | path `user_id` | `OnboardingStateOut` | وضعیت onboarding و سوال بعدی کاربر را می‌دهد. |
| POST | `/api/onboarding/{user_id}/answer` | `AnswerIn { question_id, answer_text }` | `OnboardingAnswerOut` | پاسخ را با Arvan validate می‌کند؛ اگر valid بود ذخیره و فیلد profile را update می‌کند. |

رفتار invalid:

- ذخیره نمی‌شود.
- `guidance` برمی‌گردد.
- همان سوال دوباره پرسیده می‌شود.

### Admin APIs

همه endpointهای admin به جز login/logout به cookie معتبر ادمین نیاز دارند. guard در `src.security.require_admin` است.

| متد | مسیر | ورودی | خروجی | کار |
|---|---|---|---|---|
| POST | `/api/admin/login` | `AdminLoginIn { username, password }` | `AdminLoginOut { ok, username }` | احراز هویت admin و تنظیم cookie `zito_admin_session`. |
| POST | `/api/admin/logout` | cookie | `{"ok": true}` | حذف cookie ادمین. |
| GET | `/api/admin/me` | cookie | `{"ok": true}` | تست معتبر بودن login. |
| GET | `/api/admin/users` | cookie | `list[UserOut]` | لیست کاربران و پاسخ‌هایشان. |
| GET | `/api/admin/users/{user_id}` | cookie + path | `UserOut` | جزئیات یک کاربر. |
| PUT | `/api/admin/answers/{answer_id}` | `AdminAnswerUpdate { answer_text }` | `AnswerOut` | ویرایش پاسخ و sync فیلد profile مرتبط. |
| DELETE | `/api/admin/users/{user_id}` | path | `{"deleted": true}` | حذف کاربر و داده‌های cascade. |

### Training APIs

| متد | مسیر | ورودی | خروجی | کار |
|---|---|---|---|---|
| POST | `/api/training/knowledge` | `KnowledgeIn { title, content, tags }` | `KnowledgeOut` | افزودن سند KB؛ نیازمند admin. |
| POST | `/api/training/{user_id}/lesson` | path `user_id` | `TrainingLessonOut` | ساخت/لود progress و تولید lesson با RAG + Arvan. |
| POST | `/api/training/{user_id}/question` | `TrainingQuestionIn { question }` | JSON dict | سوال آموزشی را validate و با RAG پاسخ می‌دهد. |
| POST | `/api/training/{user_id}/answer` | `TrainingAnswerIn { lesson, check_question, answer_text }` | JSON dict | جواب تمرین را evaluate می‌کند و در صورت pass، progress را افزایش می‌دهد. |
| POST | `/api/training/{user_id}/message` | `TrainingMessageIn { lesson, check_question, message }` | JSON dict | endpoint یکپارچه UI؛ اگر message سوال بود جواب می‌دهد، وگرنه تمرین را ارزیابی می‌کند. |

### فایل schemas

مدل‌های Pydantic در `src/schemas.py` تعریف شده‌اند. مهم‌ترین‌ها:

- `PhoneLoginIn`, `PhoneLoginOut`
- `AnswerIn`, `OnboardingAnswerOut`
- `UserOut`, `AnswerOut`
- `AdminLoginIn`, `AdminLoginOut`, `AdminAnswerUpdate`
- `KnowledgeIn`, `KnowledgeOut`
- `TrainingLessonOut`, `TrainingMessageIn`, `TrainingAnswerIn`, `TrainingQuestionIn`

---

## ۸. تاریخچه‌ی Git

### خروجی کامل `git log --oneline --all`

```text
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
501158f Tune landing background gradient
1a2579f Refine landing cosmic motion effect
c1bfc56 Add database-backed admin login
d5e545a Start version 2 phone login flow
5ab6e01 Bypass proxy for Arvan client
4fbee09 Polish Zito dark UI
881610a Initial Zito app
```

### توضیح commitهای مهم

- `76091ee Initial commit`: commit اولیه ریپوی دوم `elmsaz/elmsazZito` که فقط README اولیه داشت.
- `aab3cbf Merge elmsaz repository history`: اتصال تاریخچه ریپوی دوم به تاریخچه اصلی پروژه بدون force push و بدون تغییر فایل‌های Zito.
- `5c0ab1c Add technical project report`: افزودن مستند فنی کامل پروژه در `PROJECT_REPORT.md`.
- `881610a Initial Zito app`: پایه FastAPI، دیتابیس، onboarding، Arvan client، prompts، RAG seed و UI اولیه را ساخت.
- `4fbee09 Polish Zito dark UI`: UI تیره و ظاهر شکیل‌تر برای تجربه چت/پنل اضافه شد.
- `5ab6e01 Bypass proxy for Arvan client`: در `httpx.AsyncClient` مقدار `trust_env=False` اضافه شد تا proxy/env سیستم باعث خرابی تماس Arvan نشود.
- `d5e545a Start version 2 phone login flow`: ورود کاربر با شماره موبایل و اتصال آن به username/user record اضافه شد.
- `c1bfc56 Add database-backed admin login`: پنل ادمین از حالت ساده به login دیتابیس‌محور با password hash و cookie session منتقل شد.
- `1a2579f`, `501158f`, `655db1f`, `964e902`: اصلاحات visual landing، گرادیان، motion و استفاده از artwork شفاف.
- `c28e85d Add resilient training fallback flow`: fallback برای آموزش اضافه شد تا اگر AI/RAG خطا داد، جریان کاملاً قطع نشود.
- `a7a9461 Use clean app URL for chat entry`: مسیر کاربر از `/chat?user_id=...` به `/app/` تمیز شد و user_id در localStorage مدیریت می‌شود.
- `2aa6841 Redesign training chat flow with planet stage`: UX جدید آموزش با سیاره حوزه انتخاب‌شده و modal پاسخ تمرین اضافه شد.
- `cf55c97 Unify UI typography with Yekan`: فونت UI به سمت Yekan یکپارچه شد.
- `0c3a37d Use landing artwork in chat UI`: لوگو و آواتار chat از assets لندینگ استفاده کردند.
- `558867b Unify Persian frontend font`: font inheritance برای landing/chat/admin/login یکدست شد.
- `9946fde Harden environment and secret handling`: `.gitignore`، `SECURITY.md` و guard production secrets اضافه شد.
- `660ab15 Relax production admin env guard`: guard مربوط به `ADMIN_PASSWORD` اصلاح شد تا deployهای production با admin موجود نخوابند؛ رمز seed فقط هنگام ساخت اولین admin چک می‌شود.
- `4b02592 Add local secrets manager`: ابزار محلی DPAPI برای نگهداری secretها اضافه شد. این commit runtime production را تغییر نمی‌دهد.

### وضعیت GitHub و production

- آخرین commit روی هر دو GitHub repo در زمان به‌روزرسانی 2026-07-22: `5c0ab1c`
- ریپوی `TheAlta/ZitoApp`: روی `5c0ab1c`
- ریپوی `elmsaz/elmsazZito`: روی `5c0ab1c`
- commit اجراشده روی production در آخرین SSH check: `660ab15`
- تفاوت production با GitHub: commitهای بعد از `660ab15` شامل hardening مستندات/secret handling، ابزار local secrets manager، merge تاریخچه ریپوی دوم و `PROJECT_REPORT.md` هستند. این تغییرات runtime-critical نیستند، اما برای نظم تیمی بهتر است در deploy بعدی سرور هم pull شود.

---

## ۹. زیرساخت و Deploy

### سرور

- Provider: Arvancloud cloud server / ابرک
- IP: `185.97.119.60`
- Hostname: `zito`
- OS: `Ubuntu 24.04.1 LTS (Noble Numbat)`
- Kernel: `Linux 6.8.0-45-generic x86_64`
- User runtime: `ubuntu`
- مسیر پروژه روی سرور: `/opt/zito/app`

### وضعیت سرویس‌ها

در آخرین بررسی:

```text
systemctl is-active zito  -> active
systemctl is-active nginx -> active
https://zito.ir/app/      -> HTTP 200
https://zito.ir/health    -> HTTP 200
```

### systemd service

فایل: `/etc/systemd/system/zito.service`

```ini
[Unit]
Description=Zito FastAPI app
After=network.target postgresql.service

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/zito/app
EnvironmentFile=/opt/zito/app/.env
ExecStart=/opt/zito/app/.venv/bin/python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

نکات:

- برنامه فقط روی `127.0.0.1:8000` listen می‌کند.
- اینترنت مستقیم به Uvicorn وصل نیست؛ Nginx reverse proxy است.
- env production از `/opt/zito/app/.env` خوانده می‌شود.

### Nginx

symlink:

```text
/etc/nginx/sites-enabled/zito -> /etc/nginx/sites-available/zito
```

کانفیگ:

```nginx
server {
    server_name zito.ir www.zito.ir 185.97.119.60;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/zito.ir/fullchain.pem; # managed by Certbot
    ssl_certificate_key /etc/letsencrypt/live/zito.ir/privkey.pem; # managed by Certbot
    include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem; # managed by Certbot
}

server {
    if ($host = zito.ir) {
        return 301 https://$host$request_uri;
    } # managed by Certbot

    listen 80;
    server_name zito.ir www.zito.ir 185.97.119.60;
    return 404; # managed by Certbot
}
```

نکته قابل بهبود: بخش HTTP فقط برای `zito.ir` redirect دارد؛ برای `www.zito.ir` rule جداگانه explicit دیده نشد و fallback فعلی `return 404` است. باید در hardening بعدی بررسی شود.

### دامنه و SSL

- دامنه: `zito.ir`
- DNS/CDN در پنل Arvancloud تنظیم شده است.
- رکورد A برای `@` به `185.97.119.60` اشاره می‌کند.
- SSL توسط Certbot مدیریت می‌شود.
- مسیر certificate: `/etc/letsencrypt/live/zito.ir/fullchain.pem`
- مسیر private key: `/etc/letsencrypt/live/zito.ir/privkey.pem`

### Deploy فعلی

مسیر استاندارد deploy دستی:

```bash
cd /opt/zito/app
git pull --ff-only
.venv/bin/python -m compileall src
.venv/bin/python -c "from src.config import get_settings; get_settings(); print('settings-ok')"
sudo systemctl restart zito
sudo systemctl is-active zito
```

بعد از deploy:

```bash
curl https://zito.ir/health
curl https://zito.ir/app/
```

### Secretها و env در server/local

متغیرهای لازم:

```text
APP_NAME
APP_ENV
AUTO_CREATE_TABLES
DATABASE_URL
ARVAN_API_BASE_URL
ARVAN_API_KEY
ARVAN_MODEL
ARVAN_TIMEOUT_SECONDS
ARVAN_MOCK_AI
ADMIN_USERNAME
ADMIN_PASSWORD
ADMIN_SESSION_SECRET
ADMIN_SESSION_DAYS
```

رمز SSH سرور داخل `.env` نیست و نباید باشد. محل مناسب آن password manager یا SSH key است. برای local، ابزار `tools/zito-secrets.ps1` ساخته شده و secretها را در `.secrets/zito-vault.local.json` به شکل DPAPI-encrypted نگه می‌دارد. پوشه `.secrets/` در Git ignore شده است.

---

## ۱۰. تصمیمات فنی مهم و دلایل آن‌ها

### FastAPI به جای Django/Flask

FastAPI برای API-first بودن پروژه، type hints، Pydantic schema و async AI calls مناسب‌تر بود. پروژه فعلاً نیاز به admin سنگین Django نداشت.

### SQLAlchemy + Alembic

برای حفظ کنترل روی schema و migrationها انتخاب شد. مدل‌ها در `src/models.py` هستند و migrations در `migrations/versions`.

### PostgreSQL برای production، SQLite برای local quick test

SQLite برای تست سریع local بدون نصب DB مناسب است. PostgreSQL برای production پایدارتر و مناسب‌تر برای relationها و رشد داده است.

### Wrapper واحد Arvan

تمام تماس‌های LLM در `src/lib/arvan_client.py` متمرکز شده‌اند. مزیت:

- تغییر endpoint/model فقط در یک نقطه.
- مدیریت خطاها یکدست.
- امکان mock mode برای توسعه local.
- جلوگیری از پراکندگی API key در کد.

### RAG داخلی به جای Arvan Bucket در MVP

چون Knowledge Base رسمی شرکت هنوز داده نشده، برای MVP جدول `knowledge_documents` ساخته شد. این تصمیم باعث شد آموزش و RAG قابل تست شود بدون وابستگی به bucket خارجی. بعداً می‌توان آن را به KB رسمی یا vector database منتقل کرد.

### Admin DB-backed login

در نسخه‌های قبلی admin ساده‌تر بود. بعداً جدول `admins` اضافه شد و رمز با PBKDF2-SHA256 hash می‌شود. این امن‌تر از نگهداری رمز plain در کد است.

### Clean URL `/app/`

برای جلوگیری از URLهایی مثل `/chat?user_id=4` مسیر کاربر به `/app/` منتقل شد و user_id در localStorage نگه داشته می‌شود.

### UI server-rendered HTML

فعلاً build tool/frontend framework اضافه نشده تا MVP سریع‌تر deploy شود. هزینه‌اش این است که با بزرگ شدن UI، نگهداری فایل‌های HTML بزرگ سخت‌تر می‌شود.

---

## ۱۱. مشکلات حل‌شده و راه‌حل‌ها

### ۱. اجرای PowerShell venv به خاطر Execution Policy

مشکل: اجرای `.\.venv\Scripts\Activate.ps1` با خطای script disabled متوقف می‌شد.  
راه‌حل: به جای activate کردن venv، مستقیم از Python داخل venv استفاده شد:

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

### ۲. خطای Unicode در تماس Arvan

مشکل: خطای `ascii codec can't encode characters` هنگام ارسال متن فارسی.  
راه‌حل: مسیر ارسال request اصلاح شد و از JSON/UTF-8 صحیح استفاده شد. همچنین در client از `httpx` با json payload استفاده می‌شود.

### ۳. دخالت proxy محیط در تماس Arvan

مشکل: تماس با Arvan گاهی از proxy/env سیستم تاثیر می‌گرفت.  
راه‌حل: در `src/lib/arvan_client.py:139` مقدار `trust_env=False` گذاشته شد.

### ۴. validation خیلی ضعیف برای نام

مشکل: پاسخ‌هایی مثل «قوانینت رو بگو» یا «نمی گم» ممکن بود پذیرفته شود.  
راه‌حل: prompt `initial_answer_validation.md` سخت‌گیرتر شد و mock/fallback هم برای سوال نام حداقل دو بخش نام و نبود عدد/درخواست سیستم را چک می‌کند.

### ۵. بعد از onboarding پیام اشتباه «ارسال شد به مدیر»

مشکل: flow کاربر بعد از تایید اطلاعات متوقف می‌شد.  
راه‌حل: UI و API flow تغییر کرد تا کاربر وارد آموزش و سپس مرحله سیاره/درس شود.

### ۶. admin panel برای کاربر قابل مشاهده بود

مشکل: پنل مدیریت باید جدا و محافظت‌شده باشد.  
راه‌حل: routeهای `/admin` و `/admin/login` جدا شدند و APIهای `/api/admin/*` با `require_admin` محافظت شدند.

### ۷. production env guard زیادی سخت‌گیر بود

مشکل: guard امنیتی اولیه اگر `ADMIN_PASSWORD` در `.env` production placeholder بود، کل settings را fail می‌کرد؛ حتی اگر admin قبلاً در دیتابیس وجود داشت.  
راه‌حل: در commit `660ab15` guard عمومی برای `ADMIN_PASSWORD` برداشته شد و فقط هنگام seed اولین admin در `src/seed.py:105` بررسی می‌شود.

### ۸. خطر commit شدن secretها

مشکل: پروژه نیاز به روال تیمی برای secretها داشت.  
راه‌حل:

- `.gitignore` سخت‌گیرتر شد.
- `.env.example` فقط placeholder دارد.
- `SECURITY.md` اضافه شد.
- ابزار local DPAPI password manager در `tools/zito-secrets.ps1` اضافه شد.
- `.secrets/` ignore شد.

---

## ۱۲. کارهای ناقص یا باقی‌مانده

### محصول و آموزش

- Knowledge Base واقعی شرکت هنوز وارد نشده است؛ فعلاً seed پیش‌فرض دارد.
- RAG فعلی lexical و ساده است (`ILIKE`) و vector search/embedding ندارد.
- مسیرهای آموزشی فقط سه حوزه دارند و ساختار course/chapter رسمی ندارند.
- `last_lesson` در `user_progress` فعلاً string ذخیره می‌شود؛ بهتر است JSONB یا جدول lesson/session مستقل شود.
- progress فعلی هر pass را 25 درصد افزایش می‌دهد؛ ساختار pedagogical دقیق‌تر لازم است.
- فاز ۲ هنوز پیاده‌سازی نشده و باید با schema واقعی CMS و Fake CMS/Seed CMS شروع شود.
- در فاز ۲ باید قرارداد JSON هرکدام از ۲۰ قالب آموزشی مشخص شود تا Core و UI از ابتدا با CMS واقعی سازگار باشند.
- مرحله ۲۰ باید به صورت رسمی تایید شود. پیشنهاد فعلی: «پروژه نهایی / جمع‌بندی شخصی‌سازی‌شده».

### Backend/API

- test suite خودکار وجود ندارد.
- rate limiting برای APIهای auth/AI وجود ندارد.
- request logging/structured logging کامل نیست.
- error monitoring مثل Sentry یا logging مرکزی وجود ندارد.
- OpenAPI docs وجود دارد، اما مستند رسمی request/response با مثال هنوز کامل نشده است.
- endpointهای admin برای ساخت/ویرایش admin users هنوز کامل نیستند.
- APIهای فاز ۲ هنوز ساخته نشده‌اند: OTP، profile v2، enroll، stage engine، avatar chat v2، exam و certificate.
- CMS واقعی فاز ۲ هنوز ساخته نشده است: CRUD دوره، upload KB، AI generation async، review/approve/publish.

### امنیت

- admin cookie در `src/security.py:62` با `secure=False` تنظیم شده؛ برای production بهتر است `secure=True` شود.
- ورود SSH هنوز password-based است؛ بهتر است SSH key و سپس disable password login انجام شود.
- secretهای production در فایل `.env` سرور هستند؛ بهتر است در مرحله بعد به secret manager یا حداقل permission سخت‌گیرانه‌تر منتقل شوند.
- API key آروان قبلاً در چت مطرح شده؛ باید در dashboard آروان rotate شود.
- وضعیت Git در زمان به‌روزرسانی 2026-07-22: فایل‌های tracked شامل `.env`، `.secrets/`، دیتابیس local یا private key واقعی نیستند. موارد دیده‌شده در `.env.example` و `SETUP.md` placeholder آموزشی هستند.

### Deploy/DevOps

- CI/CD وجود ندارد؛ deploy دستی با `git pull` و `systemctl restart` انجام می‌شود.
- دو ریپوی GitHub همزمان نگهداری می‌شوند: `TheAlta/ZitoApp` و `elmsaz/elmsazZito`. در زمان به‌روزرسانی هر دو روی `5c0ab1c` هستند.
- production در آخرین SSH check روی `660ab15` بود. اختلاف با GitHub فعلاً runtime-critical نیست، اما برای نظم تیمی بهتر است در deploy بعدی سرور هم pull شود.
- backup برنامه‌ریزی‌شده PostgreSQL مستند/فعال نشده است.
- migration discipline باید جدی‌تر شود؛ `AUTO_CREATE_TABLES=true` برای production بلندمدت مناسب نیست.
- health check فقط دیتابیس را تست می‌کند؛ وضعیت Arvan AIaaS را جداگانه چک نمی‌کند.

### Frontend

- UI در فایل‌های HTML بزرگ نگهداری می‌شود؛ با رشد محصول بهتر است به component-based frontend منتقل شود یا حداقل CSS/JS جدا شود.
- تست responsive/visual خودکار وجود ندارد.
- accessibility هنوز کامل audit نشده است.

### مستندات

- `PROJECT_CONTEXT.md` در بخش Admin هنوز نوشته «HTTP Basic auth»، در حالی که وضعیت فعلی login page + cookie session است. باید در یک اصلاح مستنداتی آپدیت شود.
- Runbook کامل incident/deploy/rollback هنوز جداگانه نوشته نشده است.
