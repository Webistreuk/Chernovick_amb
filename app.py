import math
import os
import secrets
from functools import wraps
from datetime import datetime, timedelta

from flask import (
    Flask, render_template, jsonify, request,
    redirect, url_for, flash, session, abort, g
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
)

PER_PAGE = 5
SEARCH_FIELDS = ("name", "address", "phone")
BASE_LAT = 43.585
BASE_LNG = 39.723

USERS = {
    "doctor": {"password_hash": generate_password_hash("doctor123"), "role": "doctor", "name": "Фельдшер Иванов"},
    "doctor2": {"password_hash": generate_password_hash("doctor123"), "role": "doctor", "name": "Фельдшер Петров"},
    "admin": {"password_hash": generate_password_hash("admin123"), "role": "admin", "name": "Админ Сидоров"},
    "superadmin": {"password_hash": generate_password_hash("super123"), "role": "superadmin", "name": "Главный Админ"},
}

ACTIVE_CALLS = {}
COMPLETED = {}
CALL_STATUS = {}
PATIENT_INFO = []
PROBLEMS = []
CASES = []
DIARY = []
_info_seq = 0
_problem_seq = 0
_case_seq = 0
_diary_seq = 0

DOCTOR_LOCATIONS = {
    "doctor": {"lat": 43.590, "lng": 39.720},
    "doctor2": {"lat": 43.575, "lng": 39.740},
}

PRIORITY_LABELS = {
    "emergency": "Экстренный",
    "urgent": "Неотложный",
    "planned": "Плановый",
}

STATUS_LABELS = {
    "accepted": "Принят",
    "en_route": "В пути",
    "arrived": "Прибыл",
}


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


@app.context_processor
def inject_globals():
    return {
        "csrf_token": csrf_token,
        "current_user": g.get("user"),
        "doctor_portal_url": os.environ.get("DOCTOR_PORTAL_URL", ""),
        "priority_labels": PRIORITY_LABELS,
        "status_labels": STATUS_LABELS,
    }


def verify_csrf():
    token = request.form.get("_csrf") or (request.get_json(silent=True) or {}).get("_csrf")
    if not token or token != session.get("_csrf"):
        abort(400, "Invalid CSRF token")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not g.get("user"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not g.get("user"):
                return redirect(url_for("login", next=request.path))
            if g.user["role"] not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator


@app.before_request
def load_user():
    login = session.get("user_login")
    if login and login in USERS:
        u = USERS[login]
        g.user = {"login": login, "role": u["role"], "name": u["name"]}
    else:
        g.user = None


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


PATIENTS = {
    1:  {"id": 1,  "name": "Иванов Иван Иванович",        "birth_date": "01.01.1966", "sex": "Мужской", "oms": "1234 5678 9012 3456", "allergies": "Пенициллин",     "phone": "+7 900 111-22-33"},
    2:  {"id": 2,  "name": "Петрова Анна Сергеевна",       "birth_date": "12.05.1990", "sex": "Женский", "oms": "9876 5432 1098 7654", "allergies": "Нет",            "phone": "+7 900 222-33-44"},
    3:  {"id": 3,  "name": "Сидоров Пётр Алексеевич",      "birth_date": "23.09.1958", "sex": "Мужской", "oms": "1111 2222 3333 4444", "allergies": "Лидокаин",       "phone": "+7 900 333-44-55"},
    4:  {"id": 4,  "name": "Кузнецова Мария Ивановна",     "birth_date": "07.03.1975", "sex": "Женский", "oms": "5555 6666 7777 8888", "allergies": "Нет",            "phone": "+7 900 444-55-66"},
    5:  {"id": 5,  "name": "Смирнов Алексей Николаевич",   "birth_date": "18.11.1982", "sex": "Мужской", "oms": "9999 0000 1111 2222", "allergies": "Аспирин",        "phone": "+7 900 555-66-77"},
    6:  {"id": 6,  "name": "Волкова Екатерина Сергеевна",  "birth_date": "30.06.1995", "sex": "Женский", "oms": "3333 4444 5555 6666", "allergies": "Нет",            "phone": "+7 900 666-77-88"},
    7:  {"id": 7,  "name": "Морозов Дмитрий Владимирович", "birth_date": "14.02.1970", "sex": "Мужской", "oms": "7777 8888 9999 0000", "allergies": "Сульфаниламиды", "phone": "+7 900 777-88-99"},
    8:  {"id": 8,  "name": "Новикова Ольга Павловна",      "birth_date": "09.08.1988", "sex": "Женский", "oms": "1212 3434 5656 7878", "allergies": "Нет",            "phone": "+7 900 888-99-00"},
    9:  {"id": 9,  "name": "Фёдоров Сергей Михайлович",    "birth_date": "25.12.1962", "sex": "Мужской", "oms": "2323 4545 6767 8989", "allergies": "Новокаин",       "phone": "+7 900 999-00-11"},
    10: {"id": 10, "name": "Егорова Наталья Андреевна",    "birth_date": "03.04.1979", "sex": "Женский", "oms": "3434 5656 7878 9090", "allergies": "Нет",            "phone": "+7 901 111-22-44"},
    11: {"id": 11, "name": "Павлов Андрей Олегович",       "birth_date": "21.07.1985", "sex": "Мужской", "oms": "4545 6767 8989 0101", "allergies": "Пенициллин",     "phone": "+7 901 222-33-55"},
    12: {"id": 12, "name": "Соколова Ирина Викторовна",    "birth_date": "16.10.1992", "sex": "Женский", "oms": "5656 7878 9090 1212", "allergies": "Нет",            "phone": "+7 901 333-44-66"},
    13: {"id": 13, "name": "Лебедев Максим Игоревич",      "birth_date": "05.01.1973", "sex": "Мужской", "oms": "6767 8989 0101 2323", "allergies": "Йод",            "phone": "+7 901 444-55-77"},
    14: {"id": 14, "name": "Козлова Татьяна Юрьевна",      "birth_date": "28.05.1968", "sex": "Женский", "oms": "7878 9090 1212 3434", "allergies": "Нет",            "phone": "+7 901 555-66-88"},
    15: {"id": 15, "name": "Степанов Виктор Петрович",     "birth_date": "11.09.1955", "sex": "Мужской", "oms": "8989 0101 2323 4545", "allergies": "Аспирин",        "phone": "+7 901 666-77-99"},
    16: {"id": 16, "name": "Николаева Светлана Борисовна", "birth_date": "19.03.1980", "sex": "Женский", "oms": "9090 1212 3434 5656", "allergies": "Нет",            "phone": "+7 901 777-88-00"},
    17: {"id": 17, "name": "Орлов Роман Денисович",        "birth_date": "02.11.1998", "sex": "Мужской", "oms": "0101 2323 4545 6767", "allergies": "Лидокаин",       "phone": "+7 901 888-99-11"},
    18: {"id": 18, "name": "Андреева Юлия Сергеевна",      "birth_date": "24.08.1987", "sex": "Женский", "oms": "1212 4545 6767 8989", "allergies": "Нет",            "phone": "+7 901 999-00-22"},
    19: {"id": 19, "name": "Макаров Илья Валерьевич",      "birth_date": "13.06.1976", "sex": "Мужской", "oms": "2323 5656 7878 9090", "allergies": "Пенициллин",     "phone": "+7 902 111-22-55"},
    20: {"id": 20, "name": "Захарова Алина Максимовна",    "birth_date": "08.12.1993", "sex": "Женский", "oms": "3434 6767 8989 0101", "allergies": "Нет",            "phone": "+7 902 222-33-66"},
}

CALLS = [
    {"id": 1,  "number": "1245", "address": "ул. Ленина 5",        "priority": "emergency", "reason": "Боли в груди",         "patient_id": 1,  "created_at": "2026-11-20T08:15:00", "lat": 43.596226, "lng": 39.730886},
    {"id": 2,  "number": "1246", "address": "пр. Мира 12",          "priority": "urgent",    "reason": "Высокая температура",  "patient_id": 2,  "created_at": "2026-11-20T09:40:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 3,  "number": "1247", "address": "ул. Гагарина 3",       "priority": "planned",   "reason": "Плановый осмотр",      "patient_id": 3,  "created_at": "2026-11-20T11:05:00", "lat": 43.6037919, "lng": 39.7243046},
    {"id": 4,  "number": "1248", "address": "ул. Пушкина 17",       "priority": "emergency", "reason": "ДТП, пострадавший",    "patient_id": 4,  "created_at": "2026-11-20T13:22:00", "lat": 43.568333, "lng": 39.738889},
    {"id": 5,  "number": "1249", "address": "пр. Победы 44",        "priority": "urgent",    "reason": "Гипертонический криз", "patient_id": 5,  "created_at": "2026-11-20T15:50:00", "lat": 43.911960, "lng": 39.328028},
    {"id": 6,  "number": "1250", "address": "ул. Садовая 8",        "priority": "planned",   "reason": "Консультация",         "patient_id": 6,  "created_at": "2026-11-20T18:10:00", "lat": 43.4301045, "lng": 39.9262999},
    {"id": 7,  "number": "1251", "address": "ул. Кирова 21",        "priority": "emergency", "reason": "Остановка сердца",     "patient_id": 7,  "created_at": "2026-11-21T07:30:00", "lat": 43.4268257, "lng": 39.9253134},
    {"id": 8,  "number": "1252", "address": "пр. Космонавтов 9",    "priority": "urgent",    "reason": "Боли в животе",        "patient_id": 8,  "created_at": "2026-11-21T10:12:00", "lat": 43.585278, "lng": 39.720278},
    {"id": 9,  "number": "1253", "address": "ул. Чехова 14",        "priority": "planned",   "reason": "Перевозка",            "patient_id": 9,  "created_at": "2026-11-21T12:45:00", "lat": 43.618655, "lng": 39.724751},
    {"id": 10, "number": "1254", "address": "ул. Горького 30",      "priority": "emergency", "reason": "Суицидальная попытка", "patient_id": 10, "created_at": "2026-11-21T16:20:00", "lat": 43.5913678, "lng": 39.727046},
    {"id": 11, "number": "1255", "address": "пр. Октябрьский 5",    "priority": "urgent",    "reason": "Травма конечности",    "patient_id": 11, "created_at": "2026-11-22T08:05:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 12, "number": "1256", "address": "ул. Лермонтова 2",     "priority": "planned",   "reason": "Плановый осмотр",      "patient_id": 12, "created_at": "2026-11-22T11:35:00", "lat": 43.574, "lng": 39.7377},
    {"id": 13, "number": "1257", "address": "ул. Некрасова 11",     "priority": "emergency", "reason": "Роды на дому",         "patient_id": 13, "created_at": "2026-11-22T14:00:00", "lat": 43.5148139, "lng": 39.867396},
    {"id": 14, "number": "1258", "address": "пр. Строителей 18",    "priority": "urgent",    "reason": "Одышка",               "patient_id": 14, "created_at": "2026-11-22T17:25:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 15, "number": "1259", "address": "ул. Толстого 6",       "priority": "planned",   "reason": "Запись на приём",      "patient_id": 15, "created_at": "2026-11-23T09:10:00", "lat": 43.8972187, "lng": 39.3500412},
    {"id": 16, "number": "1260", "address": "ул. Достоевского 4",   "priority": "emergency", "reason": "Анафилаксия",          "patient_id": 16, "created_at": "2026-11-23T12:50:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 17, "number": "1261", "address": "пр. Ленинградский 22", "priority": "urgent",    "reason": "Высокое давление",     "patient_id": 17, "created_at": "2026-11-23T15:30:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 18, "number": "1262", "address": "ул. Маяковского 7",    "priority": "planned",   "reason": "Консультация",         "patient_id": 18, "created_at": "2026-11-23T18:15:00", "lat": 43.9030792, "lng": 39.3430953},
    {"id": 19, "number": "1263", "address": "ул. Тургенева 10",     "priority": "emergency", "reason": "Отравление",           "patient_id": 19, "created_at": "2026-11-24T08:40:00", "lat": 43.572999, "lng": 39.737201},
    {"id": 20, "number": "1264", "address": "пр. Советский 1",      "priority": "urgent",    "reason": "Боли в спине",         "patient_id": 20, "created_at": "2026-11-24T11:05:00", "lat": 43.582632, "lng": 39.719073},
]


def enrich_call(call):
    p = PATIENTS.get(call["patient_id"], {})
    lat, lng = call.get("lat"), call.get("lng")
    dist = round(haversine_km(BASE_LAT, BASE_LNG, lat, lng), 1) if lat and lng else None
    active_owner = next((login for login, cid in ACTIVE_CALLS.items() if cid == call["id"]), None)
    return {
        **call,
        "patient_name": p.get("name", "—"),
        "patient_phone": p.get("phone", "—"),
        "distance_km": dist,
        "is_completed": call["id"] in COMPLETED,
        "result": COMPLETED.get(call["id"]),
        "active_owner": active_owner,
        "is_active_for_me": active_owner == (g.user["login"] if g.get("user") else None),
        "status_progress": CALL_STATUS.get(call["id"]),
        "priority_label": PRIORITY_LABELS.get(call.get("priority"), call.get("priority", "")),
        "status_label": STATUS_LABELS.get(CALL_STATUS.get(call["id"]), "Принят"),
    }


def filter_calls(q, field):
    all_calls = [enrich_call(c) for c in CALLS]
    if not q:
        return all_calls
    q_low = q.lower()

    def match(c):
        if field == "name":
            return q_low in c["patient_name"].lower()
        if field == "address":
            return q_low in c["address"].lower()
        if field == "phone":
            norm_q = "".join(ch for ch in q if ch.isdigit())
            norm_p = "".join(ch for ch in c["patient_phone"] if ch.isdigit())
            if norm_p.startswith("7"):
                norm_p = norm_p[1:]
            return norm_p.startswith(norm_q)
        return False
    return [c for c in all_calls if match(c)]


def paginate(all_calls, page):
    total = len(all_calls)
    total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    start = (page - 1) * PER_PAGE
    return {"calls": all_calls[start:start + PER_PAGE], "page": page, "total_pages": total_pages, "total": total}


PRIORITY_ORDER = {"emergency": 0, "urgent": 1, "planned": 2}


def prepare_calls(q, field, view, page):
    all_calls = filter_calls(q, field)
    all_calls.sort(key=lambda c: c["created_at"], reverse=True)
    all_calls.sort(key=lambda c: (c["is_completed"], not c["is_active_for_me"]))
    all_calls.sort(key=lambda c: PRIORITY_ORDER.get(c.get("priority"), 99))
    if view == "nearest":
        all_calls.sort(key=lambda c: (c["distance_km"] is None, c["distance_km"] or 0))
        all_calls = all_calls[:1]
        return all_calls, 1, 1, all_calls
    pdata = paginate(all_calls, page)
    return pdata["calls"], pdata["page"], pdata["total_pages"], all_calls


def phone_mask_display(digits):
    template = "XXX XXX-XX-XX"
    out, di = "", 0
    for ch in template:
        if ch == "X":
            out += digits[di] if di < len(digits) else "X"
            di += 1
        else:
            out += ch
    return "+7 " + out


@app.route("/login", methods=["GET", "POST"])
def login():
    if g.get("user"):
        return redirect(url_for("calls_list"))
    error = None
    if request.method == "POST":
        verify_csrf()
        login_ = (request.form.get("login") or "").strip()
        password = request.form.get("password") or ""
        user = USERS.get(login_)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_login"] = login_
            session.permanent = True
            csrf_token()
            flash(f"Добро пожаловать, {user['name']}", "success")
            nxt = request.args.get("next") or url_for("calls_list")
            return redirect(nxt)
        error = "Неверный логин или пароль"
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    verify_csrf()
    session.clear()
    flash("Вы вышли из системы", "info")
    return redirect(url_for("login"))


@app.route("/admin")
@role_required("admin", "superadmin")
def admin_panel():
    doctors = [{"login": l, "name": u["name"], "role": u["role"], "active_call_id": ACTIVE_CALLS.get(l)} for l, u in USERS.items()]
    stats = {
        "completed": sum(1 for v in COMPLETED.values() if v == "normal"),
        "false": sum(1 for v in COMPLETED.values() if v == "false"),
        "in_progress": len([c for c in ACTIVE_CALLS.values() if c]),
        "total": len(CALLS),
    }
    history = [enrich_call(c) for c in CALLS if c["id"] in COMPLETED]
    return render_template("admin.html", doctors=doctors, stats=stats, history=history)


@app.route("/admin/reset/<login>", methods=["POST"])
@role_required("admin", "superadmin")
def admin_reset(login):
    verify_csrf()
    if login in ACTIVE_CALLS:
        cid = ACTIVE_CALLS.pop(login, None)
        if cid:
            CALL_STATUS.pop(cid, None)
        flash(f"Активный вызов у {login} сброшен", "success")
    else:
        flash(f"У {login} нет активного вызова", "info")
    return redirect(url_for("admin_panel"))


@app.route("/admin/create_user", methods=["POST"])
@role_required("admin", "superadmin")
def admin_create_user():
    verify_csrf()
    login_ = (request.form.get("login") or "").strip().lower()
    password = request.form.get("password") or ""
    role = request.form.get("role") or "doctor"
    name = (request.form.get("name") or "").strip()

    if not login_ or not password or not name:
        flash("Заполните все поля", "danger")
        return redirect(url_for("admin_panel"))
    if login_ in USERS:
        flash("Пользователь с таким логином уже существует", "danger")
        return redirect(url_for("admin_panel"))
    if g.user["role"] == "admin" and role == "superadmin":
        abort(403)
    if role not in ("doctor", "admin", "superadmin"):
        abort(400)

    USERS[login_] = {"password_hash": generate_password_hash(password), "role": role, "name": name}
    flash(f"Пользователь {login_} создан", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/map/call/<int:call_id>")
@role_required("admin", "superadmin")
def admin_map_call(call_id):
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash(f"Вызов #{call_id} не найден", "danger")
        return redirect(url_for("calls_list"))
    call = enrich_call(call)
    owner_login = call.get("active_owner")
    owner_loc = DOCTOR_LOCATIONS.get(owner_login) if owner_login else None
    owner_name = USERS[owner_login]["name"] if owner_login and owner_login in USERS else None
    return render_template(
        "admin_map_call.html",
        call=call,
        owner_login=owner_login,
        owner_name=owner_name,
        owner_lat=owner_loc["lat"] if owner_loc else None,
        owner_lng=owner_loc["lng"] if owner_loc else None,
    )


@app.route("/")
@login_required
def calls_list():
    page = request.args.get("page", 1, type=int) or 1
    q = (request.args.get("q") or "").strip()
    field = request.args.get("field") or "name"
    view = request.args.get("view") or "all"
    map_on = request.args.get("map") == "on"
    list_on = request.args.get("list") == "on" or g.user["role"] == "doctor"
    accept_id = request.args.get("accept_id", type=int)
    focus_call = request.args.get("focus", type=int)
    if field not in SEARCH_FIELDS:
        field = "name"

    page_calls, page, total_pages, all_calls = prepare_calls(q, field, view, page)
    q_display = (phone_mask_display("".join(ch for ch in q if ch.isdigit())) if field == "phone" and q else q)
    my_active = ACTIVE_CALLS.get(g.user["login"]) if g.user["role"] == "doctor" else None

    my_active_call = None
    if g.user["role"] == "doctor" and my_active:
        raw = next((c for c in CALLS if c["id"] == my_active), None)
        if raw:
            my_active_call = enrich_call(raw)

    return render_template(
        "calls_list.html",
        calls=page_calls, page=page, total_pages=total_pages, total=len(all_calls),
        q=q, q_display=q_display, field=field, view=view,
        active_call_id=my_active, my_active_call=my_active_call,
        map_on=map_on, list_on=list_on, accept_id=accept_id, focus_call=focus_call,
    )


@app.route("/search")
@login_required
def calls_search():
    page = request.args.get("page", 1, type=int) or 1
    q = (request.args.get("q") or "").strip()
    field = request.args.get("field") or "name"
    view = request.args.get("view") or "all"
    if field not in SEARCH_FIELDS:
        field = "name"

    page_calls, page, total_pages, all_calls = prepare_calls(q, field, view, page)
    q_display = (phone_mask_display("".join(ch for ch in q if ch.isdigit())) if field == "phone" and q else q)
    my_active = ACTIVE_CALLS.get(g.user["login"]) if g.user["role"] == "doctor" else None

    return render_template(
        "_calls_results.html",
        calls=page_calls, page=page, total_pages=total_pages, total=len(all_calls),
        q=q, q_display=q_display, field=field, view=view, active_call_id=my_active,
    )


@app.route("/api/map_data")
@login_required
def api_map_data():
    view = request.args.get("view") or "all"
    is_admin = g.user["role"] in ("admin", "superadmin")

    calls = [enrich_call(c) for c in CALLS if c["id"] not in COMPLETED]
    if view == "nearest":
        calls.sort(key=lambda c: (c["distance_km"] is None, c["distance_km"] or 0))
        calls = calls[:1]

    calls_data = []
    for c in calls:
        p = PATIENTS.get(c["patient_id"], {})
        calls_data.append({
            "id": c["id"], "lat": c["lat"], "lng": c["lng"], "patient_id": c["patient_id"],
            "patient_name": p.get("name", "—"), "address": c["address"],
            "priority": c.get("priority"), "priority_label": c.get("priority_label"),
            "reason": c.get("reason", ""),
            "distance_km": c["distance_km"], "is_completed": c["is_completed"], "result": c["result"],
            "active_owner": c["active_owner"],
        })

    doctors = []
    if is_admin:
        for login, loc in DOCTOR_LOCATIONS.items():
            if login not in USERS or USERS[login]["role"] != "doctor":
                continue
            active_call = ACTIVE_CALLS.get(login)
            doctors.append({
                "login": login,
                "name": USERS[login]["name"],
                "lat": loc["lat"],
                "lng": loc["lng"],
                "active_call_id": active_call,
            })

    return jsonify({"calls": calls_data, "doctors": doctors})


@app.route("/call/<int:call_id>")
@login_required
def call_card(call_id):
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash(f"Вызов #{call_id} не найден", "danger")
        return redirect(url_for("calls_list"))
    call = enrich_call(call)
    info = [i for i in PATIENT_INFO if i["call_id"] == call_id]
    problems = [p for p in PROBLEMS if p["call_id"] == call_id]
    cases = [c for c in CASES if c["call_id"] == call_id]
    diary = [d for d in DIARY if d["call_id"] == call_id]
    my_active = ACTIVE_CALLS.get(g.user["login"]) if g.user["role"] == "doctor" else None
    return render_template(
        "call_card.html", call=call, patient_info=info, problems=problems,
        cases=cases, diary=diary, active_call_id=my_active,
    )


@app.route("/call/<int:call_id>/accept", methods=["POST"])
@role_required("doctor")
def call_accept(call_id):
    verify_csrf()
    if call_id in COMPLETED:
        flash("Этот вызов уже завершён.", "warning")
        return redirect(url_for("call_card", call_id=call_id))
    current = ACTIVE_CALLS.get(g.user["login"])
    if current is not None and current != call_id:
        flash(f"У вас уже активный вызов #{current}. Завершите его сначала.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    for other_login, cid in ACTIVE_CALLS.items():
        if cid == call_id and other_login != g.user["login"]:
            flash("Этот вызов уже взят другим фельдшером.", "danger")
            return redirect(url_for("calls_list"))
    ACTIVE_CALLS[g.user["login"]] = call_id
    CALL_STATUS[call_id] = "accepted"
    flash(f"Вызов #{call_id} принят", "success")
    return redirect(url_for("call_card", call_id=call_id))


@app.route("/call/<int:call_id>/status", methods=["POST"])
@role_required("doctor")
def call_status(call_id):
    verify_csrf()
    if ACTIVE_CALLS.get(g.user["login"]) != call_id:
        flash("Менять статус можно только у своего активного вызова.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    new_status = request.form.get("status")
    if new_status not in ("en_route", "arrived"):
        abort(400)
    CALL_STATUS[call_id] = new_status
    flash(f"Статус обновлён: {STATUS_LABELS.get(new_status, new_status)}", "success")
    return redirect(url_for("call_card", call_id=call_id))


@app.route("/call/<int:call_id>/complete", methods=["POST"])
@role_required("doctor")
def call_complete(call_id):
    verify_csrf()
    if ACTIVE_CALLS.get(g.user["login"]) != call_id:
        flash("Завершить можно только свой активный вызов.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    COMPLETED[call_id] = "normal"
    ACTIVE_CALLS.pop(g.user["login"], None)
    CALL_STATUS.pop(call_id, None)
    flash(f"Вызов #{call_id} завершён", "success")
    return redirect(url_for("calls_list"))


@app.route("/call/<int:call_id>/false", methods=["POST"])
@role_required("doctor")
def call_false(call_id):
    verify_csrf()
    if ACTIVE_CALLS.get(g.user["login"]) != call_id:
        flash("Отметить ложным можно только свой активный вызов.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    COMPLETED[call_id] = "false"
    ACTIVE_CALLS.pop(g.user["login"], None)
    CALL_STATUS.pop(call_id, None)
    flash(f"Вызов #{call_id} отмечен как ложный", "warning")
    return redirect(url_for("calls_list"))


@app.route("/call/<int:call_id>/info/new", methods=["GET", "POST"])
@role_required("doctor")
def info_new(call_id):
    global _info_seq
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash("Вызов не найден", "danger")
        return redirect(url_for("calls_list"))
    if ACTIVE_CALLS.get(g.user["login"]) != call_id:
        flash("Информацию можно добавлять только к своему активному вызову.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    if request.method == "POST":
        verify_csrf()
        data = request.form.to_dict()
        _info_seq += 1
        PATIENT_INFO.append({
            "id": _info_seq, "call_id": call_id, "author": g.user["login"],
            "type": data.get("type", ""), "text": data.get("text", ""),
            "time": datetime.now().strftime("%H:%M"), "incorrect": False,
        })
        flash("Информация сохранена", "success")
        return redirect(url_for("call_card", call_id=call_id))
    info_types = ["Данные о здоровье пациента", "Жалобы пациента", "Витальные показатели", "Лекарства / аллергии", "Другое"]
    return render_template(
        "patient_info_form.html",
        form_title=f"Информация про пациента (вызов #{call_id})",
        form_action=f"/call/{call_id}/info/new",
        info_types=info_types, call_id=call_id,
    )


@app.route("/call/<int:call_id>/problems/new", methods=["GET", "POST"])
@role_required("doctor")
def problems_new(call_id):
    global _problem_seq
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash("Вызов не найден", "danger")
        return redirect(url_for("calls_list"))
    if ACTIVE_CALLS.get(g.user["login"]) != call_id:
        flash("Проблемы можно добавлять только к своему активному вызову.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    if request.method == "POST":
        verify_csrf()
        data = request.form.to_dict()
        _problem_seq += 1
        PROBLEMS.append({
            "id": _problem_seq, "call_id": call_id, "author": g.user["login"],
            "type": data.get("type", ""), "text": data.get("text", ""),
            "time": datetime.now().strftime("%H:%M"), "incorrect": False,
        })
        flash("Проблема зафиксирована", "success")
        return redirect(url_for("call_card", call_id=call_id))
    problem_types = ["Проблемы с автомобилем", "Проблемы с пациентом", "Другое"]
    return render_template(
        "problems_form.html",
        form_title=f"Проблемы на вызове #{call_id}",
        form_action=f"/call/{call_id}/problems/new",
        problem_types=problem_types, call_id=call_id,
    )


@app.route("/call/<int:call_id>/case/new", methods=["GET", "POST"])
@role_required("doctor")
def case_new(call_id):
    global _case_seq
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash("Вызов не найден", "danger")
        return redirect(url_for("calls_list"))
    if ACTIVE_CALLS.get(g.user["login"]) != call_id:
        flash("Случай можно добавлять только к своему активному вызову.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    if request.method == "POST":
        verify_csrf()
        data = request.form.to_dict()
        _case_seq += 1
        CASES.append({
            "id": _case_seq, "call_id": call_id, "author": g.user["login"],
            "type": data.get("type", ""), "result": data.get("result", ""),
            "text": data.get("text", ""), "time": datetime.now().strftime("%H:%M"),
        })
        flash("Случай обслуживания сохранён", "success")
        return redirect(url_for("call_card", call_id=call_id))
    case_types = ["Первичный вызов", "Повторный вызов", "Консультация", "Другое"]
    return render_template(
        "case_form.html",
        form_title=f"Случай обслуживания (вызов #{call_id})",
        form_action=f"/call/{call_id}/case/new",
        case_types=case_types, call_id=call_id,
    )


@app.route("/call/<int:call_id>/diary/new", methods=["GET", "POST"])
@role_required("doctor")
def diary_new(call_id):
    global _diary_seq
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash("Вызов не найден", "danger")
        return redirect(url_for("calls_list"))
    if ACTIVE_CALLS.get(g.user["login"]) != call_id:
        flash("Дневник можно добавлять только к своему активному вызову.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    if request.method == "POST":
        verify_csrf()
        data = request.form.to_dict()
        _diary_seq += 1
        DIARY.append({
            "id": _diary_seq, "call_id": call_id, "author": g.user["login"],
            "type": data.get("type", ""), "text": data.get("text", ""),
            "time": datetime.now().strftime("%H:%M"),
        })
        flash("Запись дневника сохранена", "success")
        return redirect(url_for("call_card", call_id=call_id))
    diary_types = ["Осмотр", "Наблюдение", "Изменение состояния", "Другое"]
    return render_template(
        "diary_form.html",
        form_title=f"Дневник (вызов #{call_id})",
        form_action=f"/call/{call_id}/diary/new",
        diary_types=diary_types, call_id=call_id,
    )


@app.route("/call/<int:call_id>/info/<int:info_id>/mark_incorrect", methods=["POST"])
@role_required("doctor")
def info_mark_incorrect(call_id, info_id):
    verify_csrf()
    rec = next((r for r in PATIENT_INFO if r["id"] == info_id and r["call_id"] == call_id), None)
    if not rec:
        flash("Запись не найдена", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    if rec.get("author") != g.user["login"]:
        abort(403)
    rec["incorrect"] = True
    flash("Запись отмечена как некорректная", "warning")
    return redirect(url_for("call_card", call_id=call_id))


@app.route("/call/<int:call_id>/problems/<int:problem_id>/mark_incorrect", methods=["POST"])
@role_required("doctor")
def problem_mark_incorrect(call_id, problem_id):
    verify_csrf()
    rec = next((r for r in PROBLEMS if r["id"] == problem_id and r["call_id"] == call_id), None)
    if not rec:
        flash("Запись не найдена", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    if rec.get("author") != g.user["login"]:
        abort(403)
    rec["incorrect"] = True
    flash("Проблема отмечена как некорректная", "warning")
    return redirect(url_for("call_card", call_id=call_id))


APPOINTMENTS = []


@app.route("/patient/<int:patient_id>")
@login_required
def patient_card(patient_id):
    patient = PATIENTS.get(patient_id)
    if not patient:
        flash(f"Пациент #{patient_id} не найден", "danger")
        return render_template("patient_card.html", patient=None, appointments=[])
    appointments = [a for a in APPOINTMENTS if a["patient_id"] == patient_id]
    return render_template("patient_card.html", patient=patient, appointments=appointments)


@app.route("/patient/<int:patient_id>/appointment/new", methods=["GET", "POST"])
@login_required
def appointment_new(patient_id):
    if request.method == "POST":
        verify_csrf()
        data = request.form.to_dict()
        APPOINTMENTS.append({
            "patient_id": patient_id, "text": data.get("text", ""),
            "time": datetime.now().strftime("%H:%M"),
        })
        flash("Запись на приём сохранена", "success")
        return redirect(url_for("patient_card", patient_id=patient_id))
    return render_template(
        "form.html",
        form_title=f"Запись на приём (пациент #{patient_id})",
        form_action=f"/patient/{patient_id}/appointment/new",
    )


@app.route("/map/route/<int:call_id>")
@login_required
def map_route(call_id):
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash(f"Вызов #{call_id} не найден", "danger")
        return redirect(url_for("calls_list"))
    if g.user["role"] in ("admin", "superadmin"):
        return redirect(url_for("admin_map_call", call_id=call_id))
    return render_template("map_route.html", call=enrich_call(call))


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, message="Некорректный запрос"), 400


@app.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Нет доступа"), 403


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith(("/api/", "/static/")):
        return ("Not Found", 404)
    flash("Страница не найдена", "warning")
    return redirect(url_for("calls_list"))


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)