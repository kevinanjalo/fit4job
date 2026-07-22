"""Authentication endpoints: register, login, current user."""
from fastapi import APIRouter, Depends, HTTPException, Response
from app.core import audit, firebase
from app.core.security import create_access_token, get_current_user
from app.models.schemas import GoogleAuthRequest, TokenResponse, UserLogin, UserRegister
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: UserRegister, response: Response):
    try:
        user = user_service.register(payload.name, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = create_access_token(user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    audit.record(user["email"], "register")
    return TokenResponse(access_token=token, role=user["role"], name=user["name"])


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, response: Response):
    user = user_service.authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    audit.record(user["email"], "login")
    return TokenResponse(access_token=token, role=user["role"], name=user["name"])


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleAuthRequest, response: Response):
    if firebase.get_db() is None:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server")
    try:
        from firebase_admin import auth as firebase_auth
        decoded = firebase_auth.verify_id_token(payload.id_token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired Google sign-in token")
    email = decoded.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email on file")
    name = decoded.get("name") or email.split("@")[0]
    user = user_service.find_or_create_google_user(name, email)
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    token = create_access_token(user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    audit.record(user["email"], "google_login")
    return TokenResponse(access_token=token, role=user["role"], name=user["name"])


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"detail": "Logged out"}


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"email": user["sub"], "role": user["role"]}
