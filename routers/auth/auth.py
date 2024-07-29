from fastapi import FastAPI, APIRouter, Body, HTTPException, status,Response, Cookie,Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .frappeclient import FrappeClient
from jose import JWTError,jwt
from datetime import datetime, timedelta, timezone
import requests
from decouple import config
from typing import Optional,Union
import uuid

from database import invoicedb as db

session_collection = db.get_collection("sessions")

SECRET_KEY = config('SECRET_KEY')
ALGORITHM = config('ALGORITHM',default = "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60
FRAPPE_URL = config('FRAPPE_URL')



router = APIRouter()
client = FrappeClient(FRAPPE_URL)

class LoginData(BaseModel):
    username: str
    password: str


@router.post("/", response_description="Auth")
async def auth(response: Response, form_data: OAuth2PasswordRequestForm = Depends()):
    try:
        await client.login(form_data.username, form_data.password)

    except requests.exceptions.HTTPError as http_err:
        if http_err.response.status_code == 401:
           raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
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

    user = client.get_doc('User', form_data.username)

    # Create a session for the user
    session_id = str(uuid.uuid4())

    session_data = {
        "session_id": session_id,
        "username": user.get("username"),
        "email": user.get("email"),
        "roles": [r.get("role") for r in user.get("roles")],
        "created_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)  # 30 minutes expiration
    }
    
    await session_collection.insert_one(session_data)


    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=1800,  # 30 minutes
        expires=1800,
        # secure=True,  # Use this in production with HTTPS
        samesite="lax"
    )
    return {"message": "Login successful"}




@router.post("/logout", response_description="logout")
async def logout(response: Response, session_id: str = Cookie(None)):
    if session_id:
        await session_collection.delete_one({"session_id": session_id})
    response.delete_cookie("session_id")
    client.logout()
    return {"message": "Logout successful"}



# create jwt auth
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
