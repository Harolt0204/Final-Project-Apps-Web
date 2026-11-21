# Thesis Management

Plataforma web con roles para gestionar de punta a punta el proceso de tesis y titulación
de pregrado de Yachay Tech: desde el registro del tema hasta la nota de la defensa.

Proyecto final de Aplicaciones Web — Fernando Chantera, Harolt Farinango, Mateo Pilaquinga.

| Capa | Tecnología |
| :--- | :--- |
| API | FastAPI · SQLAlchemy 2 · Alembic · JWT (PyJWT) · bcrypt |
| Base de datos | MySQL 8 (Docker Compose en desarrollo) |
| Frontend | React + Vite + TypeScript (SPA) · React Router |
| Calidad | pytest · Ruff · GitHub Actions |

Documentación:
- `documentation.md`: análisis del sistema heredado y decisiones DEC-01…DEC-12. Es un documento
  interno del equipo y no se publica en el repositorio; los comentarios del código que citan
  sus secciones (§3.1, §8.1, hallazgos, I-1…I-12, D-1…D-12) se refieren a él.
- [`docs/decisions.md`](docs/decisions.md): decisiones tomadas en este proyecto (DEC-13 en adelante).

## Estructura

```
backend/
  app/
    api/routes/     endpoints (auth, users, theses, review, compliance, defense, reports,
                    people, catalog, health)
    core/           configuración y seguridad (JWT, contraseñas)
    models/         modelos ORM (estado actual del esquema)
    schemas/        modelos Pydantic de entrada y salida
    services/       reglas de negocio y autorización por tesis
  alembic/versions/ 0001 esquema heredado · 0002 correcciones · 0003 usuarios y auditoría
                    · 0004 catálogo de escuelas · 0005 observaciones del comité
                    · 0006 historial de similitud y ajustes · 0007 requisitos administrativos
                    · 0008 aulas y horario de defensas · 0009 revocación de tokens
  scripts/seed.py   datos de demostración
  scripts/verify_db_rules.py   comprueba las reglas de la BD en MySQL
  scripts/create_admin.py      primer administrador en producción
  tests/
frontend/src/       SPA (login, layout tipo MiYT, páginas; diseño responsivo)
docker-compose.yml       MySQL 8 para desarrollo
docker-compose.prod.yml  MySQL + app (imagen de producción)
Dockerfile               imagen única: frontend compilado + API
```

## Puesta en marcha (Windows, PowerShell)

Requisitos: Python 3.12+, Node 20+, Docker Desktop.

```powershell
# 1. Variables de entorno (una sola vez). Cambia JWT_SECRET por un valor aleatorio.
Copy-Item .env.example .env

# 2. Base de datos
docker compose up -d db

# 3. Backend
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

- Aplicación: <http://localhost:5173>
- Documentación interactiva de la API (Swagger): <http://127.0.0.1:8000/docs>
- `GET /health` comprueba también la conexión con MySQL.

### Cuentas de demostración

`scripts/seed.py` crea un administrador (usuario `admin`), 5 profesores y
7 estudiantes ficticios. Se inicia sesión con el usuario `nombre.apellido` (sin
`@yachaytech.edu.ec`). Todos usan la contraseña `DEV_PASSWORD` definida en ese archivo.
**Solo para desarrollo local.** Las asignaciones reproducen el ejemplo de la propuesta
(diapositiva 9): por ejemplo, Andrea Benítez es tutora de la tesis 1 y presidenta del
tribunal de la tesis 2, y Lucía Paredes es miembro del comité de la tesis 1 y co-tutora de
la tesis 3. Camila Ortiz todavía no tiene tesis.

### Reiniciar la base de datos

```powershell
cd backend
.\.venv\Scripts\alembic.exe downgrade base
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m scripts.seed
```

## Pruebas y calidad

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\ruff.exe format --check .
cd ..\frontend
npm run build      # incluye la verificación de tipos de TypeScript
```

Los tests usan SQLite en memoria, así que no necesitan Docker. Las reglas que solo
existen en MySQL (trigger, CHECK, FK compuesta) se comprueban contra la base real con:

```powershell
.\.venv\Scripts\python.exe -m scripts.verify_db_rules
```

 El pipeline de CI
(`.github/workflows/ci.yml`) además aplica todas las migraciones sobre un MySQL 8 real,
carga los datos de demostración y revierte las migraciones.

## Producción

La imagen de producción compila el frontend y lo sirve desde la propia API, así que
todo funciona como un solo servicio y un solo origen. Al arrancar aplica las migraciones.

```powershell
# En .env: MYSQL_ROOT_PASSWORD, MYSQL_PASSWORD y un JWT_SECRET aleatorio (>= 32 caracteres)
docker compose -f docker-compose.prod.yml up -d --build
# Primer administrador (la contraseña se pide de forma interactiva):
docker compose -f docker-compose.prod.yml exec app python -m scripts.create_admin --username coordinacion
```

La aplicación queda en <http://localhost:8080>. En un servidor real debe ir detrás de
HTTPS (la app envía HSTS en producción). Para una plataforma de contenedores basta con
la imagen del `Dockerfile` y estas variables: `ENVIRONMENT=production`, `DATABASE_URL`
(MySQL 8), `JWT_SECRET`, y `PORT` si la plataforma lo asigna. El usuario de MySQL debe
poder crear triggers (`log_bin_trust_function_creators=1` o privilegio equivalente).

## Diseño responsivo

La aplicación se adapta a celulares y tablets. La vista de escritorio no cambia: los estilos
para pantallas pequeñas están en una sección aparte al final de `frontend/src/styles.css`
(comentario `phones`).

| Ancho de pantalla | Qué cambia |
| :--- | :--- |
| ≤ 1000 px (tablets) | Menos espacio entre pestañas para que quepan las 9 del administrador |
| ≤ 760 px (celulares) | Botón **Menu** con las pestañas (cuando hay más de 3), submenús en una línea que se desliza de lado, barra de progreso compacta, campos de texto a 16 px (evita el zoom de iPhone) |
| ≤ 640 px | Las tablas se muestran como tarjetas con etiquetas ("Student: Daniela Torres") |

Archivos involucrados:

- `frontend/src/styles.css`: todos los estilos para pantallas pequeñas.
- `frontend/src/components/Layout.tsx`: botón **Menu** y desplazamiento del submenú hasta la opción activa.
- `frontend/src/components/useTableLabels.ts`: copia el encabezado de cada columna a sus
  celdas (`data-label`), que el CSS usa para las tarjetas.

### Reglas para páginas nuevas

- **Tablas:** usar `<div className="table-wrap"><table className="grid">` con encabezados
  en `<thead><th>`. En celular se convierten solas en tarjetas, sin código extra.
  - Una columna sin título (por ejemplo, la de botones) ocupa todo el ancho de la tarjeta.
  - Las tablas que deben conservar sus columnas (reportes, datos numéricos) llevan la clase
    `compact` y en celular se deslizan de lado.
- **Estilos para celular:** agregarlos dentro de los bloques `@media (max-width: 760px)`
  o `@media (max-width: 640px)` del final de `styles.css`, no en medio del archivo.
- **Anchos:** no usar anchos fijos en píxeles para contenedores; preferir `%`, `minmax()`
  o `flex`.
- **Botones:** mantener una altura mínima de unos 40 px para que se puedan tocar con el dedo.

### Cómo probarlo

- **En la computadora:** abrir las herramientas de desarrollador del navegador (F12) y
  activar la vista de dispositivo (Ctrl+Shift+M). Revisar al menos 360 px, 390 px y 768 px
  de ancho.
- **En un celular real** (conectado al mismo WiFi):

  ```powershell
  cd frontend
  npm run dev -- --host
  ```

  Abrir en el celular la dirección **Network** que muestra la terminal (por ejemplo
  `http://192.168.1.20:5173`) y permitir el acceso si el Firewall de Windows lo pide.

## Seguridad

- Contraseñas con bcrypt (12–72 caracteres); JWT de 60 minutos.
- 5 intentos fallidos de login por correo e IP en 15 minutos → HTTP 429.
- Cambiar o restablecer la contraseña revoca los tokens anteriores; una cuenta
  desactivada pierde el acceso al instante.
- Autorización por objeto: quien no participa en una tesis recibe 404.
- Cabeceras CSP, HSTS (producción), `X-Frame-Options`, `nosniff`, `Referrer-Policy`.
- Los errores no exponen detalles internos; en producción la app no arranca con un
  `JWT_SECRET` débil.

## Modelo de acceso

- Roles globales: `admin`, `professor`, `student`.
- Tutor, co-tutor, presidente y miembro del comité **no son roles**: se derivan de las
  asignaciones de cada tesis. Un profesor solo ve las tesis en las que participa, y un
  estudiante solo la suya. Si un usuario no participa en una tesis, la API responde 404.

## Reglas que garantiza la base de datos

| Regla | Mecanismo |
| :--- | :--- |
| 1 tutor y como máximo 1 co-tutor, que deben ser personas distintas | PK `(thesis_id, role)` + `UNIQUE (thesis_id, professor_id)` |
| Máximo 3 revisores | Trigger `trg_reviewer_assignments_max3` |
| Exactamente 1 presidente por tesis | `UNIQUE` sobre una columna generada |
| Notas entre 0 y 10, similitud entre 0 y 100 % | `CHECK` |
| Cada cuenta vinculada a la persona que corresponde a su rol | `CHECK ck_users_link` |
| Historial de cambios de estado | Tabla `thesis_status_history` |
| Un estudiante, una tesis | `UNIQUE (theses.student_id)` |
| Escuela válida para estudiantes y profesores | FK a `schools` |
| Solo un revisor de la tesis puede escribir observaciones | FK compuesta a `reviewer_assignments` |
| Una observación respondida tiene respuesta; una resuelta, fecha | `CHECK` |
| El dictamen de similitud coincide con el porcentaje y el umbral | `CHECK` |
| Un requisito rechazado tiene una nota | `CHECK` |
| Defensa presencial con aula y sin enlace; virtual con enlace y sin aula | `CHECK` |

Otras reglas viven en la capa de servicio (`app/services/`): el tutor no puede revisar su
propia tesis, no hay co-tutor sin tutor, y una tesis cerrada no cambia de tutores.

## Flujo de la tesis

```
PROPOSED ─► TOPIC_APPROVED ─► THESIS_I ─► THESIS_II ─► IN_REVIEW ─► READY_FOR_DEFENSE ─► DEFENDED
   │                                          ▲            │                         (3.ª nota del tribunal)
   └─► REJECTED                               └────────────┘ devuelta para cambios
```

El paso a `READY_FOR_DEFENSE` es la validación previa a la defensa: comité completo,
manuscrito aprobado por los 3 revisores, observaciones resueltas, último análisis de
similitud aceptado y todos los requisitos administrativos certificados.

Con la tesis lista, coordinación programa la defensa: la API rechaza la fecha si el aula
o algún miembro del tribunal tiene otra defensa a esa hora. Cuando el tercer miembro
registra su nota, la tesis queda `DEFENDED` con el promedio como nota final.

Cada paso indica quién puede darlo (coordinación o el tutor) y qué requisitos deben
cumplirse; el detalle de la tesis muestra a todos los participantes lo que falta.
Cada cambio queda en `thesis_status_history` con autor, fecha y comentario.

## Plan de sprints

| Sprint | Incremento | Estado |
| :--- | :--- | :--- |
| 0 | Estructura del repositorio, entorno, CI y migración base del esquema heredado | ✅ |
| 1 | Correcciones del esquema; autenticación, usuarios y roles | ✅ |
| 2 | Estudiantes, profesores y periodos; registro de tesis; asignación de tutores | ✅ |
| 3 | Flujo de estados con historial; comité revisor y observaciones | ✅ |
| 4 | Similitud y requisitos administrativos; validación previa a la defensa | ✅ |
| 5 | Aulas y agenda de defensas con detección de choques; notas del tribunal | ✅ |
| 6 | Reportes; hardening, pruebas y empaquetado para producción | ✅ (falta publicar en un servidor) |
