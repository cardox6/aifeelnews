from fastapi import APIRouter

router = APIRouter(tags=["Users"])


@router.get("/ping")
def ping_users():
    return {"message": "users router is live"}
