import os
from typing import Any, Dict

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import auth, credentials  # type: ignore[import-untyped]

_app: Any = None


def get_firebase_app() -> Any:
    global _app
    if _app:
        return _app

    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_path:
        cred = credentials.Certificate(service_account_path)
        _app = firebase_admin.initialize_app(cred)
    else:
        _app = firebase_admin.initialize_app()

    return _app


def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    get_firebase_app()
    return auth.verify_id_token(id_token)  # type: ignore[no-any-return]
