import hashlib
from typing import Set
from .utils import now_ts

# simple in-memory revocation set of token hashes
_revoked: Set[str] = set()

def hash_token(tok: str) -> str:
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()

def revoke_token(tok: str) -> None:
    _revoked.add(hash_token(tok))

def is_revoked(tok: str) -> bool:
    return hash_token(tok) in _revoked

def make_token(user_id: str, exp_ts: int, scope: str) -> str:
    return f"{user_id}|{exp_ts}|{scope}"

def parse_token(token: str):
    """
    Accepts flexible formats from the spec examples:
    - "user|ts|scope"
    - "user ts scope"
    - "user ts|scope" (tolerate odd separators)
    Returns (user_id, exp_ts, scope) or (None, None, None) on failure.
    """
    t = token.strip()
    for sep in ["|", " "]:
        if sep in t and t.count(sep) >= 2:
            parts = t.split(sep)
            parts = [p for p in parts if p]
            if len(parts) >= 3:
                try:
                    user_id = parts[0].strip()
                    exp_ts = int(parts[1].strip())
                    scope = parts[2].strip()
                    return user_id, exp_ts, scope
                except Exception:
                    pass
    # last resort: try mixed
    t2 = t.replace("  ", " ").replace("|", " ").split()
    if len(t2) >= 3:
        try:
            return t2[0], int(t2[1]), t2[2]
        except Exception:
            pass
    return None, None, None

def validate_token(token: str, expected_scope: str, sender_id: str) -> bool:
    user_id, exp_ts, scope = parse_token(token or "")
    if not user_id:
        return False
    if user_id != sender_id:
        return False
    if now_ts() > (exp_ts or 0):
        return False
    if scope != expected_scope:
        return False
    if is_revoked(token):
        return False
    return True
