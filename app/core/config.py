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
    BASE_URL_BACKEND: str = "http://localhost:8000"
    APP_ENV: str = "dev"
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
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    PRODUCT_IMAGE_MAX_SIZE_BYTES: int = 5 * 1024 * 1024
    PRODUCT_IMAGE_MAX_FILES_PER_PRODUCT: int = 8
    PAYMENT_PROVIDER: str = "mock"
    PAYMENT_SECRET: str = ""
    WEBHOOK_SECRET: str = ""
    PAYMENT_PUBLIC_KEY: str = ""
    PAYU_MERCHANT_ID: str = ""
    PAYU_API_LOGIN: str = ""
    PAYU_API_KEY: str = ""
    PAYU_ACCOUNT_ID: str = ""
    PAYU_COUNTRY: str = "CO"
    PAYU_CURRENCY: str = "COP"
    PAYU_SANDBOX: bool = True
    PAYU_SIGNATURE_ALGORITHM: str = "MD5"

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
