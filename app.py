import os
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from routers.invoice import router as invoice_router
from routers.auth.auth import router as auth_router
from datetime import datetime, timedelta, timezone


from database import invoicedb as db
session_collection = db.get_collection("sessions")


async def cleanup_expired_sessions():
    while True:
        # Delete sessions where the expiration time is less than the current UTC time
        session_collection.delete_many({"expires_at": {"$lt": datetime.now(timezone.utc)}})
        
        # Wait for an hour before checking again
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Background task for cleaning expired sessions
    task = asyncio.create_task(cleanup_expired_sessions())

    try:
        yield  # Startup phase completed, app is running
    finally:
        # Shutdown phase, clean up tasks
        print("Application shutdown")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("Cleanup task cancelled during shutdown")


app = FastAPI(lifespan=lifespan)

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
app.include_router(auth_router,prefix="/auth",tags=["auth"])

