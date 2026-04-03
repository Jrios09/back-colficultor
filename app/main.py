from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, users, productos, products_public, cart, orders
from app.core.config import settings
from app.db.mongodb import get_db
from app.db.indexes import create_indexes
from app.db.mongodb import setup_collection_validators
from app.db.seed_users import seed_demo_users

app = FastAPI(title="Colficultor API")

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(productos.router)
app.include_router(products_public.router)
app.include_router(cart.router)
app.include_router(orders.router)

@app.on_event("startup")
async def on_startup():
    db = get_db()
    await setup_collection_validators(db)
    await create_indexes(db)
    await seed_demo_users()
