"""Asosiy testlar (DB va tarmoqsiz).
Ishga tushirish:
  ALLOW_EPHEMERAL_KEY=1 BOT_TOKEN=123:abc DATABASE_URL=postgres://x ADMIN_ID=1 python3 -m pytest -q
"""
import asyncio
import os
import sys
import time
from datetime import datetime

os.environ.setdefault("ALLOW_EPHEMERAL_KEY", "1")
os.environ.setdefault("BOT_TOKEN", "123:abc")
os.environ.setdefault("DATABASE_URL", "postgres://x")
os.environ.setdefault("ADMIN_ID", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import database as db
import hero_schedule
import main


# ---------------------------------------------------------------- _lesson_from_url
def test_lesson_from_url_path_segment():
    assert main._lesson_from_url("https://api.hero.study/qr/code-active/physics-101") == "physics 101"


def test_lesson_from_url_only_generic_words():
    assert main._lesson_from_url("https://api.hero.study/qr/code-active") is None


def test_lesson_from_url_query_param():
    assert main._lesson_from_url("https://api.hero.study/scan?lesson=Fizika%20A") == "Fizika A"


# ---------------------------------------------------------------- companions_for_lesson
def _group(emails, title="Fizika"):
    g = {"date": "2026-10-14", "start": "09:00", "end": "10:20", "title": title, "emails": set(emails)}
    return {hero_schedule.lesson_key(g): g}


def test_companions_only_same_active_lesson():
    now = datetime(2026, 10, 14, 9, 30, tzinfo=hero_schedule.TZ)
    groups = _group({"a@x", "b@x", "c@x"})
    assert hero_schedule.companions_for_lesson(["b@x", "d@x"], groups, {"a@x"}, now=now) == ["b@x"]


def test_companions_nobody_when_lesson_unknown():
    now = datetime(2026, 10, 14, 9, 30, tzinfo=hero_schedule.TZ)
    groups = _group({"a@x", "b@x"})
    assert hero_schedule.companions_for_lesson(["b@x"], groups, set(), now=now) == []


def test_companions_not_active_time():
    now = datetime(2026, 10, 14, 15, 0, tzinfo=hero_schedule.TZ)
    assert hero_schedule.companions_for_lesson(["b@x"], _group({"a@x", "b@x"}), {"a@x"}, now=now) == []


# ---------------------------------------------------------------- _why_lines
def test_why_lines_all_not_in_lesson():
    items = [{"ok": False, "reason": "not_in_lesson"}, {"ok": False, "reason": "not_in_lesson"}]
    out = main._why_lines(items, "uz")
    assert len(out) == 1 and out[0] == main.i18n.t("uz", "why_all_not_in")


def test_why_lines_partial_not_in_lesson():
    items = [{"ok": True}, {"ok": False, "reason": "not_in_lesson"}]
    out = main._why_lines(items, "uz")
    assert out == [main.i18n.t("uz", "why_not_in", n=1)]


def test_why_lines_qr_invalid():
    out = main._why_lines([{"ok": False, "reason": "qr_invalid"}, {"ok": False, "reason": "qr_invalid"}], "uz")
    assert out == [main.i18n.t("uz", "why_qr_invalid")]
    assert "QR" in out[0]


def test_why_lines_mixed_reasons():
    items = [{"ok": False, "reason": "token"}, {"ok": False, "reason": "login"}, {"ok": False, "reason": "network"}]
    out = main._why_lines(items, "uz")
    assert out == [main.i18n.t("uz", "why_token", n=2), main.i18n.t("uz", "why_hero", n=1)]


# ---------------------------------------------------------------- akkaunt tarixi
def test_split_lesson_kind():
    assert db._split_lesson_kind("Fizika · avto") == ("Fizika", "avto")
    assert db._split_lesson_kind("Fizika · hamroh") == ("Fizika", "hamroh")
    assert db._split_lesson_kind("Fizika") == ("Fizika", "manual")
    assert db._split_lesson_kind(None) == (None, "manual")


def test_activity_rows():
    details = [
        {"email": " A@X.com ", "ok": True},
        {"email": "b@x.com", "ok": False, "reason": "qr_invalid", "msg": "QR kod topilmadi yoki eskirgan"},
        {"ok": True},            # email yo'q — o'tkazib yuboriladi
        "xato",                  # element dict emas
    ]
    rows = db._activity_rows(details, 7, 99, "Fizika", "avto")
    assert rows == [("a@x.com", 7, 99, "Fizika", "avto", True, None, None),
                    ("b@x.com", 7, 99, "Fizika", "avto", False, "qr_invalid", "QR kod topilmadi yoki eskirgan")]
    assert db._activity_rows(None, 1, 1, None, "manual") == []


# ---------------------------------------------------------------- JWT / parol almashtirish
class _Req:
    def __init__(self, token): self.headers = {"Authorization": f"Bearer {token}"}


def _tok(**extra):
    return jwt.encode({"user_id": 5, "role": "user", "exp": int(time.time()) + 3600, **extra}, main.JWT_SECRET, algorithm="HS256")


def test_verify_token_old_session_closed_after_reset():
    saved = main._PW_CHANGED
    try:
        main._PW_CHANGED = {5: int(time.time()) - 100}
        assert main.verify_token(_Req(_tok(iat=int(time.time()) - 500)))[0] is None   # parol almashgunga qadar berilgan
        assert main.verify_token(_Req(_tok()))[0] is None                              # iat yo'q
        assert main.verify_token(_Req(_tok(iat=int(time.time()) - 50)))[0] == 5        # keyin berilgan — yaroqli
        main._PW_CHANGED = {}
        assert main.verify_token(_Req(_tok()))[0] == 5                                 # lug'atda yo'q — iat shart emas
    finally:
        main._PW_CHANGED = saved


def test_reset_rate_limit():
    main._reset_hits.clear()
    assert main._reset_limit_msg(42, record=True) is None
    assert main._reset_limit_msg(42) is not None          # 60 soniya ichida ikkinchisi
    main._reset_hits[42] = [time.time() - 120 - i for i in range(main.RESET_HOUR_MAX)]
    assert main._reset_limit_msg(42) is not None          # soatiga 5 ta tugagan
    main._reset_hits.clear()


def test_mask_email():
    assert main._mask_email("student@gmail.com") == "s***@gmail.com"
    assert "student" not in main._mask_email("student@gmail.com")


# ---------------------------------------------------------------- webhook
def _webhook_status(headers):
    async def run():
        app = web.Application()
        app.router.add_post("/webhook/x", main.handle_webhook)
        async with TestClient(TestServer(app)) as c:
            r = await c.post("/webhook/x", json={"update_id": 1}, headers=headers)
            return r.status
    return asyncio.run(run())


def test_webhook_no_header_403():
    assert _webhook_status({}) == 403


def test_webhook_wrong_header_403():
    assert _webhook_status({"X-Telegram-Bot-Api-Secret-Token": "noto'g'ri"}) == 403


def test_webhook_correct_header_200():
    assert _webhook_status({"X-Telegram-Bot-Api-Secret-Token": main.WEBHOOK_HEADER_SECRET}) == 200


# ---------------------------------------------------------------- decode_qr_full
import base64
import json
import qr_decode

_QR_PAYLOAD = {"data": {"subject": "Fizika ???>>> fan", "stream_id": 2737, "event_type": "lecture",
                        "begin_time": 1760000000, "end_time": 1760005400}}


def _b64(obj, urlsafe=False, pad=True):
    raw = json.dumps(obj, ensure_ascii=False).encode()
    t = (base64.urlsafe_b64encode(raw) if urlsafe else base64.b64encode(raw)).decode()
    return t if pad else t.rstrip("=")


def _check_meta(m):
    assert m["subject"] == "Fizika ???>>> fan"
    assert str(m["stream_id"]) == "2737"
    assert m["event_type"] == "lecture"
    assert m["begin_sec"] == 1760000000 and m["end_sec"] == 1760005400


def test_decode_qr_full_base64_with_plus_unencoded():
    b = _b64(_QR_PAYLOAD)
    assert "+" in b or "/" in b   # parse_qs aynan shu belgida buzardi
    d = qr_decode.decode_qr_full(f"https://api.hero.study/qr/scan?lang=en&url={b}")
    assert d["host"] == "api.hero.study" and d["path"] == "/qr/scan"
    assert d["params"]["lang"] == "en" and d["params"]["url"] == b   # '+' o'zgarmagan
    _check_meta(d["meta"])
    assert d["decoded"][0]["param"] == "url" and d["decoded"][0]["encoding"] == "base64"


def test_decode_qr_full_percent_encoded_base64():
    from urllib.parse import quote
    d = qr_decode.decode_qr_full("https://api.hero.study/qr?url=" + quote(_b64(_QR_PAYLOAD), safe=""))
    _check_meta(d["meta"])


def test_decode_qr_full_urlsafe_and_no_padding():
    for pad in (True, False):
        d = qr_decode.decode_qr_full("https://api.hero.study/qr?url=" + _b64(_QR_PAYLOAD, urlsafe=True, pad=pad))
        _check_meta(d["meta"])
    d = qr_decode.decode_qr_full("https://api.hero.study/qr?url=" + _b64(_QR_PAYLOAD, pad=False))   # oddiy +/ , padding yo'q
    _check_meta(d["meta"])


def test_decode_qr_full_flat_payload_and_camel_keys():
    flat = {"subject": "Algebra", "streamId": "55", "eventType": "lab", "beginTime": 1760000000000, "endTime": 1760005400000}
    d = qr_decode.decode_qr_full("https://api.hero.study/qr?url=" + _b64(flat))
    m = d["meta"]
    assert (m["subject"], str(m["stream_id"]), m["event_type"]) == ("Algebra", "55", "lab")
    assert m["begin_sec"] == 1760000000 and m["end_sec"] == 1760005400   # millisoniya -> soniya


def test_decode_qr_full_nested_data_is_base64_string():
    outer = {"code": "abc", "data": _b64({"subject": "Kimyo", "stream_id": 7})}
    d = qr_decode.decode_qr_full("https://api.hero.study/qr?url=" + _b64(outer))
    assert d["meta"]["subject"] == "Kimyo" and str(d["meta"]["stream_id"]) == "7"
    assert d["fields"].get("code") == "abc"


def test_decode_qr_full_plain_params_and_garbage():
    d = qr_decode.decode_qr_full("https://x.hero.study/a/b?lang=en&token=Fizika&lang=uz")
    assert d["params"]["token"] == "Fizika" and d["params"]["lang"] == ["en", "uz"]
    assert d["decoded"] == [] and d["meta"]["subject"] is None
    for bad in ("", None, "salom", "https://x.hero.study/?url=%%%", "https://x.hero.study/?url=@@@@####"):
        r = qr_decode.decode_qr_full(bad)
        assert r["decoded"] == [] and r["meta"]["stream_id"] is None


def test_decode_qr_meta_keeps_plus():
    b = _b64(_QR_PAYLOAD)
    m = main.decode_qr_meta(f"https://api.hero.study/qr?url={b}")
    assert m["subject"] == "Fizika ???>>> fan" and str(m["stream_id"]) == "2737" and m["event_type"] == "lecture"
    assert main.decode_qr_meta("https://api.hero.study/qr") == {}


def test_qr_parts_does_not_turn_plus_into_space():
    b = _b64(_QR_PAYLOAD)
    host, path, params = db._qr_parts(f"https://api.hero.study/qr?url={b}")
    assert host == "api.hero.study" and params["url"] == [b]


# ---------------------------------------------------------------- normalize_item: subject / stream / event_type
def test_normalize_item_snake_case():
    r = hero_schedule.normalize_item({"subject": "Fizika", "stream_id": 2737, "stream": "A-1", "event_type": "lecture",
                                      "begin_time": 1760000000, "end_time": 1760005400})
    assert (r["subject"], r["stream_id"], r["stream"], r["event_type"]) == ("Fizika", "2737", "A-1", "lecture")


def test_normalize_item_camel_and_steam_typo():
    r = hero_schedule.normalize_item({"subjectName": "Kimyo", "steamId": 91, "steam": "B-2", "eventType": "lab", "date": "2026-10-22", "time": "09:00-10:20"})
    assert (r["subject"], r["stream_id"], r["stream"], r["event_type"]) == ("Kimyo", "91", "B-2", "lab")
    assert r["date"] == "2026-10-22" and r["start"] == "09:00"


def test_normalize_item_stream_object_and_nested():
    r = hero_schedule.normalize_item({"title": "X", "stream": {"id": 12, "name": "Oqim 12"}, "event": {"eventType": "practice"},
                                      "subject": {"id": 3, "name": "Biologiya"}})
    assert r["stream_id"] == "12" and r["stream"] == "Oqim 12" and r["event_type"] == "practice" and r["subject"] == "Biologiya"
    r = hero_schedule.normalize_item({"lesson": {"steam": {"steamId": "S-5", "name": "Guruh"}, "subject_name": "Tarix"}})
    assert r["stream_id"] == "S-5" and r["stream"] == "Guruh" and r["subject"] == "Tarix"


def test_normalize_item_missing_fields_are_none():
    r = hero_schedule.normalize_item({"title": "Dars"})
    assert r["stream_id"] is None and r["stream"] is None and r["event_type"] is None and r["subject"] is None


def test_catalog_key_and_rows():
    a = hero_schedule.normalize_item({"subject": "Fizika", "stream_id": 1, "event_type": "lecture", "date": "2026-10-22", "time": "09:00-10:20", "teacher": "T"})
    b = hero_schedule.normalize_item({"subject": "Fizika", "stream_id": 2, "date": "2026-10-22", "time": "09:00-10:20"})
    rows = hero_schedule.catalog_rows([a, a, b, {"title": "sanasiz"}])
    assert len(rows) == 2   # stream_id farqi alohida dars; takror va sanasiz tashlab ketiladi
    assert rows[0][0] == "2026-10-22|09:00|fizika|1"
    assert rows[0][1]["teacher"] == "T" and rows[0][1]["event_type"] == "lecture" and rows[0][1]["end"] == "10:20"


# ---------------------------------------------------------------- yangi: xavfsizlik / health / ratelimit
def _client_run(coro_fn, middlewares=()):
    async def run():
        app = web.Application(middlewares=list(middlewares))
        app.router.add_get("/health", main.health)
        app.router.add_post("/api/auth/login", main.auth_login)
        async with TestClient(TestServer(app)) as c:
            return await coro_fn(c)
    return asyncio.run(run())


def test_security_headers_present():
    async def go(c):
        r = await c.post("/api/auth/login", json={"login": "x", "password": "y" * 100})
        return r.status, dict(r.headers)
    st, h = _client_run(go, [main._security_headers_mw])
    assert st == 401   # 72 baytdan uzun parol bcrypt'ga yetib bormaydi
    assert h["X-Content-Type-Options"] == "nosniff" and h["Cache-Control"] == "no-store"


def test_login_rejects_non_string_fields():
    async def go(c):
        r1 = await c.post("/api/auth/login", json={"login": ["a"], "password": {"b": 1}})
        r2 = await c.post("/api/auth/login", json=[1, 2, 3])
        return r1.status, r2.status
    s1, s2 = _client_run(go)
    assert s1 == 401 and s2 == 400


def test_health_starting_when_no_pool():
    async def go(c):
        return (await c.get("/health")).status
    old = db.pool; db.pool = None
    try: assert _client_run(go) == 503
    finally: db.pool = old


def test_login_key_uses_last_forwarded_ip():
    class R:
        headers = {"X-Forwarded-For": "6.6.6.6, 1.2.3.4"}; remote = "10.0.0.1"
    assert main._login_key(R, "Ali") == "1.2.3.4|ali"


def test_prune_fails_bounds_memory():
    d = {f"k{i}": [time.time()] for i in range(6000)}
    main._prune_fails(d, 600)
    assert len(d) <= 4000


# ---------------------------------------------------------------- yangi: seriya va /api/me
from datetime import date, timedelta as _td


def test_streak_counts_consecutive_days():
    t = date(2026, 11, 10)
    assert db.compute_streak([t, t - _td(days=1), t - _td(days=2), t - _td(days=4)], t) == 3
    assert db.compute_streak([t - _td(days=1), t - _td(days=2)], t) == 2   # bugun hali skaner yo'q — seriya uzilmagan
    assert db.compute_streak([t - _td(days=2)], t) == 0
    assert db.compute_streak([], t) == 0


def test_api_me_requires_auth():
    async def run():
        app = web.Application(); app.router.add_get("/api/me", main.get_me)
        async with TestClient(TestServer(app)) as c:
            return (await c.get("/api/me")).status
    assert asyncio.run(run()) == 401


# ---------------------------------------------------------------- yangi: eslatma (akkaunt qo'shmaganlarga) va /broadcast menyusi
import re as _re
import nudge
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock


def test_nudge_texts_complete_and_valid_html():
    for lang in ("uz", "en", "ru"):
        t = nudge.text_for(lang)
        assert "@newuu.uz" in t and len(t) < main.MAX_MSG_LEN
        assert t.count("<b>") == t.count("</b>")
        assert nudge.button_for(lang)
    assert nudge.text_for("xx") == nudge.text_for("uz") and nudge.button_for("xx") == nudge.button_for("uz")


def test_nudge_bucket_window():
    d = 86400
    assert nudge.bucket(0) == nudge.bucket(2 * d) != nudge.bucket(3 * d + 1)


def _msg(uid, text, private=True):
    return SimpleNamespace(from_user=SimpleNamespace(id=uid), text=text, chat=SimpleNamespace(type="private" if private else "group"))


def test_compose_filter_only_for_waiting_admin():
    main._compose_wait.clear()
    old_admin, old_ids = main.ADMIN_ID, set(main.ADMIN_TG_IDS)
    main.ADMIN_ID = 111
    try:
        assert not main._compose_filter(_msg(111, "salom"))                 # kutilmayapti
        main._compose_wait[111] = ("all", time.time() + 60)
        assert main._compose_filter(_msg(111, "salom"))
        assert not main._compose_filter(_msg(111, "/broadcast"))            # buyruq — matn emas
        assert not main._compose_filter(_msg(222, "salom"))                 # admin emas
        main._compose_wait[111] = ("all", time.time() - 1)
        assert not main._compose_filter(_msg(111, "salom"))                 # muddati o'tgan
    finally:
        main.ADMIN_ID = old_admin; main.ADMIN_TG_IDS.clear(); main.ADMIN_TG_IDS.update(old_ids); main._compose_wait.clear()


def test_run_nudge_language_cooldown_and_failures():
    sent = []
    async def fake_send(chat_id, body, markup=None):
        sent.append((chat_id, body, markup is not None))
        return chat_id != 3                                               # 3-foydalanuvchi botni bloklagan
    seen = set()
    async def fake_once(key):
        if key in seen: return False
        seen.add(key); return True
    async def fake_lang(tg): return {1: "uz", 2: "ru", 3: "en", 4: "uz"}[tg]
    users = [{"telegram_id": i} for i in (1, 2, 3, 4)]
    seen.add(f"nudge:4:{nudge.bucket(time.time())}")                       # 4-foydalanuvchi yaqinda eslatma olgan
    patches = [(main, "_send_html", fake_send), (main.notify, "once", fake_once), (main.notify, "lang_of", fake_lang), (main, "WEBAPP_URL", "https://x.test")]
    olds = [(o, n, getattr(o, n)) for o, n, _ in patches]
    for o, n, v in patches: setattr(o, n, v)
    try:
        asyncio.run(main._run_nudge(999, users, None))
    finally:
        for o, n, v in olds: setattr(o, n, v)
    by = {c: (b, m) for c, b, m in sent}
    assert by[1][0] == nudge.text_for("uz") and by[2][0] == nudge.text_for("ru") and by[1][1] and 4 not in by
    report = by[999][0]
    assert "Yuborildi: 2" in report and "o'tkazildi: 1" in report and "Yetib bormadi: 1" in report


def test_run_nudge_custom_text_is_escaped():
    sent = []
    async def fake_send(chat_id, body, markup=None): sent.append(body); return True
    async def ok(key): return True
    async def lang(tg): return "uz"
    patches = [(main, "_send_html", fake_send), (main.notify, "once", ok), (main.notify, "lang_of", lang), (main, "WEBAPP_URL", "")]
    olds = [(o, n, getattr(o, n)) for o, n, _ in patches]
    for o, n, v in patches: setattr(o, n, v)
    try: asyncio.run(main._run_nudge(1, [{"telegram_id": 5}], "<b>salom</b> & rahmat"))
    finally:
        for o, n, v in olds: setattr(o, n, v)
    assert sent[0] == "&lt;b&gt;salom&lt;/b&gt; &amp; rahmat"
