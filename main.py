from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import users, articles, bookmarks, sources
from database import Base, engine
import models.article, models.user, models.bookmark, models.source

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
app.include_router(bookmarks.router, prefix="/bookmarks", tags=["Bookmarks"])
app.include_router(sources.router, prefix="/sources", tags=["Sources"])

@app.get("/")
def root():
    return {"message": "aiFeelNews API is running"}
