from fastapi import APIRouter

router = APIRouter()

@router.get("/ping")
def ping_users():
    return {"message": "users router is live"}
