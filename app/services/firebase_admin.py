import json
import os
from typing import Any, Dict

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import auth, credentials  # type: ignore[import-untyped]

_app: Any = None


def get_firebase_app() -> Any:
    global _app
    if _app:
        return _app

    # FIREBASE_SERVICE_ACCOUNT_JSON can be either a path to a JSON file
    # (typical local dev: GOOGLE_APPLICATION_CREDENTIALS-style) or the JSON
    # contents themselves (Cloud Run with Secret Manager secretKeyRef, which
    # mounts the secret value directly into the env var). credentials.Certificate
    # only accepts a file path, so detect the JSON case and write it to a temp
    # file or pass the parsed dict.
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if raw:
        stripped = raw.lstrip()
        if stripped.startswith("{"):
            cred = credentials.Certificate(json.loads(raw))
        else:
            cred = credentials.Certificate(raw)
        _app = firebase_admin.initialize_app(cred)
    else:
        _app = firebase_admin.initialize_app()

    return _app


def verify_firebase_token(id_token: str) -> Dict[str, Any]:
    get_firebase_app()
    return auth.verify_id_token(id_token)  # type: ignore[no-any-return]
