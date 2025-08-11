import socket
import struct
import time
from typing import Tuple

def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def ip_from_user_id(user_id: str) -> str:
    # expected format "name@ip"
    if "@" in user_id:
        return user_id.split("@", 1)[1].strip()
    return ""

def make_user_id(name: str, ip: str) -> str:
    return f"{name}@{ip}"

def now_ts() -> int:
    return int(time.time())

def compute_broadcast(ip: str) -> str:
    # naive /24 broadcast if private; fallback to 255.255.255.255
    try:
        parts = ip.split(".")
        if len(parts) == 4:
            return ".".join(parts[:3] + ["255"])
    except Exception:
        pass
    return "255.255.255.255"

def join_multicast(sock: socket.socket, group: str, port: int) -> None:
    # IPv4 only
    mreq = struct.pack("=4sl", socket.inet_aton(group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    # ensure multicast TTL=1
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

def normalize_key(k: str) -> str:
    k = k.strip().upper().replace(" ", "")
    if k in ("MESSAGEID", "MESSAGE_ID"): return "MESSAGE_ID"
    if k in ("GAMEID", "GAMED"):         return "GAMEID"
    if k in ("USERID", "USER_ID"):       return "USER_ID"
    if k in ("GROUPID", "GROUP_ID"):     return "GROUP_ID"
    if k in ("AVATARDATA","AVATAR_DATA"):       return "AVATAR_DATA"
    if k in ("AVATARENCODING","AVATAR_ENCODING"): return "AVATAR_ENCODING"
    if k in ("AVATARTYPE","AVATAR_TYPE"):         return "AVATAR_TYPE"
    return k

