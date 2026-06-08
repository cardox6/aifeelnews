#!/usr/bin/env python3
"""Grant (or revoke) the ``role=admin`` Firebase custom claim for a user.

Usage:
    python scripts/dev/set_admin_claim.py user@example.com
    python scripts/dev/set_admin_claim.py user@example.com --revoke

Resolves the Firebase UID from the email, then writes the custom claim via
``firebase_admin.auth.set_custom_user_claims``. The claim is embedded in the
user's ID token the NEXT time the token is minted/refreshed — the current
token in the browser keeps its old claims until it expires (~1h) or the SPA
calls ``getIdToken(true)`` to force a refresh.

Requires real Firebase Admin credentials (``FIREBASE_SERVICE_ACCOUNT_JSON``)
and network access; this is an operator tool, not part of the test suite.
"""

import argparse
import os
import sys

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from firebase_admin import auth  # type: ignore[import-untyped]

from app.services.firebase_admin import get_firebase_app


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set or clear the role=admin Firebase custom claim"
    )
    parser.add_argument("email", help="Email of the Firebase user")
    parser.add_argument(
        "--revoke",
        action="store_true",
        help="Remove the admin claim instead of granting it",
    )
    args = parser.parse_args()

    # Initialise the same Firebase Admin app the backend uses (honours the
    # FIREBASE_SERVICE_ACCOUNT_JSON path-or-inline handling).
    get_firebase_app()

    user = auth.get_user_by_email(args.email)
    # Preserve any unrelated custom claims; only touch `role`.
    claims = dict(user.custom_claims or {})
    if args.revoke:
        claims.pop("role", None)
    else:
        claims["role"] = "admin"
    # Passing None (rather than {}) fully clears the claims object on revoke.
    auth.set_custom_user_claims(user.uid, claims or None)

    action = "revoked admin for" if args.revoke else "granted admin to"
    print(f"OK: {action} {args.email} (uid={user.uid})")
    print("Note: takes effect on the user's NEXT token refresh — sign out/in,")
    print("      or call getIdToken(true) in the SPA to force it now.")


if __name__ == "__main__":
    main()
