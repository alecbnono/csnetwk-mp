import threading
import time
from typing import Callable, Dict, Optional
from .constants import ACK_TIMEOUT_SEC, ACK_MAX_RETRIES

class AckManager:
    """
    Track outgoing messages that require ACK and trigger retries.
    caller supplies a resend_fn(message_id) to perform the actual resend.
    """
    def __init__(self, resend_fn: Callable[[str], None], on_fail: Callable[[str], None], log):
        self.pending: Dict[str, Dict] = {}
        self.resend_fn = resend_fn
        self.on_fail = on_fail
        self.log = log
        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def track(self, message_id: str):
        self.pending[message_id] = {"retries": 0, "next_due": time.time() + ACK_TIMEOUT_SEC}

    def acked(self, message_id: str):
        self.pending.pop(message_id, None)

    def _loop(self):
        while self.running:
            now = time.time()
            for mid, st in list(self.pending.items()):
                if now >= st["next_due"]:
                    if st["retries"] >= ACK_MAX_RETRIES:
                        self.log.warn(f"ACK failed after retries for MESSAGE_ID={mid}")
                        self.pending.pop(mid, None)
                        self.on_fail(mid)
                        continue
                    st["retries"] += 1
                    st["next_due"] = now + ACK_TIMEOUT_SEC
                    self.log.info(f"Retry {st['retries']} for MESSAGE_ID={mid}")
                    try:
                        self.resend_fn(mid)
                    except Exception as e:
                        self.log.error(f"Resend error for {mid}: {e}")
            time.sleep(0.1)

    def stop(self):
        self.running = False
