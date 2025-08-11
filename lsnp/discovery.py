import threading
import time
from .messages import build_message
from .constants import DISCOVERY_INTERVAL_SEC
from .utils import now_ts

class Discovery:
    def __init__(self, user_id: str, display_name: str, tx, bcast_ip: str, log, include_multicast=True, loopback_mode=False):
        self.user_id = user_id
        self.display_name = display_name
        self.tx = tx
        self.bcast_ip = bcast_ip
        self.log = log
        self.include_multicast = include_multicast

        #fix: include loopback parameter
        self.loopback_mode = loopback_mode

        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self.running:
            self.send_ping_and_profile()
            time.sleep(DISCOVERY_INTERVAL_SEC)

    def send_ping_and_profile(self):
        ping = build_message({
            "TYPE": "PING",
            "USER_ID": self.user_id
        })
        prof = build_message({
            "TYPE": "PROFILE",
            "USER_ID": self.user_id,
            "DISPLAY_NAME": self.display_name,
            "STATUS": "Exploring LSNP!",
            "PORT": str(self.tx.listen_port()),   #fix: add port to profile message
        })

        self.tx.send_broadcast(self.bcast_ip, ping)
        self.tx.send_broadcast(self.bcast_ip, prof)
        if self.include_multicast:
            self.tx.send_multicast(ping)
            self.tx.send_multicast(prof)
        
        #debugging: when in loopback-only, also poke localhost to ensure both local processes get it
        # if self.loopback_mode:
        #     self.tx.send_unicast("127.0.0.1", ping)
        #     self.tx.send_unicast("127.0.0.1", prof)

    def stop(self):
        self.running = False
