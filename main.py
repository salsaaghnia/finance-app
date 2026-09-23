import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime, date
from beanie import Document, init_beanie, PydanticObjectId
from pymongo import AsyncMongoClient
from typing import Literal, Optional
import pandas as pd
import io


app = FastAPI()

class Transaction(Document):

    date: datetime 
    amount: int = Field(..., ge=1)
    method: Literal["cash", "gopay", "bca", "shopee", "mandiri"]
    desc: str
    trx_type: Literal["income", "purchase"]

    class Settings:

        name = "trx_collection"



class RequestNewTransaction(BaseModel):

    amount: int = Field(..., ge=1)
    method: Literal["cash", "gopay", "bca", "shopee", "mandiri"]
    desc: str
    trx_type: Literal["income", "purchase"]
    date: Optional[datetime] = None

class RequestUpdateTransaction(BaseModel):
    amount: Optional[int] = Field(None, ge=1)
    method: Optional[Literal["cash", "gopay", "bca", "shopee", "mandiri"]] = None
    desc: Optional[str] = None
    trx_type: Optional[Literal["income", "purchase"]] = None
    date: Optional[datetime] = None


@app.on_event("startup")

async def init_db():
    mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://salchasesthesun_db_user:XR5oVfjVLmJwLjcn@cluster0.d4kdnzz.mongodb.net/?appName=Cluster0")
    db_name = os.getenv("DB_NAME", "bootcamp")
    client = AsyncMongoClient(mongo_uri)
    await init_beanie(database=client[db_name], document_models=[Transaction])



@app.post("/transaction/add")

async def add_transaction(request_body: RequestNewTransaction):
    final_date = request_body.date if request_body.date is not None else datetime.now()
    trx = Transaction(
        date=final_date, 
        amount=request_body.amount, 
        method=request_body.method, 
        desc=request_body.desc, 
        trx_type=request_body.trx_type
    )
    await trx.insert()
    return trx



@app.get("/transaction")

async def get_transaction(start_date: datetime, end_date: datetime):

    return await Transaction.find(

        Transaction.date >= start_date, Transaction.date <= end_date

    ).to_list()



@app.get("/transaction/summary")

async def summary_by_method(year: int, month: int):

    start = datetime(year, month, 1)

    # first day of next month

    if month == 12:

        end = datetime(year + 1, 1, 1)

    else:

        end = datetime(year, month + 1, 1)



    pipeline = [

        {

            "$match": {

                "date": {

                    "$gte": start,

                    "$lt": end

                }

            }

        },

        {

            "$group": {

                "_id": "$trx_type",

                "total_amount": {

                    "$sum": "$amount"

                },

                "count": {

                    "$sum": 1

                },

            }

        }

    ]



    summary_data = await Transaction.aggregate(pipeline).to_list()

    
    total_income = 0
    total_purchase = 0

    
    for item in summary_data:
        if item["_id"] == "income":
            total_income = item["total_amount"]
        elif item["_id"] == "purchase":
            total_purchase = item["total_amount"]

   
    net_amount = total_income - total_purchase

    
    if total_income > 0:
        ratio = round(total_purchase / total_income, 2)
    else:
        
        ratio = 1.0 if total_purchase > 0 else 0.0

    
    if ratio >= 1.0:
        spender_status = "reckless spender"
    else:
        spender_status = "big saver"

    
    return {
        "year": year,
        "month": month,
        "details": summary_data,
        "total_income": total_income,
        "total_purchase": total_purchase,
        "net_amount": net_amount,
        "expense_to_income_ratio": ratio,
        "status": spender_status
    }

@app.put("/transaction/{id}")
async def update_transaction(id: PydanticObjectId, req: RequestUpdateTransaction):
    trx = await Transaction.get(id)
    if not trx:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
    
    # exclude_unset=True memastikan hanya field yang dikirim user yang akan di-update
    update_data = req.model_dump(exclude_unset=True)
    
    if update_data:
        await trx.set(update_data)
        
    return trx

@app.post("/transaction/migrate")
async def migrate_from_excel(file: UploadFile = File(...)):
    
    contents = await file.read()
    df = pd.read_excel(io.BytesIO(contents))
    
    transactions_to_insert = []
    
    
    for index, row in df.iterrows():
        
        raw_amount = str(row["amount"]).strip()
        
        
        if raw_amount.startswith("-"):
            trx_type = "purchase"
            
            clean_amount = raw_amount.replace("-", "").replace("Rp", "").replace(",", "").strip()
        else:
            trx_type = "income"
            
            clean_amount = raw_amount.replace("Rp", "").replace(",", "").strip()
            
        amount_int = int(clean_amount)
        
        
        dt = pd.to_datetime(row["datetime"]).to_pydatetime()
        
        
        trx = Transaction(
            date=dt,
            amount=amount_int,
            method=row["payment_method"].strip().lower(), 
            desc=str(row["description"]).strip(),
            trx_type=trx_type
        )
        
        transactions_to_insert.append(trx)
        
    
    if transactions_to_insert:
        await Transaction.insert_many(transactions_to_insert)
        
    return {
        "message": "Migrasi sukses", 
        "total_migrated": len(transactions_to_insert)
    }

@app.delete("/transaction/{id}")
async def delete_transaction(id: PydanticObjectId):
    trx = await Transaction.get(id)
    if not trx:
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan")
        
    await trx.delete()
    return {"message": f"Transaksi dengan ID {id} berhasil dihapus"}