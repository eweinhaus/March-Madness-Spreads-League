from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
import warnings
from dotenv import load_dotenv

# Suppress bcrypt warnings
warnings.filterwarnings("ignore", category=UserWarning, module="passlib.handlers.bcrypt")

# Load environment variables
load_dotenv()

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "secret-key-in-env")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

# Password hashing - use bcrypt as primary, sha256_crypt as fallback
pwd_context = CryptContext(schemes=["bcrypt", "sha256_crypt"], deprecated="auto")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str
    league_id: Optional[str] = None
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

class User(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    league_id: str
    make_picks: bool = True
    admin: bool = False

class ForgotPasswordRequest(BaseModel):
    username: str
    email: str

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash with enhanced error handling."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # First attempt with normal verification
        result = pwd_context.verify(plain_password, hashed_password)
        logger.info(f"Password verification successful: {result}")
        return result
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        
        # Handle bcrypt compatibility issues
        if "bcrypt" in str(e).lower() or "version" in str(e).lower():
            logger.warning("Bcrypt compatibility issue detected, trying fallback verification")
            try:
                # Try with explicit bcrypt verification
                import bcrypt
                if hashed_password.startswith('$2b$') or hashed_password.startswith('$2a$'):
                    result = bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
                    logger.info(f"Fallback bcrypt verification result: {result}")
                    return result
                else:
                    # Try with sha256_crypt as fallback
                    from passlib.hash import sha256_crypt
                    result = sha256_crypt.verify(plain_password, hashed_password)
                    logger.info(f"SHA256 fallback verification result: {result}")
                    return result
            except Exception as fallback_error:
                logger.error(f"Fallback verification also failed: {str(fallback_error)}")
                return False
        
        # Re-raise other exceptions
        raise

def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)

def create_access_token(data: dict, username: str) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "sub": username})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[str]:
    """Verify a JWT token and return the username or a special message if expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError as e:
        # Check if the error is due to token expiration
        if "token is expired" in str(e):
            return "Token expired"  # Custom message for expired token
        return None 