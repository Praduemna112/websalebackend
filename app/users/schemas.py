from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserUpdate(BaseModel):
    username: str


class PasswordReset(BaseModel):
    current_password: str
    new_password: str


class ForgotPassword(BaseModel):
    username: str
    admin_token: str
    new_password: str


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    is_active: bool


class AccessToken(BaseModel):
    message: str = "Login successful"