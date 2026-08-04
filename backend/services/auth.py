from jose import jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import secrets

SECRET_KEY = "secret123"
ALGORITHM = "HS256"

# Use PBKDF2 (good choice ✅)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# -------------------------
# 🔐 PASSWORD FUNCTIONS
# -------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# -------------------------
# 🔑 ACCESS TOKEN (LOGIN)
# -------------------------
def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=5)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# -------------------------
# 🧾 SESSION TOKEN
# -------------------------
def create_session_token(data: dict) -> str:
    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(days=1)
    session_id = secrets.token_hex(16)

    to_encode.update({
        "exp": expire,
        "session_id": session_id
    })

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# -------------------------
# 🔍 VERIFY TOKEN
# -------------------------
def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except Exception:
        return None