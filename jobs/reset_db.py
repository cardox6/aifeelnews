# jobs/reset_db.py
from database import Base, engine
from models.article import Article
from models.bookmark import Bookmark  # Include all models

def reset_database():
    print("⚠️ Dropping and recreating all tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Database reset complete.")

if __name__ == "__main__":
    reset_database()
