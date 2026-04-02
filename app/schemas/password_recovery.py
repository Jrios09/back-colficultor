from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class GenericMessageResponse(BaseModel):
    message: str


class ResetPasswordValidateResponse(BaseModel):
    valid: bool
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=20, max_length=512)
    newPassword: str = Field(..., alias="newPassword", min_length=8, max_length=128)
    confirmPassword: str = Field(..., alias="confirmPassword", min_length=8, max_length=128)

    model_config = {"populate_by_name": True}

    @field_validator("newPassword")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_upper = any(char.isupper() for char in value)
        has_lower = any(char.islower() for char in value)
        has_digit = any(char.isdigit() for char in value)
        has_special = any(not char.isalnum() for char in value)

        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError(
                "La contraseña debe incluir mayúscula, minúscula, número y símbolo"
            )
        return value

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.newPassword != self.confirmPassword:
            raise ValueError("Las contraseñas no coinciden")
        return self


class ResetPasswordResponse(BaseModel):
    message: str
