import time
import hashlib

# Simulated revocation list (could be persisted in memory or file)
revoked_tokens = set()

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def is_token_expired(token: str) -> bool:
    try:
        _, expiry_str, _ = token.split("|")
        expiry = int(expiry_str)
        return time.time() > expiry
    except Exception:
        return True

def is_token_scope_valid(token: str, required_scope: str) -> bool:
    try:
        _, _, scope = token.split("|")
        return scope == required_scope
    except Exception:
        return False

def is_token_revoked(token: str) -> bool:
    return hash_token(token) in revoked_tokens

def validate_token(token: str, required_scope: str) -> bool:
    return not is_token_expired(token) and \
           is_token_scope_valid(token, required_scope) and \
           not is_token_revoked(token)

def revoke_token(token: str):
    revoked_tokens.add(hash_token(token))
