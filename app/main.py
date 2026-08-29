"""
BIS SmartAI — FastAPI Application Entry Point
Problem Statement: SIH26107
"""
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import (
    auth, users, chat, conversations,
    standards, saved, compliance, documents, feedback,
    services, laboratories
)

app = FastAPI(
    title=settings.app_name,
    description="AI-powered Intelligent Assistant for Indian Standards and BIS Services for Industries and Consumers (SIH26107)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS configuration
origins = [
    settings.frontend_url,
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(conversations.router, prefix="/api")
app.include_router(standards.router, prefix="/api")
app.include_router(saved.router, prefix="/api")
app.include_router(compliance.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(feedback.router, prefix="/api")
app.include_router(services.router, prefix="/api")
app.include_router(laboratories.router, prefix="/api")


@app.get("/health", status_code=status.HTTP_200_OK, tags=["Health"])
async def health_check():
    """Health check endpoint for application and services."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "database": "configured" if settings.is_db_configured else "not_configured",
        "groq_configured": settings.is_groq_configured,
        "gemini_configured": settings.is_gemini_configured,
        "ai_configured": settings.is_ai_configured,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to BIS SmartAI API",
        "docs": "/docs",
        "health": "/health",
    }
