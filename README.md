# riesgo_fen – Evaluación de riesgo frente al FEN – Mamógrafos (DPCAN)

FastAPI + PostgreSQL (Neon) · despliegue en Render.

## Rutas
| Ruta | Uso |
|---|---|
| `/` | Encuesta pública |
| `/admin` | Login y panel de resultados (solo administrador) |
| `/admin/export.csv` | Exportación (requiere sesión) |
| `/healthz` | Health check de Render |

## Modelo de medición
Escala por criterio: **0 = No**, **1 = Parcial**, **2 = Sí** (13 criterios, máx. 26 puntos).
Índice de riesgo = puntaje / 26 × 100 → **Bajo** 0–33 · **Moderado** 34–66 · **Alto** 67–100.
**Alerta crítica**: si los criterios 4, 5, 7 o 12 (inundación del área, daño del mamógrafo,
electricidad, equipos de respaldo) valen 2, el nivel sube como mínimo a Moderado.
También se reporta un % por cada una de las 4 dimensiones. Todo se calcula en el servidor (`app/scoring.py`).

## 1. Base de datos en Neon
1. Crear proyecto en https://neon.tech (región **AWS São Paulo** o la más cercana).
2. Copiar la *connection string* (pooled), p. ej.
   `postgresql://usuario:clave@ep-xxx-pooler.sa-east-1.aws.neon.tech/neondb?sslmode=require`
3. La tabla `respuestas` se crea sola al primer arranque.

## 2. Servicio en Render
1. Subir esta carpeta a un repositorio de GitHub.
2. Render → **New → Blueprint** → elegir el repo (usa `render.yaml`).
3. Completar las variables:
   - `DATABASE_URL` → la cadena de Neon
   - `ADMIN_PASSWORD` → contraseña robusta (12+ caracteres)
   - `ADMIN_USER` viene como `admin.dpcan` (puede cambiarlo)
   - `SECRET_KEY` se genera automáticamente
4. Deploy. La encuesta queda en `https://fen-mamografos.onrender.com/`.

> Plan free de Render: el servicio "duerme" tras 15 min sin uso y tarda ~50 s en despertar.
> Para la campaña de recojo conviene el plan Starter.

## Local
```bash
pip install -r requirements.txt
set DATABASE_URL=postgresql://...      # PowerShell: $env:DATABASE_URL="..."
set ADMIN_PASSWORD=MiClave
uvicorn app.main:app --reload
```
