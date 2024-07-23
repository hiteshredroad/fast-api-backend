import motor.motor_asyncio
import os

# export MONGODB_URL="mongodb://localhost:27017/"

client = motor.motor_asyncio.AsyncIOMotorClient(os.environ["MONGODB_URL"])

# for invoice
db = client.invoicedb