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

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": form_data.username}, expires_delta=access_token_expires
    )

    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        max_age=1800, 
        expires=1800,
        secure=True,  # Use this in production with HTTPS
        samesite="lax"
    )
    
    return {"message": {
        "status_code":status.HTTP_200_OK,
        "success_key": 1,
        "message": "Login successful",
        "username": user.get("username"),
        "email": user.get("email"),
        "roles":[r.get("role") for r in user.get("roles")],
    }}
  



@router.post("/logout", response_description="logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logout successful"}


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(access_token: Union[str, None] = Cookie(None)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not access_token:
        raise credentials_exception
    try:
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = client.get_doc('User', username)  # Assuming this is how you get user data
    if user is None:
        raise credentials_exception
    return True