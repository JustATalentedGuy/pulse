import secrets

from fastapi import HTTPException, Security, status
from fastapi.security.api_key import APIKeyHeader

from app.config import get_settings


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    expected = get_settings().api_key
    if not api_key or not secrets.compare_digest(api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    return api_key
