import os
from fastapi import FastAPI, APIRouter, Body, HTTPException, status,Response, Cookie,Depends,BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse,FileResponse
from pydantic import BaseModel
from .frappeclient import FrappeClient
from jose import JWTError,jwt
from datetime import datetime, timedelta, timezone
import requests
from decouple import config
from typing import Optional,Union,List
from routers.utils import create_backup
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
        httponly=False,
        max_age=1800,  # 30 minutes
        expires=1800,
        secure=False,  # Use this in production with HTTPS
        samesite="lax",
        # domain=".example.com",  # Ensure this is set correctly
        path="/",  # This can be adjusted as needed
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


@router.post("/backup")
async def backup_database(background_tasks: BackgroundTasks):
    background_tasks.add_task(create_backup)
    return {"message": "Backup process started"}


@router.get("/backups", response_model=List[str])
async def list_backups():
    current_file_path = os.path.abspath(__file__)
    current_directory = current_file_path
    while os.path.basename(current_directory) != 'fast-api-backend':
        current_directory = os.path.dirname(current_directory)

    backup_dir = os.path.join(current_directory, 'backups')
    
    if not os.path.exists(backup_dir):
        return []
    
    backups = [f for f in os.listdir(backup_dir) if f.endswith('.gz')]
    return sorted(backups, reverse=True)  # Most recent first

@router.get("/backups/{filename}")
async def download_backup(filename: str):
    current_file_path = os.path.abspath(__file__)
    current_directory = current_file_path
    while os.path.basename(current_directory) != 'fast-api-backend':
        current_directory = os.path.dirname(current_directory)

    backup_dir = os.path.join(current_directory, 'backups')
    file_path = os.path.join(backup_dir, filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Backup file not found")
    
    return FileResponse(file_path, media_type='application/gzip', filename=filename)
