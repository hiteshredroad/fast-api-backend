from fastapi import APIRouter, Body, HTTPException, status
from fastapi.responses import Response,JSONResponse
from pydantic import ConfigDict, BaseModel, Field, EmailStr
from pydantic.functional_validators import BeforeValidator
from typing import Optional, List
from typing_extensions import Annotated
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo import ASCENDING, DESCENDING
from datetime import datetime,timezone,timedelta


# https://fastapi.tiangolo.com/tutorial/

# how do i make out custom unique for invoice like empid-month
# How do I update a nested model in pydantic with mongodb and fast api
# https://docs.pydantic.dev/latest/#pydantic-examples

# export MONGODB_URL="mongodb+srv://<username>:<password>@<url>/<db>?retryWrites=true&w=majority"
# when you start the sever
# export MONGODB_URL="mongodb://localhost:27017/"
# MONGODB_URL = ""

# include modal and method in same place

# Import your database connection from app.py
from database import invoicedb as db

router = APIRouter()

invoice_collection = db.get_collection("invoices")

PyObjectId = Annotated[str, BeforeValidator(str)]

class InvoiceModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    invoice_number: Optional[str] = None
    name: str = Field(...)
    email: EmailStr = Field(...)
    amount: float = Field(...,gt=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_schema_extra={
            "example": {
                "invoice_number": "INV-22-02-2023-0001",
                "name": "John Doe",
                "email": "johndoe@example.com",
                "amount": 100.50,
            }
        },
    )

class UpdateInvoiceModel(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    amount: Optional[float] = None
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str},
        json_schema_extra={
            "example": {
                "name": "John Doe",
                "email": "johndoe@example.com",
                "amount": 100.50,
            }
        },
    )

class InvoiceCollection(BaseModel):
    invoices: List[InvoiceModel]

async def generate_invoice_number():
    utc_time = datetime.now(timezone.utc)
    ist_time = utc_time + timedelta(hours=5, minutes=30)
    date_string = ist_time.strftime("%d-%m-%Y")
    
    latest_invoice = await invoice_collection.find_one(
        {"invoice_number": {"$regex": f"^INV-{date_string}"}},
        sort=[("invoice_number", -1)]
    )
    
    if latest_invoice:
        latest_number = int(latest_invoice["invoice_number"].split("-")[-1])
        new_number = latest_number + 1
    else:
        new_number = 1
    
    return f"INV-{date_string}-{new_number:04d}"

@router.post(
    "/",
    response_description="Add new invoice",
    response_model=InvoiceModel,
    status_code=status.HTTP_201_CREATED,
    response_model_by_alias=False,
)
async def create_invoice(invoice: InvoiceModel = Body(...)):
    invoice_number = await generate_invoice_number()
    invoice.invoice_number = invoice_number
    new_invoice = await invoice_collection.insert_one(
        invoice.model_dump(by_alias=True, exclude=["id"])
    )
    created_invoice = await invoice_collection.find_one(
        {"_id": new_invoice.inserted_id}
    )
    return created_invoice

@router.get(
    "/",
    response_description="List all invoices",
    response_model=InvoiceCollection,
    response_model_by_alias=False,
)
async def list_invoices():
    # sort_order = DESCENDING  # or ASCENDING for ascending order
    # invoices = await invoice_collection.find().sort("created_at", sort_order).to_list(1000)
    # return InvoiceCollection(invoices=invoices)
    try:
        return InvoiceCollection(invoices=await invoice_collection.find().to_list(1000))
    except HTTPException as http_exc:
        return {"error": http_exc.detail, "status_code": http_exc.status_code}
    except Exception as exc:
        return {"error": str(exc), "status_code": "unknown"}
    
@router.get(
    "/get_pagination",
    response_description="List all invoices",
    response_model=InvoiceCollection,
    response_model_by_alias=False,
)
async def list_pagination_invoice(skip: int = 0, limit: int = 10):
    return InvoiceCollection(invoices=await invoice_collection.find(skip=skip, limit=limit).to_list(limit-skip))

@router.get(
    "/{invoice_number}",
    response_description="Get a single invoice",
    response_model=InvoiceModel,
    response_model_by_alias=False,
)
async def show_invoice(invoice_number: str):
    if (
        invoice := await invoice_collection.find_one({"invoice_number": invoice_number})
    ) is not None:
        return invoice
    raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found")

@router.put(
    "/{invoice_number}",
    response_description="Update an invoice",
    response_model=InvoiceModel,
    response_model_by_alias=False,
)
async def update_invoice(invoice_number: str, invoice: UpdateInvoiceModel = Body(...)):
    invoice = {
        k: v for k, v in invoice.model_dump(by_alias=True).items() if v is not None
    }
    if len(invoice) >= 1:
        update_result = await invoice_collection.find_one_and_update(
            {"invoice_number": invoice_number},
            {"$set": invoice},
            return_document=ReturnDocument.AFTER,
        )
        if update_result is not None:
            return update_result
        else:
            raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found")
    if (existing_invoice := await invoice_collection.find_one({"invoice_number": invoice_number})) is not None:
        return existing_invoice
    raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found")

@router.delete("/{invoice_number}", response_description="Delete an invoice")
async def delete_invoice(invoice_number: str):
    delete_result = await invoice_collection.delete_one({"invoice_number": invoice_number})
    if delete_result.deleted_count == 1:
        return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": f"Invoice {invoice_number} has been deleted successfully."}
            )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    raise HTTPException(status_code=404, detail=f"Invoice {invoice_number} not found")








