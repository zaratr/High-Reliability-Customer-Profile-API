from datetime import datetime, timedelta, timezone
from typing import List

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer, SecurityScopes
from passlib.hash import bcrypt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.auth import ApiKeyClient
from app.schemas.auth import TokenData

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


ROLE_SCOPES = {
    "ADMIN": ["customers:write", "customers:read", "signals:write", "deactivate"],
    "SUPPORT": ["customers:read", "deactivate"],
    "SERVICE": ["signals:write"],
}


def create_access_token(username: str, scopes: List[str]) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode = {"sub": username, "scopes": scopes, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    username = payload.get("sub")
    scopes = payload.get("scopes", [])
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid token")
    return TokenData(username=username, scopes=scopes)


def get_current_user(
    security_scopes: SecurityScopes, credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)
) -> TokenData:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="credentials required")
    token = credentials.credentials
    token_data = decode_token(token)
    for scope in security_scopes.scopes:
        if scope not in token_data.scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient scope")
    return token_data


def get_api_key_client(api_key: str, db: Session) -> ApiKeyClient:
    client = db.query(ApiKeyClient).filter(ApiKeyClient.hashed_key == bcrypt.hash(api_key)).first()
    if not client or not client.enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")
    return client


def api_key_auth(api_key: str = Security(api_key_header), db: Session = Depends(get_db)) -> ApiKeyClient:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="api key required")
    # In a real system hashed comparison would be constant time; simplified here
    client = db.query(ApiKeyClient).filter(ApiKeyClient.hashed_key == api_key).first()
    if not client or not client.enabled:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid api key")
    return client
