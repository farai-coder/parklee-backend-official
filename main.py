from fastapi import FastAPI
from database import Base, engine
from routers import users, spots, reservations, events, analytics, auth

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Parking API")

app.include_router(users.user_router)
app.include_router(spots.router)
app.include_router(reservations.router)
app.include_router(analytics.router)
app.include_router(events.router)
app.include_router(auth.auth_router)

# add cors midddleware
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
