from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr
from services.auth import (
    hash_password, verify_password, create_token,
    create_session_token, SECRET_KEY, ALGORITHM
)
from services.user_storage import (
    get_user, user_exists, create_user,
    get_session, create_session, delete_session
)
from datetime import datetime
from jose import jwt

router = APIRouter()

ALLOWED_DOMAIN = "@climatehub.in"


# -------------------------
# MODELS
# -------------------------
class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


# -------------------------
# REGISTER
# -------------------------
@router.post("/register")
def register(user: UserRegister):
    if not user.email.lower().endswith(ALLOWED_DOMAIN):
        raise HTTPException(
            status_code=403,
            detail=f"Only {ALLOWED_DOMAIN} emails are allowed to register"
        )

    if user_exists(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    success = create_user(user.email, {
        "password": hash_password(user.password),
        "full_name": user.full_name,
        "auth_provider": "password",
        "created_at": str(datetime.now())
    })

    if not success:
        raise HTTPException(status_code=500, detail="Failed to register user")

    return {"message": "User registered successfully"}


# -------------------------
# LOGIN
# -------------------------
@router.post("/login")
def login(user: UserLogin):
    db_user = get_user(user.email)

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not db_user.get("password") or not verify_password(user.password, db_user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token({"email": user.email})
    session_token = create_session_token({"email": user.email})

    create_session(session_token, user.email)

    return {
        "token": token,
        "session_token": session_token,
        "user": {
            "email": user.email,
            "full_name": db_user.get("full_name")
        }
    }


# -------------------------
# LOGOUT
# -------------------------
@router.post("/logout")
def logout(session_token: str):
    email = get_session(session_token)

    if not email:
        raise HTTPException(status_code=401, detail="Invalid session")

    delete_session(session_token)

    return {"message": "Logged out successfully"}


# -------------------------
# GET CURRENT USER
# -------------------------
@router.get("/me")
def get_current_user(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("email")

        db_user = get_user(email)

        if not db_user:
            raise HTTPException(status_code=401, detail="User not found")

        return {
            "email": email,
            "full_name": db_user.get("full_name")
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


# -------------------------
# GOOGLE AUTH
# -------------------------
class GoogleUserRequest(BaseModel):
    email: str
    displayName: str
    uid: str
    emailVerified: bool

@router.post("/auth/google")
def google_auth(user_data: GoogleUserRequest):
    if not user_data.email.lower().endswith(ALLOWED_DOMAIN):
        raise HTTPException(
            status_code=403,
            detail=f"Only {ALLOWED_DOMAIN} emails allowed"
        )

    if not user_exists(user_data.email):
        create_user(user_data.email, {
            "full_name": user_data.displayName,
            "password": None,
            "uid": user_data.uid,
            "auth_provider": "google",
            "created_at": str(datetime.now())
        })

    token = create_token({"email": user_data.email})
    session_token = create_session_token({"email": user_data.email})

    create_session(session_token, user_data.email)

    return {
        "token": token,
        "session_token": session_token,
        "user": {
            "email": user_data.email,
            "full_name": user_data.displayName,
            "uid": user_data.uid
        }
    }