import os
from typing import Optional, List

from fastapi import FastAPI, Body, HTTPException, status
from fastapi.responses import Response
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator

from typing_extensions import Annotated

from bson import ObjectId
import motor.motor_asyncio
from pymongo import ReturnDocument



from invoice import router as invoice_router

app = FastAPI()

# Include the invoice router
app.include_router(invoice_router, prefix="/invoices", tags=["invoices"])
