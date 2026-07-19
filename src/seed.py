from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config import get_settings
from src.models import Admin, KnowledgeDocument, Question
from src.security import hash_password


DEFAULT_QUESTIONS = [
    {
        "key": "identity",
        "text": "سلام، من زیتو هستم. اول نام و نام خانوادگی واقعی خودت را بنویس.",
        "sort_order": 1,
    },
    {
        "key": "profession",
        "text": "حالا بگو می خواهی در کدام مسیر با کمک هوش مصنوعی یاد بگیری: حسابداری، روانشناسی یا حقوق؟",
        "sort_order": 2,
    },
]

DEFAULT_KNOWLEDGE = [
    {
        "title": "حسابداری و هوش مصنوعی: شروع امن",
        "content": (
            "در حسابداری، هوش مصنوعی باید به عنوان دستیار تحلیل و کنترل استفاده شود، نه جایگزین قضاوت حسابدار. "
            "کاربردهای مناسب شامل دسته بندی تراکنش ها، خلاصه سازی اسناد مالی، پیدا کردن ناهنجاری ها، آماده سازی پیش نویس گزارش و توضیح مفاهیم مالی است. "
            "کاربر باید همیشه خروجی AI را با سند، استاندارد و کنترل داخلی تطبیق دهد. داده های مالی محرمانه نباید بدون مجوز وارد ابزارهای عمومی شوند."
        ),
        "tags": "accounting,ai,حسابداری,هوش مصنوعی,finance",
    },
    {
        "title": "حسابداری و هوش مصنوعی: تمرین مرحله ای",
        "content": (
            "برای یادگیری AI در حسابداری، مسیر مرحله ای این است: شناخت داده مالی، نوشتن prompt دقیق، بررسی خروجی، کنترل خطا و مستندسازی تصمیم. "
            "یک تمرین مناسب این است که کاربر سه تراکنش نمونه را به AI بدهد و از آن بخواهد دسته پیشنهادی، دلیل دسته بندی و ریسک احتمالی را توضیح دهد. "
            "پاسخ خوب باید به کنترل انسانی، محرمانگی و تطبیق با سند اشاره کند."
        ),
        "tags": "accounting,ai,حسابداری,prompt,training",
    },
    {
        "title": "روانشناسی و هوش مصنوعی: مرزهای حرفه ای",
        "content": (
            "در روانشناسی، هوش مصنوعی می تواند برای آموزش مفاهیم، تمرین خودآگاهی، طراحی پرسش های باز، خلاصه سازی یادداشت های غیرحساس و پیشنهاد مسیر مطالعه کمک کند. "
            "AI نباید نقش درمانگر قطعی، تشخیص پزشکی یا جایگزین متخصص را بگیرد. در موضوعات بحران، آسیب به خود یا دیگران، باید ارجاع به متخصص و منابع فوری انجام شود. "
            "لحن پاسخ باید همدلانه، محتاط و بدون برچسب زنی باشد."
        ),
        "tags": "psychology,ai,روانشناسی,ethics,mental health",
    },
    {
        "title": "روانشناسی و هوش مصنوعی: تمرین یادگیری",
        "content": (
            "مسیر آموزشی مناسب برای روانشناسی و AI شامل شناخت محدودیت ها، پرسیدن سوال های غیرتشخیصی، تحلیل سناریوهای آموزشی و بازنویسی پاسخ با لحن همدلانه است. "
            "تمرین خوب این است که کاربر یک موقعیت فرضی بنویسد و از AI بخواهد سه سوال باز، یک بازتاب همدلانه و یک هشدار محدودیت حرفه ای تولید کند. "
            "پاسخ قابل قبول باید به عدم تشخیص قطعی و اهمیت متخصص انسانی اشاره کند."
        ),
        "tags": "psychology,ai,روانشناسی,training,empathy",
    },
    {
        "title": "حقوق و هوش مصنوعی: استفاده مسئولانه",
        "content": (
            "در حقوق، هوش مصنوعی می تواند برای خلاصه سازی متن، استخراج نکات، ساخت چک لیست، مقایسه بندهای قراردادی و آماده سازی پیش نویس اولیه کمک کند. "
            "AI نباید به عنوان وکیل قطعی یا منبع نهایی قانون استفاده شود. قوانین ممکن است تغییر کنند و تفسیر حقوقی به حوزه قضایی، متن قرارداد و نظر متخصص بستگی دارد. "
            "هر خروجی باید با قانون معتبر، رویه و مشاوره حقوقی انسانی بررسی شود."
        ),
        "tags": "law,ai,حقوق,legal,contract",
    },
    {
        "title": "حقوق و هوش مصنوعی: تمرین قرارداد",
        "content": (
            "برای یادگیری AI در حقوق، کاربر باید یاد بگیرد درخواست را دقیق، محدود و قابل راستی آزمایی بنویسد. "
            "تمرین مناسب این است که یک بند قراردادی فرضی بررسی شود و AI فقط ریسک های احتمالی، سوال های پیگیری و پیشنهادهای بازنویسی غیرقطعی بدهد. "
            "پاسخ خوب باید هشدار دهد که این خروجی مشاوره حقوقی نهایی نیست و نیاز به بررسی متخصص دارد."
        ),
        "tags": "law,ai,حقوق,contract,prompt,training",
    },
]


def seed_questions(db: Session) -> None:
    existing = {item.key: item for item in db.scalars(select(Question)).all()}
    for item in DEFAULT_QUESTIONS:
        current = existing.get(item["key"])
        if current:
            current.text = item["text"]
            current.sort_order = item["sort_order"]
            current.is_active = True
        else:
            db.add(Question(**item))
    db.commit()


def seed_knowledge(db: Session) -> None:
    existing_titles = {item.title: item for item in db.scalars(select(KnowledgeDocument)).all()}
    for item in DEFAULT_KNOWLEDGE:
        current = existing_titles.get(item["title"])
        if current:
            current.content = item["content"]
            current.tags = item["tags"]
        else:
            db.add(KnowledgeDocument(**item))
    db.commit()


def seed_admin(db: Session) -> None:
    existing_admin = db.scalars(select(Admin).limit(1)).first()
    if existing_admin:
        return
    settings = get_settings()
    if settings.is_production and not settings.has_safe_admin_seed_password:
        raise RuntimeError("Cannot seed the first production admin with an unsafe ADMIN_PASSWORD.")
    db.add(Admin(username=settings.admin_username, password_hash=hash_password(settings.admin_password)))
    db.commit()


def seed_defaults(db: Session) -> None:
    seed_questions(db)
    seed_knowledge(db)
    seed_admin(db)
