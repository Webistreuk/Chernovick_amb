import math
import os
import requests
from flask import (
    Flask, render_template, jsonify, request,
    redirect, url_for, flash, send_from_directory, Response, abort
)
from datetime import datetime

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

PER_PAGE = 5
SEARCH_FIELDS = ("name", "address", "phone")

BASE_LAT = 43.585
BASE_LNG = 39.723

ACTIVE_CALL_ID = None
COMPLETED = {}
PATIENT_INFO = []
PROBLEMS = []
_info_seq = 0
_problem_seq = 0

# ---------- Локальный кэш тайлов ----------
TILES_DIR = os.path.join(app.root_path, "static", "tiles")
os.makedirs(TILES_DIR, exist_ok=True)

OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
OSM_UA = "AmbulanceLocalMap/1.0 (contact: dev@example.com)"

EMPTY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xf8\xff"
    b"\xff?\x00\x05\xfe\x02\xfe\xa75\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)


def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------- 20 пациентов ----------
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

# ---------- 20 вызовов ----------
CALLS = [
    {"id": 1,  "number": "1245", "address": "ул. Ленина 5",        "status": "critical", "patient_id": 1,  "created_at": "2026-11-20T08:15:00", "lat": 43.596226, "lng": 39.730886},
    {"id": 2,  "number": "1246", "address": "пр. Мира 12",          "status": "medium",   "patient_id": 2,  "created_at": "2026-11-20T09:40:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 3,  "number": "1247", "address": "ул. Гагарина 3",       "status": "low",      "patient_id": 3,  "created_at": "2026-11-20T11:05:00", "lat": 43.6037919, "lng": 39.7243046},
    {"id": 4,  "number": "1248", "address": "ул. Пушкина 17",       "status": "critical", "patient_id": 4,  "created_at": "2026-11-20T13:22:00", "lat": 43.568333, "lng": 39.738889},
    {"id": 5,  "number": "1249", "address": "пр. Победы 44",        "status": "medium",   "patient_id": 5,  "created_at": "2026-11-20T15:50:00", "lat": 43.911960, "lng": 39.328028},
    {"id": 6,  "number": "1250", "address": "ул. Садовая 8",        "status": "low",      "patient_id": 6,  "created_at": "2026-11-20T18:10:00", "lat": 43.4301045, "lng": 39.9262999},
    {"id": 7,  "number": "1251", "address": "ул. Кирова 21",        "status": "critical", "patient_id": 7,  "created_at": "2026-11-21T07:30:00", "lat": 43.4268257, "lng": 39.9253134},
    {"id": 8,  "number": "1252", "address": "пр. Космонавтов 9",    "status": "medium",   "patient_id": 8,  "created_at": "2026-11-21T10:12:00", "lat": 43.585278, "lng": 39.720278},
    {"id": 9,  "number": "1253", "address": "ул. Чехова 14",        "status": "low",      "patient_id": 9,  "created_at": "2026-11-21T12:45:00", "lat": 43.618655, "lng": 39.724751},
    {"id": 10, "number": "1254", "address": "ул. Горького 30",      "status": "critical", "patient_id": 10, "created_at": "2026-11-21T16:20:00", "lat": 43.5913678, "lng": 39.727046},
    {"id": 11, "number": "1255", "address": "пр. Октябрьский 5",    "status": "medium",   "patient_id": 11, "created_at": "2026-11-22T08:05:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 12, "number": "1256", "address": "ул. Лермонтова 2",     "status": "low",      "patient_id": 12, "created_at": "2026-11-22T11:35:00", "lat": 43.574, "lng": 39.7377},
    {"id": 13, "number": "1257", "address": "ул. Некрасова 11",     "status": "critical", "patient_id": 13, "created_at": "2026-11-22T14:00:00", "lat": 43.5148139, "lng": 39.867396},
    {"id": 14, "number": "1258", "address": "пр. Строителей 18",    "status": "medium",   "patient_id": 14, "created_at": "2026-11-22T17:25:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 15, "number": "1259", "address": "ул. Толстого 6",       "status": "low",      "patient_id": 15, "created_at": "2026-11-23T09:10:00", "lat": 43.8972187, "lng": 39.3500412},
    {"id": 16, "number": "1260", "address": "ул. Достоевского 4",   "status": "critical", "patient_id": 16, "created_at": "2026-11-23T12:50:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 17, "number": "1261", "address": "пр. Ленинградский 22", "status": "medium",   "patient_id": 17, "created_at": "2026-11-23T15:30:00", "lat": 43.585525, "lng": 39.723062},
    {"id": 18, "number": "1262", "address": "ул. Маяковского 7",    "status": "low",      "patient_id": 18, "created_at": "2026-11-23T18:15:00", "lat": 43.9030792, "lng": 39.3430953},
    {"id": 19, "number": "1263", "address": "ул. Тургенева 10",     "status": "critical", "patient_id": 19, "created_at": "2026-11-24T08:40:00", "lat": 43.572999, "lng": 39.737201},
    {"id": 20, "number": "1264", "address": "пр. Советский 1",      "status": "medium",   "patient_id": 20, "created_at": "2026-11-24T11:05:00", "lat": 43.582632, "lng": 39.719073},
]


def enrich_call(call):
    p = PATIENTS.get(call["patient_id"], {})
    lat = call.get("lat")
    lng = call.get("lng")
    dist = None
    if lat is not None and lng is not None:
        dist = round(haversine_km(BASE_LAT, BASE_LNG, lat, lng), 1)
    return {
        **call,
        "patient_name": p.get("name", "—"),
        "patient_phone": p.get("phone", "—"),
        "distance_km": dist,
        "is_active": call["id"] == ACTIVE_CALL_ID,
        "is_completed": call["id"] in COMPLETED,
        "result": COMPLETED.get(call["id"]),
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
    return {
        "calls": all_calls[start:start + PER_PAGE],
        "page": page,
        "total_pages": total_pages,
        "total": total,
    }


def prepare_calls(q, field, view, page):
    all_calls = filter_calls(q, field)
    all_calls.sort(key=lambda c: c["created_at"], reverse=True)
    all_calls.sort(key=lambda c: (c["is_completed"], not c["is_active"]))

    if view == "nearest":
        all_calls.sort(key=lambda c: (c["distance_km"] is None, c["distance_km"] or 0))
        all_calls = all_calls[:1]
        return all_calls, 1, 1, all_calls

    pdata = paginate(all_calls, page)
    return pdata["calls"], pdata["page"], pdata["total_pages"], all_calls


def phone_mask_display(digits):
    template = "XXX XXX-XX-XX"
    out = ""
    di = 0
    for ch in template:
        if ch == "X":
            out += digits[di] if di < len(digits) else "X"
            di += 1
        else:
            out += ch
    return "+7 " + out


# ---------- Прокси тайлов ----------
@app.route("/tiles/<int:z>/<int:x>/<int:y>.png")
def tile(z, x, y):
    if not (0 <= z <= 19 and 0 <= x < 2**z and 0 <= y < 2**z):
        abort(404)

    path_dir = os.path.join(TILES_DIR, str(z), str(x))
    file_name = f"{y}.png"
    file_path = os.path.join(path_dir, file_name)

    if os.path.isfile(file_path):
        return send_from_directory(path_dir, file_name, mimetype="image/png")

    try:
        r = requests.get(
            OSM_URL.format(z=z, x=x, y=y),
            headers={"User-Agent": OSM_UA},
            timeout=8,
        )
        if r.status_code == 200 and r.content:
            os.makedirs(path_dir, exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(r.content)
            return Response(r.content, mimetype="image/png")
    except requests.RequestException:
        pass

    return Response(EMPTY_PNG, mimetype="image/png")


# ---------- Список вызовов ----------
@app.route("/")
def calls_list():
    page = request.args.get("page", 1, type=int) or 1
    q = (request.args.get("q") or "").strip()
    field = request.args.get("field") or "name"
    view = request.args.get("view") or "all"
    map_on = request.args.get("map") == "on"
    accept_id = request.args.get("accept_id", type=int)

    if field not in SEARCH_FIELDS:
        field = "name"

    page_calls, page, total_pages, all_calls = prepare_calls(q, field, view, page)
    q_display = (phone_mask_display("".join(ch for ch in q if ch.isdigit()))
                 if field == "phone" and q else q)

    return render_template(
        "calls_list.html",
        calls=page_calls, page=page,
        total_pages=total_pages, total=len(all_calls),
        q=q, q_display=q_display, field=field, view=view,
        active_call_id=ACTIVE_CALL_ID,
        map_on=map_on,
        accept_id=accept_id,
    )


@app.route("/search")
def calls_search():
    page = request.args.get("page", 1, type=int) or 1
    q = (request.args.get("q") or "").strip()
    field = request.args.get("field") or "name"
    view = request.args.get("view") or "all"

    if field not in SEARCH_FIELDS:
        field = "name"

    page_calls, page, total_pages, all_calls = prepare_calls(q, field, view, page)
    q_display = (phone_mask_display("".join(ch for ch in q if ch.isdigit()))
                 if field == "phone" and q else q)

    return render_template(
        "_calls_results.html",
        calls=page_calls, page=page,
        total_pages=total_pages, total=len(all_calls),
        q=q, q_display=q_display, field=field, view=view,
        active_call_id=ACTIVE_CALL_ID,
    )


@app.route("/api/map_points")
def api_map_points():
    view = request.args.get("view") or "all"
    calls = [enrich_call(c) for c in CALLS]

    if view == "nearest":
        calls.sort(key=lambda c: (c["distance_km"] is None, c["distance_km"] or 0))
        calls = calls[:1]

    points = []
    for c in calls:
        p = PATIENTS.get(c["patient_id"], {})
        points.append({
            "id": c["id"],
            "lat": c["lat"],
            "lng": c["lng"],
            "patient_id": c["patient_id"],
            "patient_name": p.get("name", "—"),
            "address": c["address"],
            "status": c["status"],
            "distance_km": c["distance_km"],
            "is_completed": c["is_completed"],
            "result": c["result"],
        })
    return jsonify(points)


@app.route("/call/<int:call_id>")
def call_card(call_id):
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash(f"Вызов #{call_id} не найден", "danger")
        return redirect(url_for("calls_list"))
    call = enrich_call(call)
    info = [i for i in PATIENT_INFO if i["call_id"] == call_id]
    problems = [p for p in PROBLEMS if p["call_id"] == call_id]
    return render_template(
        "call_card.html",
        call=call, patient_info=info, problems=problems,
        active_call_id=ACTIVE_CALL_ID,
    )


@app.route("/call/<int:call_id>/accept", methods=["POST"])
def call_accept(call_id):
    global ACTIVE_CALL_ID
    if call_id in COMPLETED:
        flash("Этот вызов уже завершён.", "warning")
        return redirect(url_for("call_card", call_id=call_id))
    if ACTIVE_CALL_ID is not None and ACTIVE_CALL_ID != call_id:
        flash(f"У вас уже активный вызов #{ACTIVE_CALL_ID}. Завершите его сначала.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    ACTIVE_CALL_ID = call_id
    flash(f"Вызов #{call_id} принят", "success")
    return redirect(url_for("call_card", call_id=call_id))


@app.route("/call/<int:call_id>/complete", methods=["POST"])
def call_complete(call_id):
    global ACTIVE_CALL_ID
    if ACTIVE_CALL_ID != call_id:
        flash("Завершить можно только активный вызов.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    COMPLETED[call_id] = "normal"
    ACTIVE_CALL_ID = None
    flash(f"Вызов #{call_id} завершён", "success")
    return redirect(url_for("calls_list"))


@app.route("/call/<int:call_id>/false", methods=["POST"])
def call_false(call_id):
    global ACTIVE_CALL_ID
    if ACTIVE_CALL_ID != call_id:
        flash("Отметить ложным можно только активный вызов.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    COMPLETED[call_id] = "false"
    ACTIVE_CALL_ID = None
    flash(f"Вызов #{call_id} отмечен как ложный", "warning")
    return redirect(url_for("calls_list"))


@app.route("/call/<int:call_id>/info/new", methods=["GET", "POST"])
def info_new(call_id):
    global _info_seq
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash("Вызов не найден", "danger")
        return redirect(url_for("calls_list"))
    if ACTIVE_CALL_ID != call_id:
        flash("Информацию можно добавлять только к активному вызову.", "danger")
        return redirect(url_for("call_card", call_id=call_id))

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        _info_seq += 1
        PATIENT_INFO.append({
            "id": _info_seq,
            "call_id": call_id,
            "type": data.get("type", ""),
            "text": data.get("text", ""),
            "time": datetime.now().strftime("%H:%M"),
            "incorrect": False,
        })
        flash("Информация сохранена", "success")
        return redirect(url_for("call_card", call_id=call_id))

    info_types = [
        "Данные о здоровье пациента",
        "Жалобы пациента",
        "Витальные показатели",
        "Лекарства / аллергии",
        "Другое",
    ]
    return render_template(
        "patient_info_form.html",
        form_title=f"Информация про пациента (вызов #{call_id})",
        form_action=f"/call/{call_id}/info/new",
        info_types=info_types,
        call_id=call_id,
    )


@app.route("/call/<int:call_id>/problems/new", methods=["GET", "POST"])
def problems_new(call_id):
    global _problem_seq
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash("Вызов не найден", "danger")
        return redirect(url_for("calls_list"))
    if ACTIVE_CALL_ID != call_id:
        flash("Проблемы можно добавлять только к активному вызову.", "danger")
        return redirect(url_for("call_card", call_id=call_id))

    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        _problem_seq += 1
        PROBLEMS.append({
            "id": _problem_seq,
            "call_id": call_id,
            "type": data.get("type", ""),
            "text": data.get("text", ""),
            "time": datetime.now().strftime("%H:%M"),
            "incorrect": False,
        })
        flash("Проблема зафиксирована", "success")
        return redirect(url_for("call_card", call_id=call_id))

    problem_types = [
        "Проблемы с автомобилем",
        "Проблемы с пациентом",
        "Другое",
    ]
    return render_template(
        "problems_form.html",
        form_title=f"Проблемы на вызове #{call_id}",
        form_action=f"/call/{call_id}/problems/new",
        problem_types=problem_types,
        call_id=call_id,
    )


@app.route("/call/<int:call_id>/info/<int:info_id>/mark_incorrect", methods=["POST"])
def info_mark_incorrect(call_id, info_id):
    if ACTIVE_CALL_ID != call_id:
        flash("Отмечать можно только записи активного вызова.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    rec = next((r for r in PATIENT_INFO if r["id"] == info_id and r["call_id"] == call_id), None)
    if not rec:
        flash("Запись не найдена", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    rec["incorrect"] = True
    flash("Запись отмечена как некорректная", "warning")
    return redirect(url_for("call_card", call_id=call_id))


@app.route("/call/<int:call_id>/problems/<int:problem_id>/mark_incorrect", methods=["POST"])
def problem_mark_incorrect(call_id, problem_id):
    if ACTIVE_CALL_ID != call_id:
        flash("Отмечать можно только записи активного вызова.", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    rec = next((r for r in PROBLEMS if r["id"] == problem_id and r["call_id"] == call_id), None)
    if not rec:
        flash("Запись не найдена", "danger")
        return redirect(url_for("call_card", call_id=call_id))
    rec["incorrect"] = True
    flash("Проблема отмечена как некорректная", "warning")
    return redirect(url_for("call_card", call_id=call_id))


APPOINTMENTS = []


@app.route("/patient/<int:patient_id>")
def patient_card(patient_id):
    patient = PATIENTS.get(patient_id)
    if not patient:
        flash(f"Пациент #{patient_id} не найден", "danger")
        return render_template("patient_card.html", patient=None, appointments=[])
    appointments = [a for a in APPOINTMENTS if a["patient_id"] == patient_id]
    return render_template("patient_card.html", patient=patient, appointments=appointments)


@app.route("/patient/<int:patient_id>/appointment/new", methods=["GET", "POST"])
def appointment_new(patient_id):
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form.to_dict()
        APPOINTMENTS.append({
            "patient_id": patient_id,
            "text": data.get("text", ""),
            "time": datetime.now().strftime("%H:%M"),
        })
        flash("Запись на приём сохранена", "success")
        return redirect(url_for("patient_card", patient_id=patient_id))
    return render_template("form.html",
                           form_title=f"Запись на приём (пациент #{patient_id})",
                           form_action=f"/patient/{patient_id}/appointment/new")


@app.route("/map/route/<int:call_id>")
def map_route(call_id):
    call = next((c for c in CALLS if c["id"] == call_id), None)
    if not call:
        flash(f"Вызов #{call_id} не найден", "danger")
        return redirect(url_for("calls_list"))
    return render_template("map_route.html", call=enrich_call(call))


@app.route("/sw.js")
def service_worker():
    resp = app.send_static_file("sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Content-Type"] = "application/javascript"
    return resp


@app.route("/api/case", methods=["POST"])
def api_case():
    data = request.get_json() or request.form.to_dict()
    return jsonify({"ok": True, "client_id": data.get("client_id")})


@app.errorhandler(404)
def not_found(e):
    flash("Страница не найдена", "warning")
    return redirect(url_for("calls_list"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)