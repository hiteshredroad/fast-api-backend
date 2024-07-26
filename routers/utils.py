from fastapi import Depends, HTTPException, Security,Cookie,status,Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError,jwt
from decouple import config
from typing import Optional,Union
from routers.auth.auth import client

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