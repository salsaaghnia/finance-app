
import os
from fastapi import FastAPI
from pydantic import BaseModel, Field
from beanie import Document, init_beanie
from pymongo import AsyncMongoClient
from datetime import datetime
from typing import Literal
from collections import defaultdict

app = FastAPI(title="Profiling App")


class Transaction(Document):
    date: datetime 
    amount: int = Field(..., ge=1)
    method: Literal["cash", "gopay", "bca", "shopee", "mandiri"]
    desc: str
    trx_type: Literal["income", "purchase"]

    class Settings:
        name = "trx_profiling"

        


class ProfilingRequest(BaseModel):
    current_amount: int

@app.on_event("startup")
async def init_db():
    mongo_uri = os.getenv("MONGO_URI", "mongodb+srv://salchasesthesun_db_user:XR5oVfjVLmJwLjcn@cluster0.d4kdnzz.mongodb.net/?appName=Cluster0")
    db_name = os.getenv("DB_NAME", "bootcamp")
    client = AsyncMongoClient(mongo_uri)
    await init_beanie(database=client[db_name], document_models=[Transaction])

@app.post("/check-limit")
async def check_limit(req: ProfilingRequest):
    purchases = await Transaction.find({"trx_type": "purchase"}).to_list()
    
    if not purchases:
        return {"alert_message": "Ini data pengeluaran pertamamu. Terus catat secara rutin ya! 📈"}

    monthly_totals = defaultdict(float)
    
    for trx in purchases:
        
        month_key = trx.date.strftime("%Y-%m")
        monthly_totals[month_key] += float(trx.amount)

    sorted_months = sorted(monthly_totals.keys())
    
    if len(sorted_months) <= 1:
        return {"alert_message": "Data pengeluaran masih dalam bulan pertama, belum bisa membandingkan rata-rata. Keep tracking! 🌟"}
        
    current_month = sorted_months[-1]
    y = monthly_totals[current_month]
    
    previous_months = sorted_months[:-1]
    total_previous = sum(monthly_totals[m] for m in previous_months)
    x = total_previous / len(previous_months)
    
    if x >= y:
        message = f"Aman! Pengeluaranmu bulan ini (Rp {y:,.0f}) masih di bawah rata-rata (Rp {x:,.0f}). Good job, pertahankan kebiasaan baik ini ya!"
    else:
        message = (
            f"Warning! Pengeluaranmu bulan ini (Rp {y:,.0f}) sudah melebihi "
            f"rata-rata bulan-bulan sebelumnya (Rp {x:,.0f}). "
            "Yuk, pelan pelan belanjanya biar keuangan kembali sehat! Kamu pasti bisa mengelola, semangat!"
        )
        
    return {"alert_message": message, "x": x, "y": y}