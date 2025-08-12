from fastapi import FastAPI
from database import Base, SessionLocal, engine
from routers import users, spots, reservations, events, analytics, auth, sessions

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Parking API")

app.include_router(users.user_router)
app.include_router(spots.router)
app.include_router(reservations.router)
app.include_router(analytics.router)
app.include_router(events.router)
app.include_router(auth.auth_router)
app.include_router(sessions.router)

# add cors midddleware
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Create admin user on startup
@app.on_event("startup")
def on_startup():
    db = SessionLocal()
    try:
        users.create_default_admin_if_not_exists(db)
    finally:
        db.close()
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 
    
