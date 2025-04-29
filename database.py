import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import dotenv

dotenv.load_dotenv()

ENV = os.getenv("ENV", "local")

if ENV == "local":
    DATABASE_URL = os.getenv("LOCAL_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/newsdb")
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/newsdb")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency for routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
