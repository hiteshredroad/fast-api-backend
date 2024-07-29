from fastapi import Depends, HTTPException, Security,Cookie,status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError,jwt
from decouple import config
from typing import Optional,Union
from datetime import datetime, timedelta, timezone


from database import invoicedb as db
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
    
    # Extend session expiration
    await session_collection.update_one(
        {"session_id": session_id},
        {"$set": {"expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)}}
    )
    
    return session
