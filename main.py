from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import users, articles
from database import Base, engine
import models.article, models.user, models.bookmark

Base.metadata.create_all(bind=engine)
app = FastAPI(title="aiFeelNews API")

# Middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(users.router, prefix="/users", tags=["Users"])
app.include_router(articles.router, prefix="/articles", tags=["Articles"])

@app.get("/")
def root():
    return {"message": "aiFeelNews API is running"}
