from database import Base, engine

def reset_database():
    """
    WARNING: This will drop ALL tables in your configured database.
    """
    print("⚠️ Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("🆕 Recreating schema via SQLAlchemy models...")
    Base.metadata.create_all(bind=engine)
    print("✅ Database reset complete.")

if __name__ == "__main__":
    reset_database()
