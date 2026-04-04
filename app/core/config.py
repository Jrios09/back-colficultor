from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    MONGODB_URI: str = "mongodb://localhost:27017"
    DB_NAME: str = "colficultor"
    JWT_SECRET_KEY: str = "change_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5500", "http://localhost:5500"]  # React/Vite/LiveServer
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    MAIL_FROM: str = ""
    FRONTEND_URL: str = "http://localhost:5500"
    FORGOT_PASSWORD_RATE_LIMIT: int = 5
    FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS: int = 300
    AUTH_LOGIN_RATE_LIMIT: int = 5
    AUTH_LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300
    AUTH_REGISTER_RATE_LIMIT: int = 3
    AUTH_REGISTER_RATE_LIMIT_WINDOW_SECONDS: int = 600
    AUTH_RESET_VALIDATE_RATE_LIMIT: int = 10
    AUTH_RESET_VALIDATE_RATE_LIMIT_WINDOW_SECONDS: int = 300
    AUTH_RESET_PASSWORD_RATE_LIMIT: int = 5
    AUTH_RESET_PASSWORD_RATE_LIMIT_WINDOW_SECONDS: int = 600
    AUTH_FORGOT_PASSWORD_RATE_LIMIT: int = 5
    AUTH_FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS: int = 300
    RECAPTCHA_SECRET_KEY: str = ""
    RECAPTCHA_VERIFY_URL: str = "https://www.google.com/recaptcha/api/siteverify"
    RECAPTCHA_SCORE_THRESHOLD: float = 0.5

    # ── Google OAuth 2.0 ───────────────────────────────────────────────
    # Reemplaza estos valores en tu archivo .env
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    # URL a la que Google redirigirá tras la autenticación (debe registrarse
    # en Google Cloud Console > Credenciales > URIs de redireccionamiento)
    GOOGLE_CALLBACK_URL: str = "http://localhost:8000/api/auth/google/callback"

    class Config:
        env_file = ".env"

settings = Settings()
