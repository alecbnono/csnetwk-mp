import base64
import os
from typing import Dict
from .messages import build_message, new_message_id
from .tokens import make_token, validate_token
from .utils import now_ts

class FileTransfers:
    def __init__(self, user_id: str, tx, peers, ack_mgr, log, loss_scope="file"):
        self.user_id = user_id
        self.tx = tx
        self.peers = peers
        self.ack_mgr = ack_mgr
        self.log = log
        self.loss_scope = loss_scope
        # fileid -> { offer:{...}, accepted:bool, chunks:dict(index->bytes), total:int, filename:str, sender:str }
        self.rx: Dict[str, Dict] = {}
        # resend book-keeping: mid -> (callable that re-sends the message)
        self._resenders: Dict[str, callable] = {}

    def _send_and_track(self, ip, port, msg_dict, scope="file"):
        # ensure MESSAGE_ID
        if "MESSAGE_ID" not in msg_dict:
            msg_dict["MESSAGE_ID"] = new_message_id()
        mid = msg_dict["MESSAGE_ID"]
        raw = build_message(msg_dict)

        def do_resend():
            # rebuild to include any fields the caller may mutate
            self.tx.send_unicast(ip, port, build_message(msg_dict), drop_for=scope)

        # store a resender so AckManager (via App fallback) can re-send us
        self._resenders[mid] = do_resend

        # self.tx.send_unicast(ip, raw, drop_for=scope)
        # fix: include port in send_unicast
        self.tx.send_unicast(ip, port, raw, drop_for=scope)

        self.ack_mgr.track(mid)

    # ---------- sender side ----------
    def send_offer(self, to_user: str, fileid: str, filename: str, filesize: int, filetype: str, description: str, ttl=3600):
        # ip = self.peers.address_of(to_user)
        # fix: use endpoint_of to get both ip and port
        ip, port = self.peers.endpoint_of(to_user)

        tok = make_token(self.user_id, now_ts() + ttl, "file")
        msg = {
            "TYPE": "FILE_OFFER",
            "FROM": self.user_id,
            "TO": to_user,
            "FILENAME": filename,
            "FILESIZE": str(filesize),
            "FILETYPE": filetype,
            "FILEID": fileid,
            "DESCRIPTION": description,
            "TIMESTAMP": str(now_ts()),
            "TOKEN": tok,
        }
        self._send_and_track(ip, port, msg, scope=self.loss_scope)

    def send_chunk(self, to_user: str, fileid: str, index: int, total: int, chunk_bytes: bytes, chunk_size: int, ttl=3600):
        # ip = self.peers.address_of(to_user)
        # fix: use endpoint_of to get both ip and port
        ip, port = self.peers.endpoint_of(to_user)

        tok = make_token(self.user_id, now_ts() + ttl, "file")
        b64 = base64.b64encode(chunk_bytes).decode("ascii")
        msg = {
            "TYPE": "FILE_CHUNK",
            "FROM": self.user_id,
            "TO": to_user,
            "FILEID": fileid,
            "CHUNK_INDEX": str(index),
            "TOTAL_CHUNKS": str(total),
            "CHUNK_SIZE": str(chunk_size),
            "DATA": b64,
            "TOKEN": tok
        }
        self._send_and_track(ip, port, msg, scope=self.loss_scope)

    # ---------- receiver side ----------
    def on_offer(self, msg: Dict[str, str], addr_ip: str):
        sender = msg.get("FROM","")
        token_ok = validate_token(msg.get("TOKEN",""), "file", sender)
        if not token_ok: return
        fileid = msg.get("FILEID","")
        self.rx[fileid] = {
            "offer": msg,
            "accepted": False,
            "chunks": {},
            "total": None,
            "filename": msg.get("FILENAME","received.bin"),
            "sender": sender
        }
        # Non-verbose print
        print(f'User {sender.split("@")[0]} is sending you a file, do you accept? Use: accept {fileid}')

    def accept(self, fileid: str):
        if fileid in self.rx:
            self.rx[fileid]["accepted"] = True
            print(f"Accepted file {fileid}")

    def ignore(self, fileid: str):
        if fileid in self.rx:
            del self.rx[fileid]
            print(f"Ignored file {fileid}")

    def on_chunk(self, msg: Dict[str, str], addr_ip: str):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "file", sender):
            return
        fileid = msg.get("FILEID","")
        st = self.rx.get(fileid)
        if not st or not st.get("accepted"):
            # ignore silently per spec
            return
        idx = int(msg.get("CHUNK_INDEX","0"))
        tot = int(msg.get("TOTAL_CHUNKS","1"))
        data_b64 = msg.get("DATA","")
        try:
            chunk = base64.b64decode(data_b64.encode("ascii"))
        except Exception:
            return
        st["chunks"][idx] = chunk
        st["total"] = tot

        #fix: save files under per-sender directories
        if len(st["chunks"]) == tot:
            out = b"".join(st["chunks"][i] for i in range(tot))
            fname = os.path.basename(st["filename"])

            # NEW: save under inbox/<sender_name>/<filename>
            sender_name = (st.get("sender","").split("@")[0] or "unknown")
            base_dir = os.path.join("inbox", sender_name)
            os.makedirs(base_dir, exist_ok=True)
            path = os.path.join(base_dir, fname)

            with open(path, "wb") as f:
                f.write(out)

            print(f'📥 File saved to {path}')

            # notify FILE_RECEIVED (unchanged)
            ip, port = self.peers.endpoint_of(sender)
            ack_msg = build_message({
                "TYPE": "FILE_RECEIVED",
                "FROM": self.user_id,
                "TO": sender,
                "FILEID": fileid,
                "STATUS": "COMPLETE",
                "TIMESTAMP": str(now_ts())
            })
            self.tx.send_unicast(ip, port, ack_msg, drop_for=self.loss_scope)
            del self.rx[fileid]

