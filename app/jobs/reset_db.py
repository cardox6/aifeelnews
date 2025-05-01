import subprocess

def reset_database():
    """
    WARNING: This will drop ALL tables in your configured database and recreate them via Alembic migrations.
    """
    print("⚠️ Dropping all tables...")
    subprocess.run(["alembic", "downgrade", "base"], check=True)
    print("🆕 Recreating schema via Alembic migrations...")
    subprocess.run(["alembic", "upgrade", "head"], check=True)
    print("✅ Database reset complete.")

if __name__ == "__main__":
    reset_database()