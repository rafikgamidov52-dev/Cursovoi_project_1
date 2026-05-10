"""
ДомКлюч.kz — демо: Flask + SQLite, регистрация, админ, каталог, kk/ru/en.
Запуск: pip install -r requirements.txt && python app.py
Админ по умолчанию: admin@domkey.kz / admin123
При ошибках схемы БД удалите файл site.db и перезапустите приложение.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from i18n import (
    CITY_KEYS,
    FAQ_BY_LANG,
    listing_description,
    listing_title,
    t,
    utilities_note,
)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "site.db"

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@domkey.kz")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-cursovoi-change-me")


def get_locale() -> str:
    loc = session.get("locale", "ru")
    return loc if loc in ("kk", "ru", "en") else "ru"


@app.before_request
def load_logged_in_user() -> None:
    g.user = None
    uid = session.get("user_id")
    if uid is None:
        return
    row = query_one("SELECT * FROM users WHERE id = ?", (uid,))
    if row:
        g.user = row


@app.context_processor
def inject_i18n() -> dict:
    loc = get_locale()

    def _t(key: str) -> str:
        return t(loc, key)

    return dict(
        t=_t,
        locale=loc,
        faq_items=FAQ_BY_LANG.get(loc, FAQ_BY_LANG["ru"]),
        catalog_cities=CITY_KEYS,
    )


@app.template_global()
def index_url(**overrides):
    args = {k: v for k, v in request.args.items() if v and k != "page"}
    for k, v in overrides.items():
        if v is None or v == "":
            args.pop(k, None)
        else:
            args[k] = str(v)
    return url_for("index", **args)


@app.template_filter("tenge_fmt")
def tenge_fmt(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


@app.template_filter("listing_t")
def listing_t_filter(row) -> str:
    return listing_title(dict(row), get_locale())


@app.template_filter("badge_label")
def badge_label_filter(badge) -> str | None:
    if not badge:
        return None
    loc = get_locale()
    m = {"Новое": t(loc, "badge_new"), "Собственник": t(loc, "badge_owner")}
    return m.get(badge, badge)


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query_one(sql: str, args=()):
    cur = get_db().execute(sql, args)
    return cur.fetchone()


def query_all(sql: str, args=()):
    cur = get_db().execute(sql, args)
    return cur.fetchall()


def init_db() -> None:
    db = sqlite3.connect(DATABASE)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            phone TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            price INTEGER NOT NULL,
            city TEXT NOT NULL,
            district TEXT,
            rooms TEXT NOT NULL,
            area_m2 INTEGER NOT NULL,
            floor INTEGER NOT NULL,
            floors_total INTEGER NOT NULL,
            term TEXT NOT NULL,
            owner_type TEXT NOT NULL,
            deposit INTEGER,
            image_url TEXT NOT NULL,
            badge TEXT,
            title_ru TEXT NOT NULL,
            title_kk TEXT NOT NULL,
            title_en TEXT NOT NULL,
            description_ru TEXT NOT NULL,
            description_kk TEXT NOT NULL,
            description_en TEXT NOT NULL,
            utilities_ru TEXT,
            utilities_kk TEXT,
            utilities_en TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (owner_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            listing_id INTEGER NOT NULL,
            from_user_id INTEGER NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (listing_id) REFERENCES listings(id),
            FOREIGN KEY (from_user_id) REFERENCES users(id)
        );
        """
    )
    db.commit()
    db.close()


def seed_if_empty() -> None:
    conn = sqlite3.connect(DATABASE)
    try:
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if n > 0:
            return
        now = datetime.now(timezone.utc).isoformat()
        owners = [
        (
            "owner1@demo.kz",
            generate_password_hash("demo123"),
            "Айгуль Нурланова",
            "+7 701 111 2233",
            0,
        ),
        (
            "owner2@demo.kz",
            generate_password_hash("demo123"),
            "Ерлан Сейтбеков",
            "+7 702 222 3344",
            0,
        ),
        (
            "owner3@demo.kz",
            generate_password_hash("demo123"),
            "Мария Ким",
            "+7 705 333 4455",
            0,
        ),
        ]
        for email, ph, name, phone, adm in owners:
            conn.execute(
                "INSERT INTO users (email, password_hash, full_name, phone, is_admin, created_at) VALUES (?,?,?,?,?,?)",
                (email, ph, name, phone, adm, now),
            )
        conn.execute(
            "INSERT INTO users (email, password_hash, full_name, phone, is_admin, created_at) VALUES (?,?,?,?,?,?)",
            (
                ADMIN_EMAIL,
                generate_password_hash(ADMIN_PASSWORD),
                "Администратор",
                "+7 777 000 0000",
                1,
                now,
            ),
        )
        conn.commit()

        o1 = conn.execute("SELECT id FROM users WHERE email = ?", ("owner1@demo.kz",)).fetchone()[0]
        o2 = conn.execute("SELECT id FROM users WHERE email = ?", ("owner2@demo.kz",)).fetchone()[0]
        o3 = conn.execute("SELECT id FROM users WHERE email = ?", ("owner3@demo.kz",)).fetchone()[0]

        imgs = [
        "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800&q=80",
        "https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800&q=80",
        "https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800&q=80",
        "https://images.unsplash.com/photo-1493809842364-78817add7ffb?w=800&q=80",
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&q=80",
        "https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800&q=80",
        "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=800&q=80",
        "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80",
        "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=800&q=80",
        "https://images.unsplash.com/photo-1600566753190-17f0baa2a6c3?w=800&q=80",
        "https://images.unsplash.com/photo-1600047509807-ba8f99d2cdde?w=800&q=80",
        ]

        rows = [
        (
            o1,
            420_000,
            "Алматы",
            "Медеуский р-н",
            "2",
            56,
            7,
            9,
            "от 11 мес.",
            "Агентство",
            None,
            imgs[0],
            "Новое",
            "Двухкомнатная у Ботанического",
            "Ботаникалық бақтың жанындағы екі бөлмелі",
            "Two-room flat near the Botanical Garden",
            "Светлая квартира с видом на горы, полностью меблирована, кухня-студия с техникой.",
            "Тауға қарайтын жарық пәтер, толық жиһаздалған.",
            "Bright flat with mountain view, furnished, equipped kitchen.",
            "Коммунальные ~25 000 ₸",
            "Коммуналдық ~25 000 ₸",
            "Utilities ~25,000 ₸",
        ),
        (
            o2,
            310_000,
            "Астана",
            "Есильский р-н",
            "Студия",
            32,
            14,
            20,
            "долгосрок",
            "От собственника",
            310_000,
            imgs[1],
            None,
            "Студия в Highvill",
            "Highvill студиясы",
            "Studio in Highvill",
            "Компактная студия в новом ЖК, панорамные окна, охрана.",
            "Жаңа ТК студиясы, панорамалық терезелер.",
            "Compact studio in a new complex, concierge.",
            "КУ по счётчикам",
            "Санақтар бойынша КТ",
            "Metered utilities",
        ),
        (
            o1,
            185_000,
            "Шымкент",
            "Енбекшинский р-н",
            "1",
            38,
            3,
            5,
            "от 6 мес.",
            "Агентство",
            None,
            imgs[2],
            None,
            "Однушка у ТРЦ",
            "СОО жанындағы бір бөлмелі",
            "One-room near the mall",
            "Рядом с торговым центром, свежий ремонт, кондиционер.",
            "Сауда орталығының жанында, жөндеу жаңа.",
            "Near mall, recent renovation, AC.",
            "Включено отопление",
            "Жылу кіреді",
            "Heating included",
        ),
        (
            o3,
            380_000,
            "Астана",
            "Алматинский р-н",
            "2",
            61,
            9,
            12,
            "от 11 мес.",
            "От собственника",
            380_000,
            imgs[3],
            "Собственник",
            "2-комн., Нурлы Тау",
            "2 бөлме, Нұрлы Тау",
            "2 rooms, Nurly Tau",
            "Семейная планировка, два санузла, парковочное место.",
            "Отбасылық жоспарлау, екі ванна бөлмесі.",
            "Family layout, two bathrooms, parking.",
            "КУ отдельно",
            "КТ бөлек",
            "Utilities separate",
        ),
        (
            o2,
            520_000,
            "Алматы",
            "Бостандыкский р-н",
            "3 и более",
            82,
            4,
            9,
            "долгосрок",
            "Агентство",
            520_000,
            imgs[4],
            None,
            "3-комн., Самал-2",
            "3 бөлме, Самал-2",
            "3-room, Samal-2",
            "Просторная квартира для семьи, две лоджии, встроенная кухня.",
            "Үлкен отбасыға арналған кең пәтер.",
            "Spacious family flat, two balconies.",
            "КУ ~35 000 ₸",
            "КТ ~35 000 ₸",
            "Utilities ~35,000 ₸",
        ),
        (
            o1,
            240_000,
            "Шымкент",
            "мкр. Самал",
            "1",
            40,
            2,
            5,
            "от 6 месяцев",
            "От собственника",
            None,
            imgs[5],
            None,
            "1-комн., мкр. Самал",
            "1 бөлме, Самал алабы",
            "1-room, Samal microdistrict",
            "Тихий двор, рядом школа и остановка.",
            "Тыныш аула, мектеп жақын.",
            "Quiet yard, school nearby.",
            "По факту",
            "Факт бойынша",
            "As used",
        ),
        (
            o2,
            290_000,
            "Астана",
            "Есильский р-н",
            "Студия",
            29,
            11,
            16,
            "от 11 мес.",
            "Агентство",
            None,
            imgs[6],
            "Новое",
            "Студия, ЖК Nomad",
            "Nomad ТК студиясы",
            "Studio, Nomad complex",
            "Новая сдача, инфраструктура ЖК, спортзал в доме.",
            "Жаңа тапсыру, спортзал үйде.",
            "New build, gym in building.",
            "Фикс 15 000 ₸",
            "Тұрақты 15 000 ₸",
            "Fixed 15,000 ₸",
        ),
        (
            o3,
            175_000,
            "Караганда",
            "Казыбек би",
            "1",
            36,
            5,
            9,
            "долгосрок",
            "От собственника",
            100_000,
            imgs[7],
            None,
            "1-комн., Гульдер",
            "1 бөлме, Гүлдер",
            "1-room, Gulder",
            "Уютная однушка, мебель и техника остаются.",
            "Жылжымалы пәтер, жиһаз қалды.",
            "Cozy one-room, furniture stays.",
            "Зимой тепло",
            "Қыста жылы",
            "Warm in winter",
        ),
        (
            o1,
            450_000,
            "Алматы",
            "Алмалинский р-н",
            "2",
            58,
            6,
            12,
            "долгосрок",
            "Агентство",
            450_000,
            imgs[8],
            None,
            "2-комн., Абая — Жандосова",
            "2 бөлме, Абай — Жандосов",
            "2-room, Abay — Zhandosov",
            "Развязка и метро в пешей доступности.",
            "Метро жақын.",
            "Near metro interchange.",
            "КУ отдельно",
            "КТ бөлек",
            "Utilities separate",
        ),
        (
            o2,
            330_000,
            "Актобе",
            "Акжайык",
            "2",
            54,
            3,
            5,
            "от 6 мес.",
            "От собственника",
            None,
            imgs[9],
            None,
            "2-комн., жилмассив Акжайык",
            "2 бөлме, Ақжайық тұрғын алабы",
            "2-room, Akzhayyk",
            "Частный сектор рядом, парковка во дворе.",
            "Аулада тұрақ бар.",
            "Parking in yard.",
            "Умеренно",
            "Қалыпты",
            "Moderate",
        ),
        (
            o3,
            265_000,
            "Павлодар",
            "Левый берег",
            "1",
            42,
            8,
            12,
            "от 11 мес.",
            "Агентство",
            150_000,
            imgs[10],
            None,
            "1-комн., Левый берег",
            "1 бөлме, Сол жақ жағалау",
            "1-room, Left bank",
            "Вид на Иртыш, евроремонт.",
            "Ертіс көрінісі.",
            "Irtysh view, modern finish.",
            "~20 000 ₸",
            "~20 000 ₸",
            "~20,000 ₸",
        ),
        ]

        for r in rows:
            conn.execute(
                """INSERT INTO listings (
                owner_id, price, city, district, rooms, area_m2, floor, floors_total,
                term, owner_type, deposit, image_url, badge,
                title_ru, title_kk, title_en,
                description_ru, description_kk, description_en,
                utilities_ru, utilities_kk, utilities_en, created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                r + (now,),
            )
        conn.commit()
    finally:
        conn.close()


def ensure_admin_user() -> None:
    """Create/update admin account even on pre-existing databases."""
    conn = sqlite3.connect(DATABASE)
    try:
        row = conn.execute(
            "SELECT id FROM users WHERE lower(email) = lower(?)",
            (ADMIN_EMAIL,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE users SET is_admin = 1 WHERE id = ?",
                (row[0],),
            )
        else:
            conn.execute(
                """INSERT INTO users
                (email, password_hash, full_name, phone, is_admin, created_at)
                VALUES (?, ?, ?, ?, 1, ?)""",
                (
                    ADMIN_EMAIL,
                    generate_password_hash(ADMIN_PASSWORD),
                    "Администратор",
                    "+7 777 000 0000",
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
        conn.commit()
    finally:
        conn.close()


@app.route("/set-lang/<code>")
def set_lang(code: str):
    if code in ("kk", "ru", "en"):
        session["locale"] = code
    return redirect(request.referrer or url_for("index"))


@app.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        full_name = (request.form.get("full_name") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        err = []
        if not email or "@" not in email:
            err.append("email")
        if len(password) < 6:
            err.append("password_short")
        if not full_name:
            err.append("name")
        if err:
            flash("validation", "error")
            return render_template("register.html", form=request.form, err=err), 400
        try:
            get_db().execute(
                "INSERT INTO users (email, password_hash, full_name, phone, is_admin, created_at) VALUES (?,?,?,?,0,?)",
                (
                    email,
                    generate_password_hash(password),
                    full_name,
                    phone,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            get_db().commit()
        except sqlite3.IntegrityError:
            flash("email_taken", "error")
            return render_template("register.html", form=request.form, err=["email_taken"]), 400
        return redirect(url_for("login"))
    return render_template("register.html", form={}, err=[])


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        row = query_one("SELECT * FROM users WHERE email = ?", (email,))
        if not row or not check_password_hash(row["password_hash"], password):
            flash("bad_credentials", "error")
            return render_template("login.html", form=request.form), 401
        prev_locale = session.get("locale", "ru")
        if prev_locale not in ("kk", "ru", "en"):
            prev_locale = "ru"
        session.clear()
        session["user_id"] = row["id"]
        session["locale"] = prev_locale
        next_url = request.form.get("next") or request.args.get("next") or url_for("index")
        return redirect(next_url)
    return render_template("login.html", form={})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
def admin_panel():
    if not g.user:
        return redirect(url_for("login", next=url_for("admin_panel")))
    if not g.user["is_admin"]:
        flash("Только администратор может открыть эту страницу.", "error")
        return redirect(url_for("index"))
    stats = {
        "users": query_one("SELECT COUNT(*) AS c FROM users WHERE is_admin = 0")["c"],
        "listings": query_one("SELECT COUNT(*) AS c FROM listings")["c"],
        "msgs": query_one("SELECT COUNT(*) AS c FROM messages")["c"],
    }
    recent_messages = query_all(
        """
        SELECT m.id, m.body, m.created_at, l.id AS listing_id, l.title_ru, u.email
        FROM messages m
        JOIN listings l ON l.id = m.listing_id
        JOIN users u ON u.id = m.from_user_id
        ORDER BY m.id DESC
        LIMIT 12
        """
    )
    return render_template("admin.html", stats=stats, recent_messages=recent_messages)


def listing_filters():
    city = request.args.get("city") or ""
    rooms = request.args.get("rooms") or ""
    max_price = request.args.get("max_price") or ""
    owner_type = request.args.get("owner_type") or ""
    q = (request.args.get("q") or "").strip()
    try:
        page = max(1, int(request.args.get("page") or 1))
    except ValueError:
        page = 1
    per_page = 6

    conditions: list[str] = ["1=1"]
    params: list = []

    if city:
        conditions.append("city = ?")
        params.append(city)

    if rooms and rooms != "Любое" and rooms != "Any":
        if rooms == "3 и более":
            conditions.append("(rooms = ? OR rooms LIKE ?)")
            params.extend(["3 и более", "%3%"])
        else:
            conditions.append("rooms = ?")
            params.append(rooms)

    if max_price and max_price.isdigit():
        conditions.append("price <= ?")
        params.append(int(max_price))

    if owner_type and owner_type not in ("Все", "All", "__all__"):
        conditions.append("owner_type = ?")
        params.append(owner_type)

    if q:
        conditions.append("(city LIKE ? OR district LIKE ? OR title_ru LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where = " AND ".join(conditions)
    db = get_db()
    total = db.execute(f"SELECT COUNT(*) FROM listings WHERE {where}", params).fetchone()[0]
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    offset = (page - 1) * per_page
    listings = db.execute(
        f"SELECT * FROM listings WHERE {where} ORDER BY id ASC LIMIT ? OFFSET ?",
        (*params, per_page, offset),
    ).fetchall()

    return {
        "listings": listings,
        "total": total,
        "page": page,
        "pages": pages,
        "page_range": list(range(1, pages + 1)),
        "per_page": per_page,
        "city": city,
        "rooms": rooms,
        "max_price": max_price,
        "owner_type": owner_type,
        "q": q,
    }


@app.route("/")
def index():
    data = listing_filters()
    stats = {
        "listings": query_one("SELECT COUNT(*) AS c FROM listings")["c"],
        "users": query_one("SELECT COUNT(*) AS c FROM users WHERE is_admin = 0")["c"],
        "msgs": query_one("SELECT COUNT(*) AS c FROM messages")["c"],
    }
    hero_stats = {
        "listings": stats["listings"],
        "cities": query_one("SELECT COUNT(DISTINCT city) AS c FROM listings")["c"],
    }
    admin_stats = None
    if g.user and g.user["is_admin"]:
        admin_stats = stats
    return render_template(
        "index.html",
        **data,
        admin_stats=admin_stats,
        hero_stats=hero_stats,
    )


@app.route("/listing/<int:listing_id>", methods=("GET", "POST"))
def listing_detail(listing_id: int):
    row = query_one("SELECT * FROM listings WHERE id = ?", (listing_id,))
    if not row:
        abort(404)
    owner = query_one("SELECT id, full_name, email, phone FROM users WHERE id = ?", (row["owner_id"],))
    loc = get_locale()

    if request.method == "POST":
        if not g.user:
            flash("need_login", "error")
            return redirect(url_for("login", next=request.path))
        body = (request.form.get("body") or "").strip()
        if body:
            get_db().execute(
                "INSERT INTO messages (listing_id, from_user_id, body, created_at) VALUES (?,?,?,?)",
                (listing_id, g.user["id"], body, datetime.now(timezone.utc).isoformat()),
            )
            get_db().commit()
            flash("msg_sent", "ok")
        return redirect(url_for("listing_detail", listing_id=listing_id))

    title = listing_title(dict(row), loc)
    description = listing_description(dict(row), loc)
    util = utilities_note(dict(row), loc)
    badge_map = {"Новое": t(loc, "badge_new"), "Собственник": t(loc, "badge_owner")}
    badge = badge_map.get(row["badge"], row["badge"])

    return render_template(
        "listing_detail.html",
        listing=row,
        owner=owner,
        listing_title=title,
        listing_description=description,
        utilities_text=util,
        badge_label=badge,
    )


def _budget_from_select(val: str) -> str | None:
    """Map hero search budget label to max tenge for redirect."""
    m = {
        "до 200 000 ₸": "200000",
        "200–350 000 ₸": "350000",
        "350–550 000 ₸": "550000",
        "550 000+ ₸": "999999999",
    }
    return m.get(val)


@app.route("/search", methods=("POST",))
def search_redirect():
    """Hero form: POST → GET catalog with query params."""
    q = (request.form.get("q") or "").strip()
    rooms = request.form.get("rooms") or ""
    budget = request.form.get("budget") or ""
    max_price = _budget_from_select(budget) or ""
    params = {}
    if q:
        params["q"] = q
    if rooms:
        params["rooms"] = rooms
    if max_price:
        params["max_price"] = max_price
    qs = urlencode(params)
    path = url_for("index")
    if qs:
        path = f"{path}?{qs}"
    return redirect(f"{path}#catalog")


init_db()
seed_if_empty()
ensure_admin_user()


if __name__ == "__main__":
    import os
    import sys
    import threading
    import time

    port = int(os.environ.get("PORT", "5000"))
    url = f"http://127.0.0.1:{port}/"

    def _open_browser() -> None:
        time.sleep(2.2)
        import webbrowser

        if sys.platform == "win32":
            try:
                os.startfile(url)
                return
            except OSError:
                pass
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    # use_reloader=False — иначе два процесса и браузер часто не открывается / открывается до старта сервера
    app.run(debug=True, host="127.0.0.1", port=port, use_reloader=False, threaded=True)
