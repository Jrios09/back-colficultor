# Back Colficultor

Backend de **Colficultor** construido con FastAPI, arquitectura por capas y MongoDB asíncrono. Expone la API REST para autenticación, catálogo, operaciones de compra/venta, pagos, notificaciones, PQR y reportes.

## Tabla de contenido

- [Stack backend](#stack-backend)
- [Requisitos previos](#requisitos-previos)
- [Instalación](#instalación)
- [Variables de entorno](#variables-de-entorno)
- [Ejecución](#ejecución)
- [Comandos útiles](#comandos-útiles)
- [Estructura de carpetas](#estructura-de-carpetas)
- [Arquitectura interna](#arquitectura-interna)
- [Base de datos](#base-de-datos)
- [Autenticación y autorización](#autenticación-y-autorización)
- [Seguridad implementada](#seguridad-implementada)
- [Documentación de API](#documentación-de-api)
- [Módulos de endpoints](#módulos-de-endpoints)
- [Datos de prueba (seed)](#datos-de-prueba-seed)
- [Tests](#tests)
- [Despliegue](#despliegue)
- [Errores comunes](#errores-comunes)
- [Estado del módulo](#estado-del-módulo)

## Stack backend

Tecnologías detectadas en `requirements.txt` y código:

- Python
- FastAPI + Starlette
- Uvicorn
- MongoDB (Motor/PyMongo)
- Pydantic v2 + pydantic-settings
- JWT con `python-jose`
- Hash de contraseñas con `bcrypt`
- `httpx` para integraciones HTTP (reCAPTCHA/Google OAuth)
- Cloudinary SDK (gestión de imágenes)
- SMTP nativo (`smtplib`) para correos
- ReportLab/OpenPyXL para exportaciones PDF/CSV

## Requisitos previos

- Python 3.10+
- MongoDB accesible desde `MONGODB_URI`
- Entorno virtual recomendado (`venv`)
- Credenciales externas según funcionalidades activadas:
  - SMTP
  - Google OAuth
  - reCAPTCHA v3
  - Cloudinary
  - PayU (si `PAYMENT_PROVIDER=payu`)

## Instalación

```bash
cd back-colficultor
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Variables de entorno

Fuente oficial en el repositorio: `.env.example`.

```bash
cp .env.example .env
```

### Variables detectadas

| Grupo | Variables |
|---|---|
| Base de datos | `MONGODB_URI`, `DB_NAME` |
| JWT/sesión | `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `RESET_TOKEN_EXPIRE_MINUTES` |
| CORS/URLs | `BACKEND_CORS_ORIGINS`, `FRONTEND_URL`, `BASE_URL_BACKEND` |
| Correo | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` |
| Rate limiting auth/recovery | `FORGOT_PASSWORD_RATE_LIMIT`, `FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS`, `AUTH_LOGIN_RATE_LIMIT`, `AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS`, `AUTH_REGISTER_RATE_LIMIT`, `AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS`, `AUTH_RESET_VALIDATE_RATE_LIMIT`, `AUTH_RESET_VALIDATE_RATE_LIMIT_WINDOW_SECONDS`, `AUTH_RESET_PASSWORD_RATE_LIMIT`, `AUTH_RESET_PASSWORD_RATE_LIMIT_WINDOW_SECONDS`, `AUTH_FORGOT_PASSWORD_RATE_LIMIT`, `AUTH_FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS` |
| reCAPTCHA | `RECAPTCHA_SECRET_KEY`, `RECAPTCHA_ENABLED`, `RECAPTCHA_VERIFY_URL`, `RECAPTCHA_SCORE_THRESHOLD` |
| Google OAuth | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_CALLBACK_URL` |
| Cloudinary | `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET`, `PRODUCT_IMAGE_MAX_SIZE_BYTES`, `PRODUCT_IMAGE_MAX_FILES_PER_PRODUCT` |
| Pagos generales | `PAYMENT_PROVIDER`, `APP_ENV`, `WEBHOOK_SECRET`, `PAYMENT_SECRET`, `PAYMENT_PUBLIC_KEY` |
| PayU | `PAYU_MERCHANT_ID`, `PAYU_API_LOGIN`, `PAYU_API_KEY`, `PAYU_ACCOUNT_ID`, `PAYU_COUNTRY`, `PAYU_CURRENCY`, `PAYU_SANDBOX`, `PAYU_SIGNATURE_ALGORITHM` |

## Ejecución

### Desarrollo

```bash
cd back-colficultor
source .venv/bin/activate
python run.py
```

`run.py` ejecuta:

```python
uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
```

### Alternativa directa con Uvicorn

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Comandos útiles

```bash
# Instalar dependencias
pip install -r requirements.txt

# Levantar API en local
python run.py

# Verificar rutas de documentación
# Swagger: http://localhost:8000/docs
# ReDoc:   http://localhost:8000/redoc
```

## Estructura de carpetas

```text
back-colficultor/
├── app/
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   ├── core/
│   ├── db/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   └── services/
├── requirements.txt
├── run.py
└── .env.example
```

## Arquitectura interna

- `app/main.py`
  - Crea la app FastAPI.
  - Configura CORS.
  - Registra routers.
  - Ejecuta startup: validadores de colecciones, índices y seed de usuarios demo.
- `app/api/routes/*`
  - Capa HTTP: validación de entrada/salida y control de acceso por endpoint.
- `app/api/deps.py`
  - Dependencias transversales (`get_current_user`, `require_role`).
- `app/services/*`
  - Lógica de negocio (pagos, órdenes, PQR, reseñas, reportes, notificaciones, recuperación de contraseña, etc.).
- `app/repositories/*`
  - Persistencia por dominio en MongoDB.
- `app/models/*`
  - Operaciones de entidades principales (usuarios, productos).
- `app/schemas/*`
  - Contratos Pydantic y enums de dominio.
- `app/db/*`
  - Conexión Mongo, validadores de colección, índices y seed.

## Base de datos

- Motor async (`AsyncIOMotorClient`) con `MONGODB_URI` y `DB_NAME`.
- En startup se aplican:
  - Validadores `$jsonSchema` para colecciones.
  - Índices (incluidos únicos y TTL).
- Colecciones relevantes detectadas:
  - `users`, `password_resets`, `revoked_tokens`
  - `productos`, `carritos`, `ordenes`, `transacciones`
  - `resenas`, `pqr_tickets`, `notifications`
  - `oauth_states`, `google_pending`

## Autenticación y autorización

- Login local: `/api/auth/login` (OAuth2 password form).
- JWT con claims `sub`, `role`, `exp`, `jti`.
- Logout con revocación de token (`revoked_tokens`).
- OAuth Google:
  - `/api/auth/google/init`
  - `/api/auth/google/callback`
  - `/api/auth/google/complete`
- RBAC por roles `comprador`, `caficultor`, `admin`.

## Seguridad implementada

| Control | Estado | Evidencia |
|---|---|---|
| JWT | Implementado | `app/core/auth.py` |
| Hash de contraseñas | Implementado (`bcrypt`) | `app/core/security.py` |
| Revocación de token | Implementado (JTI + colección) | `revoke_token`, `is_token_revoked` |
| Rate limiting | Implementado (in-memory) | `app/core/rate_limit.py`, `auth.py` |
| CORS | Implementado | `app/main.py` |
| reCAPTCHA v3 | Implementado | `auth.py`, `recaptcha_service.py` |
| Recuperación de contraseña | Implementado | `password_recovery_service.py` |
| RBAC | Implementado | `require_role(...)` |

No se detecta un rate limiter distribuido (ej. Redis) en el código actual.

## Documentación de API

Con la API en ejecución:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## Módulos de endpoints

### Autenticación
- Prefijo: `/api/auth`
- Registro, login, logout, forgot password, validate reset token, reset password.

### Google OAuth
- Prefijo: `/api/auth/google`
- Init, callback, complete registration.

### Usuarios
- Prefijo: `/api/users`
- Perfil propio (`GET/PATCH /me`), gestión admin de usuarios/roles/eliminación.

### Productos y catálogo
- Prefijos: `/api/productos`, `/api/products`
- CRUD de productos (caficultor/admin), catálogo público con filtros, gestión de imágenes.

### Carrito
- Prefijo: `/api/carrito`
- Consultar carrito, agregar ítems, actualizar cantidad, eliminar ítems.

### Órdenes
- Prefijo: `/api/ordenes`
- Crear orden, listar órdenes del comprador, ventas del caficultor, detalle, cambio de estado, eliminación de pendiente de pago.

### Pagos
- Prefijo: `/api/pagos`
- Crear intento de pago, webhook, confirmación por redirección PayU, endpoint mock de eventos.

### Reseñas
- Prefijo base: `/api`
- Crear reseña, listar reseñas por producto, reseñas propias, respuesta de caficultor.

### PQR
- Prefijo: `/api/pqr`
- Crear ticket, listar propios, listar global (admin), detalle, cambio de estado, respuesta/mensajería.

### Notificaciones
- Prefijo: `/api/notificaciones`
- Listar, marcar una como leída, marcar todas.

### Reportes
- Prefijo: `/api/reportes`
- Exportación CSV/PDF para admin y reportes de ventas para caficultor.

## Datos de prueba (seed)

`app/db/seed_users.py` crea automáticamente (si no existen):

- `admin@colficultor.com` / `Admin123!`
- `caficultor@colficultor.com` / `Cafe123!`
- `comprador@colficultor.com` / `Compra123!`

## Despliegue

- No se detectan `Dockerfile`, `docker-compose.yml` ni workflows CI/CD en este repositorio.
- Sí hay referencias a Render en configuración/URLs del sistema.

## Errores comunes

- `401 Token inválido o expirado`: token ausente/expirado o revocado.
- `403 Verificación de seguridad fallida`: token reCAPTCHA inválido o score bajo.
- `500 WEBHOOK_SECRET no está configurado`: faltan variables de pagos.
- `500 Configuración incompleta de Cloudinary`: credenciales Cloudinary faltantes.
- `400 token de recuperación inválido/expirado`: flujo de reset ya consumido o vencido.
- `409 Transición inválida de orden`: cambio de estado no permitido por rol/estado actual.

## Estado del módulo

**Operativo y funcionalmente amplio** para escenarios de e-commerce en contexto académico/producto inicial.
