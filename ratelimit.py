"""Kirish urinishlarini cheklash uchun kichik yordamchilar (main.py'dan ajratilgan, xatti-harakat o'zgarmagan)."""
import time


def _login_key(request, login):
    xff = [x.strip() for x in (request.headers.get("X-Forwarded-For") or "").split(",") if x.strip()]
    ip = xff[-1] if xff else (request.remote or "")   # oxirgi yozuvni (bizning proksi qo'shgan) olamiz — mijoz o'zi yozgan boshlang'ich qiymatlarga ishonmaymiz
    return f"{ip}|{str(login or '')[:60].lower()}"

def _prune_fails(d, window):
    """Muddati o'tgan yozuvlarni tozalaydi; juda ko'payib ketsa eng eskilarini tashlaydi (hammasini emas)."""
    if len(d) <= 5000: return
    now = time.time()
    for k in [k for k, v in d.items() if not v or now - v[-1] > window]: d.pop(k, None)
    for k in list(d)[: max(0, len(d) - 4000)]: d.pop(k, None)
