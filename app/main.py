import csv
import hashlib
import hmac
import io
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from .establecimientos import ESTABLECIMIENTOS
from .scoring import DIMENSIONES, ESCALA, PREGUNTAS, N, calcular

DATABASE_URL = os.environ.get("DATABASE_URL", "")
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "cambie-esta-clave")
STATIC = Path(__file__).parent / "static"

SCHEMA = """
CREATE TABLE IF NOT EXISTS respuestas (
  id            SERIAL PRIMARY KEY,
  fecha         TIMESTAMPTZ NOT NULL DEFAULT now(),
  dni           CHAR(8) NOT NULL UNIQUE,
  nombres       TEXT NOT NULL,
  cargo         TEXT NOT NULL,
  telefono      TEXT NOT NULL,
  correo        TEXT NOT NULL,
  diresa        TEXT NOT NULL,
  renipress     INTEGER NOT NULL,
  categoria     TEXT NOT NULL,
  establecimiento TEXT NOT NULL,
  mamografos    INTEGER NOT NULL,
  operativos    INTEGER NOT NULL,
  jefe_tel      TEXT NOT NULL,
  resp_imagenes TEXT NOT NULL,
  respuestas    SMALLINT[] NOT NULL,
  puntaje       SMALLINT NOT NULL,
  indice        NUMERIC(5,1) NOT NULL,
  nivel         TEXT NOT NULL,
  alerta_critica BOOLEAN NOT NULL DEFAULT false,
  dimensiones   JSONB NOT NULL,
  comentario    TEXT NOT NULL DEFAULT ''
);
"""


def conn():
    if not DATABASE_URL:
        raise HTTPException(500, "DATABASE_URL no configurada")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


@asynccontextmanager
async def lifespan(_):
    if DATABASE_URL:
        with conn() as c:
            c.execute(SCHEMA)
    yield


app = FastAPI(title="Evaluación de riesgo FEN – Mamógrafos", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=8 * 3600,
                   https_only=os.environ.get("RENDER") is not None, same_site="strict")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


# ---------------------------------------------------------------- público
@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "encuesta.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/config")
def config():
    return {"establecimientos": ESTABLECIMIENTOS, "dimensiones": DIMENSIONES, "escala": ESCALA}


class Envio(BaseModel):
    nom: str = Field(min_length=3, max_length=150)
    dni: str
    car: str = Field(min_length=2, max_length=120)
    tel: str
    mail: str = Field(max_length=150)
    k: int
    jt: str
    sd: str = Field(min_length=3, max_length=200)
    a: list[int]
    c: str = Field(default="", max_length=2000)


def _tel_ok(t):
    return re.fullmatch(r"\d{7,12}", re.sub(r"[\s-]", "", t)) is not None


@app.post("/api/respuestas")
def guardar(e: Envio):
    if not re.fullmatch(r"\d{8}", e.dni):
        raise HTTPException(400, "El DNI debe tener 8 dígitos.")
    if not _tel_ok(e.tel) or not _tel_ok(e.jt):
        raise HTTPException(400, "Teléfono inválido.")
    if not re.fullmatch(r"\S+@\S+\.\S+", e.mail):
        raise HTTPException(400, "Correo inválido.")
    if not 0 <= e.k < len(ESTABLECIMIENTOS):
        raise HTTPException(400, "Establecimiento inválido.")
    if len(e.a) != N:
        raise HTTPException(400, f"Debe responder las {N} preguntas.")
    try:
        r = calcular(e.a)
    except ValueError:
        raise HTTPException(400, "Respuestas inválidas.")
    d = ESTABLECIMIENTOS[e.k]
    try:
        with conn() as c:
            c.execute(
                """INSERT INTO respuestas (dni,nombres,cargo,telefono,correo,diresa,renipress,categoria,
                   establecimiento,mamografos,operativos,jefe_tel,resp_imagenes,respuestas,puntaje,indice,
                   nivel,alerta_critica,dimensiones,comentario)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (e.dni, e.nom.strip(), e.car.strip(), e.tel.strip(), e.mail.strip(), d[0], d[2], d[3], d[4],
                 d[5], d[6], e.jt.strip(), e.sd.strip(), e.a, r["puntaje"], r["indice"], r["nivel"],
                 r["alerta_critica"], json.dumps(r["dimensiones"], ensure_ascii=False), e.c.strip()))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Este DNI ya registró una respuesta.")
    return {**r, "establecimiento": d[4]}


# ---------------------------------------------------------------- admin
_intentos: dict[str, list[float]] = {}


def _bloqueado(ip):
    ahora = time.time()
    _intentos[ip] = [t for t in _intentos.get(ip, []) if ahora - t < 900]
    return len(_intentos[ip]) >= 5


def _check(u, p):
    if not ADMIN_PASSWORD:
        return False
    h = lambda s: hashlib.sha256(s.encode()).digest()
    return hmac.compare_digest(h(u), h(ADMIN_USER)) & hmac.compare_digest(h(p), h(ADMIN_PASSWORD))


def _admin(request: Request):
    if not request.session.get("admin"):
        raise HTTPException(401, "No autorizado")


@app.get("/admin", include_in_schema=False)
def admin_page(request: Request):
    if not request.session.get("admin"):
        return FileResponse(STATIC / "login.html")
    return FileResponse(STATIC / "admin.html")


@app.post("/admin/login", include_in_schema=False)
def login(request: Request, usuario: str = Form(...), clave: str = Form(...)):
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
    if _bloqueado(ip):
        return RedirectResponse("/admin?e=bloqueado", 303)
    if not _check(usuario, clave):
        _intentos[ip].append(time.time())
        return RedirectResponse("/admin?e=1", 303)
    _intentos.pop(ip, None)
    request.session.clear()
    request.session["admin"] = usuario
    return RedirectResponse("/admin", 303)


@app.post("/admin/logout", include_in_schema=False)
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/admin", 303)


@app.get("/api/admin/respuestas")
def listar(request: Request):
    _admin(request)
    with conn() as c:
        rows = c.execute("SELECT * FROM respuestas ORDER BY fecha DESC").fetchall()
    for r in rows:
        r["fecha"] = r["fecha"].isoformat()
        r["indice"] = float(r["indice"])
    return JSONResponse({"preguntas": PREGUNTAS, "dimensiones": [d[0] for d in DIMENSIONES], "rows": rows})


@app.get("/admin/export.csv", include_in_schema=False)
def exportar(request: Request):
    _admin(request)
    with conn() as c:
        rows = c.execute("SELECT * FROM respuestas ORDER BY fecha").fetchall()
    dims = [d[0] for d in DIMENSIONES]
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(["fecha", "dni", "nombres", "cargo", "telefono", "correo", "diresa", "renipress", "categoria",
                "establecimiento", "mamografos", "operativos", "jefe_tel", "resp_imagenes",
                *[f"p{i+1}" for i in range(N)], "puntaje", "indice", "nivel", "alerta_critica",
                *[f"dim_{d}" for d in dims], "comentario"])
    for r in rows:
        w.writerow([r["fecha"].isoformat(), r["dni"], r["nombres"], r["cargo"], r["telefono"], r["correo"],
                    r["diresa"], r["renipress"], r["categoria"], r["establecimiento"], r["mamografos"],
                    r["operativos"], r["jefe_tel"], r["resp_imagenes"], *r["respuestas"], r["puntaje"],
                    r["indice"], r["nivel"], "SI" if r["alerta_critica"] else "NO",
                    *[r["dimensiones"].get(d) for d in dims], r["comentario"]])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=encuesta_fen_mamografos.csv"})


@app.delete("/api/admin/respuestas/{rid}")
def eliminar(rid: int, request: Request):
    _admin(request)
    with conn() as c:
        c.execute("DELETE FROM respuestas WHERE id=%s", (rid,))
    return {"ok": True}
