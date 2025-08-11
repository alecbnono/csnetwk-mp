import random
from typing import Dict, Tuple
from .utils import now_ts, normalize_key
from .constants import DEFAULT_TTL_SEC

def parse_message(raw: str) -> Dict[str, str]:
    msg = {}
    for line in raw.replace("\r\n", "\n").split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            msg[normalize_key(k.strip().upper())] = v.strip()
    return msg

def build_message(fields: Dict[str, str]) -> str:
    # order TYPE first for readability
    lines = []
    if "TYPE" in fields:
        lines.append(f"TYPE: {fields['TYPE']}")
    for k, v in fields.items():
        if k == "TYPE": continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines) + "\n\n"

def new_message_id() -> str:
    return f"{random.getrandbits(64):x}"

def default_post_fields(user_id: str, content: str, ttl: int = DEFAULT_TTL_SEC) -> Dict[str, str]:
    ts = now_ts()
    return {
        "TYPE": "POST",
        "USER_ID": user_id,
        "CONTENT": content,
        "TTL": str(ttl),
        "TIMESTAMP": str(ts),
        "MESSAGE_ID": new_message_id(),
    }

def needs_ack(msg: Dict[str, str]) -> Tuple[bool, str]:
    # If message has MESSAGE_ID and is a type we track, return (True, mid)
    mid = msg.get("MESSAGE_ID")
    return (mid is not None, mid or "")
