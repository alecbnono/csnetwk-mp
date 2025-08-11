from typing import Dict, Optional
from .utils import ip_from_user_id

class PeerDirectory:
    def __init__(self):
        # user_id -> {address, port, display_name, status, avatar_type, avatar_data}
        self._peers: Dict[str, Dict] = {}

    def upsert_from_profile(self, msg: Dict[str, str], addr_ip: str, addr_port: int):
        uid = msg.get("USER_ID")
        if not uid:
            return
        # Prefer advertised PORT in PROFILE; fall back to previous known; else last src port
        advertised = int(msg.get("PORT", "0") or "0")
        prev = self._peers.get(uid, {})
        port = advertised if advertised > 0 else (prev.get("port") or addr_port)

        self._peers[uid] = {
            "address": addr_ip,
            "port": port,
            "display_name": msg.get("DISPLAY_NAME", uid),
            "status": msg.get("STATUS", ""),
            "avatar_type": msg.get("AVATAR_TYPE", ""),
            "avatar_data": msg.get("AVATAR_DATA", ""),
        }

    def get(self, user_id: str) -> Optional[Dict]:
        return self._peers.get(user_id)

    def endpoint_of(self, user_id: str):
        """Return (ip, port) for a peer."""
        p = self._peers.get(user_id)
        if p and p.get("port"):
            return p["address"], p["port"]
        # Fallback: infer IP from user_id, but port will be unknown (0).
        return ip_from_user_id(user_id), 0
    
    def address_of(self, user_id: str):
        ep = self._peers.get(user_id)
        return ep["address"] if ep else ip_from_user_id(user_id)


    def list(self) -> Dict[str, Dict]:
        return dict(self._peers)
