import random

APP_NAME = "LSNP"
DEFAULT_PORT = 50999
MULTICAST_GRP = "224.0.0.251"   # lightweight mDNS-style discovery
BUFFER_SIZE = 65535             # allow big base64 chunks
DISCOVERY_INTERVAL_SEC = 300
DEFAULT_TTL_SEC = 3600
ACK_TIMEOUT_SEC = 2.0
ACK_MAX_RETRIES = 3

#fix: port for discovery (multicast/broadcast)
DISCOVERY_PORT = 50999  #fix: port for discovery (multicast/broadcast)

# Loss simulation (applies to game & file only)
DEFAULT_LOSS_PROB = 0.0  # 0..1

# Non-verbose behavior: these are suppressed unless verbose
SUPPRESS_TYPES = {"PING", "ACK", "FILE_RECEIVED", "REVOKE"}

# Which types expect ACKs and retries
ACK_TRACKED_TYPES = {
    "TICTACTOE_INVITE",
    "TICTACTOE_MOVE",
    "FILE_CHUNK",
    "FILE_OFFER",
    "DM",  # optional but helpful for delivery confirmation
}

# Fields that imply we can/should auto-ACK when receiving
AUTO_ACK_IF_MESSAGE_ID = True

# Default display name
DEFAULT_DISPLAY_NAME = f"Peer_{random.randint(1000,9999)}"
