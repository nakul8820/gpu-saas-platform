from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import health
from app.api.routes import auth
from app.api.routes import tokens
from app.api.routes import servers
from app.api.routes import jobs

app = FastAPI(
    title="GPU Platform API",
    description="GPU-as-a-Service with token-based billing",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(auth.router)
app.include_router(tokens.router)
app.include_router(servers.router)
app.include_router(jobs.router)