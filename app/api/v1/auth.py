"""Authentication endpoints: register, login, current user."""
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from app.core import audit
from app.core.logging import get_logger
from app.core.security import create_access_token, get_current_user
from app.models.schemas import OrgRegister, TokenResponse, UserLogin, UserRegister
from app.services import user_service

logger = get_logger(__name__)

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


@router.post("/register-organization", response_model=TokenResponse)
def register_organization(payload: OrgRegister, response: Response):
    try:
        org = user_service.register_organization(
            payload.organization_name, payload.email, payload.password,
            payload.website, payload.location, payload.about)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    token = create_access_token(org["email"], org["role"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    audit.record(org["email"], "register.organization")
    return TokenResponse(access_token=token, role=org["role"], name=org["name"])


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, response: Response):
    user = user_service.authenticate(payload.email, payload.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    audit.record(user["email"], "login")
    return TokenResponse(access_token=token, role=user["role"], name=user["name"])


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"detail": "Logged out"}


class GoogleSignIn(BaseModel):
    id_token: str


@router.post("/google", response_model=TokenResponse)
def google_sign_in(payload: GoogleSignIn, response: Response):
    """Verify a Firebase Google sign-in ID token and issue a Fit4Job session.

    The frontend authenticates the user with Google through the Firebase
    Web SDK, then sends the resulting ID token here. We verify it server
    side with the Firebase Admin SDK (never trusting the client), then
    create or reuse the matching Fit4Job account.
    """
    try:
        import firebase_admin
        from firebase_admin import auth as firebase_auth
        if not firebase_admin._apps:
            raise RuntimeError("Firebase Admin SDK is not initialised")
        decoded = firebase_auth.verify_id_token(payload.id_token)
    except Exception as exc:
        logger.warning("Google sign-in verification failed: %s", exc)
        raise HTTPException(status_code=401,
                            detail="Could not verify Google sign-in. Check that Firebase "
                                   "Authentication is configured (see setup.md).")

    email = decoded.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email address")
    name = decoded.get("name") or email.split("@")[0]

    user = user_service.get_or_create_google_user(email, name)
    if not user.get("active", True):
        raise HTTPException(status_code=403, detail="This account has been deactivated")
    token = create_access_token(user["email"], user["role"])
    response.set_cookie("access_token", token, httponly=True, samesite="lax")
    audit.record(user["email"], "login.google")
    return TokenResponse(access_token=token, role=user["role"], name=user["name"])


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"email": user["sub"], "role": user["role"]}
