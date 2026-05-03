import logging

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.firebase_admin import verify_firebase_token

logger = logging.getLogger(__name__)


def get_current_user(
    authorization: str | None = Header(default=None), db: Session = Depends(get_db)
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token"
        )

    token = authorization.split(" ", 1)[1]

    try:
        decoded = verify_firebase_token(token)
    except Exception as e:
        # Log the underlying cause for forensics; the client only sees
        # the generic "Invalid token" so we don't leak which step failed.
        logger.warning("Firebase token verification failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    uid = decoded["uid"]
    email = decoded.get("email")

    user = db.query(User).filter(User.firebase_uid == uid).first()
    if not user:
        user = User(firebase_uid=uid, email=email, hashed_password="")
        db.add(user)
        db.commit()
        db.refresh(user)

    return user  # type: ignore[no-any-return]
