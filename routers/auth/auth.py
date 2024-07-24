from fastapi import FastAPI, APIRouter, Body, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .frappeclient import FrappeClient
import jwt
import secrets
import math
from datetime import datetime, timedelta, timezone
import requests
from decouple import config

SECRET_KEY = config('SECRET_KEY')
ALGORITHM = config('ALGORITHM',default = "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 300
FRAPPE_URL = config('FRAPPE_URL')


router = APIRouter()
client = FrappeClient(FRAPPE_URL)

class LoginData(BaseModel):
    username: str
    password: str


@router.post("/", response_description="Auth")
async def auth(data: LoginData):
    try:
        client.login(data.username, data.password)

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"message": {
                    "success_key": 0,
                    "message": "Invalid username or password."
                }}
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"message": {
                    "success_key": 0,
                    "message": f"HTTP error occurred: {http_err}"
                }}
            )

    except requests.exceptions.ConnectionError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": {
                "success_key": 0,
                "message": "Unable to connect to Frappe server. Please try again later."
            }}
        )

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
            "username": user.get("username"),
            "email": user.get("email"),
            "roles":[r.get("role") for r in user.get("roles")],
            "token":f"bearer {access_token}"
        }}
    )

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
