"""Akkaunt (Gmail) qo'shmagan foydalanuvchilarga tayyor eslatma matnlari (HTML, 3 tilda)."""

NUDGE = {
    "uz": (
        "👋 <b>Salom!</b> Siz HeroScanner botini ishga tushirdingiz, lekin hali birorta Gmail (Hero) akkaunt qo'shmagansiz.\n\n"
        "📲 <b>Qanday qo'shiladi:</b>\n"
        "1️⃣ Pastdagi <b>«📱 Panelga Kirish»</b> tugmasini bosing (yoki /start yuboring).\n"
        "2️⃣ <b>«Yangi profil qo'shish»</b> bo'limiga <b>@newuu.uz</b> pochtangiz va Hero parolingizni kiriting.\n"
        "3️⃣ Tayyor! Endi dars QR-kodini skanerlab, davomatni bir bosishda belgilashingiz mumkin ✅\n\n"
        "🔒 Parolingiz shifrlangan holda saqlanadi.\n"
        "Savol bo'lsa — shu yerga yozing, yordam beramiz."),
    "en": (
        "👋 <b>Hi!</b> You started the HeroScanner bot, but you haven't added any Gmail (Hero) account yet.\n\n"
        "📲 <b>How to add one:</b>\n"
        "1️⃣ Tap the <b>«📱 Open panel»</b> button below (or send /start).\n"
        "2️⃣ In <b>«Add new profile»</b> enter your <b>@newuu.uz</b> email and your Hero password.\n"
        "3️⃣ Done! Now you can scan the lesson QR code and mark attendance in one tap ✅\n\n"
        "🔒 Your password is stored encrypted.\n"
        "Questions? Just write here and we'll help."),
    "ru": (
        "👋 <b>Привет!</b> Вы запустили бота HeroScanner, но ещё не добавили ни одного аккаунта Gmail (Hero).\n\n"
        "📲 <b>Как добавить:</b>\n"
        "1️⃣ Нажмите кнопку <b>«📱 Открыть панель»</b> ниже (или отправьте /start).\n"
        "2️⃣ В разделе <b>«Добавить профиль»</b> введите почту <b>@newuu.uz</b> и пароль Hero.\n"
        "3️⃣ Готово! Теперь можно сканировать QR-код урока и отмечать посещаемость в одно нажатие ✅\n\n"
        "🔒 Пароль хранится в зашифрованном виде.\n"
        "Есть вопросы? Напишите сюда — поможем."),
}
BUTTON = {"uz": "📱 Panelga Kirish", "en": "📱 Open panel", "ru": "📱 Открыть панель"}
COOLDOWN_DAYS = 3   # bir odamga eslatma shu muddatda bir martadan ko'p ketmaydi


def text_for(lang):
    return NUDGE.get(lang) or NUDGE["uz"]


def button_for(lang):
    return BUTTON.get(lang) or BUTTON["uz"]


def bucket(now, days=COOLDOWN_DAYS):
    """Cooldown oynasi raqami: bir oynada bir kalit bir marta ishlaydi."""
    return int(now // (days * 86400))
