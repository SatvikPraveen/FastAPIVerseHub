# File: app/core/security.py

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import HTTPException, status
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token bearer
security = HTTPBearer()


class SecurityManager:
    """Centralized security management for the application."""
    
    def __init__(self):
        self.pwd_context = pwd_context
        self.algorithm = settings.JWT_ALGORITHM
        self.secret_key = settings.JWT_SECRET_KEY
    
    # Password operations
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain password against a hashed password."""
        return self.pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash."""
        return self.pwd_context.hash(password)
    
    # JWT token operations
    def create_access_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: timedelta | None = None
    ) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            self.secret_key, 
            algorithm=self.algorithm
        )
        
        return encoded_jwt
    
    def create_refresh_token(
        self, 
        data: Dict[str, Any], 
        expires_delta: timedelta | None = None
    ) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                days=settings.REFRESH_TOKEN_EXPIRE_DAYS
            )
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(
            to_encode, 
            self.secret_key, 
            algorithm=self.algorithm
        )
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token, 
                self.secret_key, 
                algorithms=[self.algorithm]
            )
            
            # Check if token has expired
            exp = payload.get("exp")
            if exp and datetime.now(timezone.utc) > datetime.fromtimestamp(exp):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return payload
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    def get_user_id_from_token(self, token: str) -> int:
        """Extract user ID from JWT token."""
        payload = self.verify_token(token)
        user_id: int = payload.get("sub")
        
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return user_id
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Verify access token specifically."""
        payload = self.verify_token(token)
        
        token_type = payload.get("type")
        if token_type != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
    
    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """Verify refresh token specifically."""
        payload = self.verify_token(token)
        
        token_type = payload.get("type")
        if token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return payload
    
    def create_token_pair(self, user_id: int, additional_data: Dict[str, Any] = None) -> Dict[str, str]:
        """Create both access and refresh tokens."""
        token_data = {"sub": str(user_id)}
        
        if additional_data:
            token_data.update(additional_data)
        
        access_token = self.create_access_token(data=token_data)
        refresh_token = self.create_refresh_token(data=token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }


# Global security manager instance
security_manager = SecurityManager()


# Utility functions for backward compatibility
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using global security manager."""
    return security_manager.verify_password(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password using global security manager."""
    return security_manager.get_password_hash(password)


def create_access_token(
    data: Dict[str, Any], 
    expires_delta: timedelta | None = None
) -> str:
    """Create access token using global security manager."""
    return security_manager.create_access_token(data, expires_delta)


def create_refresh_token(
    data: Dict[str, Any], 
    expires_delta: timedelta | None = None
) -> str:
    """Create refresh token using global security manager."""
    return security_manager.create_refresh_token(data, expires_delta)


def verify_token(token: str) -> Dict[str, Any]:
    """Verify token using global security manager."""
    return security_manager.verify_token(token)