import os
from typing import Optional, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from invoice import router as invoice_router

app = FastAPI()


from invoice import router as invoice_router

app = FastAPI()

# frontend DNS
origins = [
    "http://localhost",
    "http://localhost:8080",
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include the invoice router
app.include_router(invoice_router, prefix="/invoices", tags=["invoices"])
