from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base

# Import all models
from app.models import (
    User, Workspace, Contact, Service, Booking,
    Conversation, Message, Form, FormSubmission,
    InventoryItem, Integration
)

from app.tasks.reminders import send_booking_reminders
# Import routes
from app.routes import auth, onboarding, public, dashboard, inbox, bookings, forms, inventory, staff, settings, integrations

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="NexSpace Platform API",
    description="Unified Operations Platform for Service Businesses",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://careops-platform-nine.vercel.app",
        "https://careops-platform-jousdqogg-abqariyahs-projects.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(onboarding.router, prefix="/api/onboarding", tags=["Onboarding"])
app.include_router(public.router, prefix="/api/public", tags=["Public"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(inbox.router, prefix="/api/inbox", tags=["Inbox"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["Bookings"])
app.include_router(forms.router, prefix="/api/forms", tags=["Forms"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Inventory"])
app.include_router(staff.router, prefix="/api/staff", tags=["Staff"])
app.include_router(settings.router, prefix="/api/settings", tags=["Settings"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["Integrations"])



# Root endpoint
@app.get("/")
def root():
    return {
        "message": "NexSpace Platform API",
        "status": "running",
        "docs": "/docs"
    }

# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy", "environment": "development"}



@app.get("/api/tasks/send-reminders")
def trigger_reminders():
    """
    Manual trigger for sending reminders
    Can be called by cron job or scheduler
    Visit: http://localhost:8000/api/tasks/send-reminders
    """
    try:
        count = send_booking_reminders()
        return {
            "success": True,
            "reminders_sent": count,
            "message": f"Successfully sent {count} reminder(s)"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }