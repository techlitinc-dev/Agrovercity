from pydantic import BaseModel


class FirebaseVerifyRequest(BaseModel):
    idToken: str


class TokenPair(BaseModel):
    accessToken: str
    refreshToken: str
    tokenType: str = "bearer"


class AuthResponse(BaseModel):
    accessToken: str
    refreshToken: str
    isNewUser: bool
    user: dict


class RefreshRequest(BaseModel):
    refreshToken: str


class MpinSetRequest(BaseModel):
    mpin: str


class MpinVerifyRequest(BaseModel):
    mpin: str


class MpinResetRequest(BaseModel):
    idToken: str
    newMpin: str


class OkResponse(BaseModel):
    ok: bool = True
