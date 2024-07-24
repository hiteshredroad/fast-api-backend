from fastapi import FastAPI, APIRouter, Body, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .frappeclient import FrappeClient
import jwt
import secrets
import math
from datetime import datetime, timedelta, timezone

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 300

FRAAPE_URL = "http://127.0.0.1:8001"


router = APIRouter()
client = FrappeClient(FRAAPE_URL)

class LoginData(BaseModel):
    username: str
    password: str


@router.post("/", response_description="Auth")
async def auth(data: LoginData):
    try:
        login = client.login(data.username, data.password)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"message": {
                "success_key": 0,
                 "message": "Authentication Error!"
            }}
        )

    api_generate = await generate_keys(data.username)
    user = client.get_doc('User', data.username)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": data.username}, expires_delta=access_token_expires
    )
  


    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"message": {
            "success_key": 1,
            "message": "Authentication success",
            "api_key": user.get("api_key"),
            "api_secret": api_generate,
            "username": user.get("username"),
            "email": user.get("email"),
            "roles":[r.get("role") for r in user.get("roles")],
            "token":f"bearer {access_token}"
        }}
    )

async def generate_keys(username: str):
    user_details = client.get_doc('User', username)
    api_secret = generate_hash(length=15)
    if not user_details.get("api_key"):
        api_key = generate_hash(length=15)
        user_details["api_key"] = api_key
    user_details['api_secret'] = api_secret
    client.update(user_details)
    return api_secret

def generate_hash(txt: str | None = None, length: int = 56) -> str:
    """Generate random hash using best available randomness source."""
    if not length:
        length = 56
    return secrets.token_hex(math.ceil(length / 2))[:length]


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=300)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
