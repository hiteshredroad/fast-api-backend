import motor.motor_asyncio
import os

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])

# for invoice
db = client.invoicedb