import os
import asyncio
from fastapi import Depends, HTTPException, Security,Cookie,status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError,jwt
from decouple import config
from typing import Optional,Union,List
import subprocess
from functools import wraps
from datetime import datetime, timedelta, timezone


from database import invoicedb as db,MONGODB_URL
session_collection = db.get_collection("sessions")

SECRET_KEY = config('SECRET_KEY')
ALGORITHM = config('ALGORITHM',default = "HS256")


security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return username
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    


async def get_current_user(session_id: str = Cookie(None)):
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    session = await session_collection.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session not found")
    

    if session["expires_at"] < datetime.utcnow():
        await session_collection.delete_one({"session_id": session_id})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    
    # Extend session expiration and   /// role update
    await session_collection.update_one(
        {"session_id": session_id},
        {"$set": {"expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)}}
    )
    
    return session


# check role in api endpoint
def check_roles(required_roles: List[str]):
    def decorator(func):
        # for preserve metadata
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(status_code=401, detail="User not authenticated")
            
            user_roles = current_user.get('roles', [])
            if not any(role in required_roles for role in user_roles):
                raise HTTPException(status_code=403, detail="User does not have the required role")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator




# set in cron job
async def create_backup():
    # Set your MongoDB connection details
    db_name = db.name
    
    # Set the output directory to fast-api-backend/backups
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(base_dir, 'backups')
    os.makedirs(backup_dir, exist_ok=True)  

    # Create a timestamp for the backup file
    utc_time = datetime.now(timezone.utc)
    ist_time = utc_time + timedelta(hours=5, minutes=30)
    timestamp = ist_time.strftime("%d-%m-%Y_%H-%M-%S")
    backup_file = f"{db_name}_{timestamp}.gz"
    backup_path = os.path.join(backup_dir, backup_file)


    cmd = f"mongodump --uri=\"{MONGODB_URL}\" --db {db_name} --gzip --archive={backup_path}"

    # Execute the command
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print(f"Backup created successfully: {backup_file}")
            return {"status": "success", "file": backup_file}
        else:
            error_msg = stderr.decode()
            print(f"Backup failed: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Backup failed: {error_msg}")
    except Exception as e:
        error_msg = str(e)
        print(f"Backup failed: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Backup failed: {error_msg}")
    