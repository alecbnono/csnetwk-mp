# import socket
# import random
# import threading
# from typing import Callable, Tuple
# from .constants import DEFAULT_PORT, BUFFER_SIZE, DEFAULT_LOSS_PROB, MULTICAST_GRP
# from .logger import VerboseLogger
# from .utils import join_multicast

# class Transport:
#     def __init__(self, port: int, logger: VerboseLogger, loss_prob: float = DEFAULT_LOSS_PROB):
#         self.port = port
#         self.log = logger
#         self.loss_prob = max(0.0, min(1.0, loss_prob))

#         # Single RX socket for everything (unicast/broadcast/multicast)
#         self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
#         self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         # On macOS/Linux this lets multiple processes share the same UDP port (optional)
#         try:
#             self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
#         except AttributeError:
#             pass  # not available on some platforms

#         try:
#             self.sock.bind(("", port))
#         except OSError as e:
#             self.log.error(f"Bind failed on UDP {port}: {e}")
#             raise

#         # Join multicast on the same socket (best-effort)
#         try:
#             join_multicast(self.sock, MULTICAST_GRP, port)
#         except Exception as e:
#             self.log.warn(f"Multicast join failed: {e}")

#         self.running = False

#     def send_unicast(self, ip: str, data: str, drop_for: str = ""):
#         if self._should_drop(drop_for):
#             self.log.drop(f"Simulated drop (unicast to {ip}) for '{drop_for}'")
#             return
#         with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
#             s.sendto(data.encode("utf-8"), (ip, self.port))
#         self.log.send(data.strip())

#     def send_broadcast(self, bcast_ip: str, data: str):
#         with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
#             s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
#             s.sendto(data.encode("utf-8"), (bcast_ip, self.port))
#         self.log.send(data.strip())

#     def send_multicast(self, data: str):
#         with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
#             # s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)

#             #fix: ensure local machine receives our multicast too
#             s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)

#             s.sendto(data.encode("utf-8"), (MULTICAST_GRP, self.port))
#         self.log.send(data.strip())

#     def _should_drop(self, drop_for: str) -> bool:
#         # Only drop for game/file paths
#         if drop_for in ("game", "file"):
#             return random.random() < self.loss_prob
#         return False

#     def loop(self, handler: Callable[[str, Tuple[str,int]], None]):
#         self.running = True

#         def recv_loop(sock):
#             while self.running:
#                 try:
#                     data, addr = sock.recvfrom(BUFFER_SIZE)
#                     txt = data.decode("utf-8", errors="ignore")
#                     self.log.recv(txt.strip())
#                     handler(txt, addr)
#                 except Exception as e:
#                     self.log.error(f"RX error: {e}")

#         threading.Thread(target=recv_loop, args=(self.sock,), daemon=True).start()

#     def stop(self):
#         self.running = False
#         try:
#             self.sock.close()
#         except Exception:
#             pass


import socket
import random
import threading
from typing import Callable, Tuple
from .constants import BUFFER_SIZE, DEFAULT_LOSS_PROB, MULTICAST_GRP, DISCOVERY_PORT
from .logger import VerboseLogger
from .utils import join_multicast

class Transport:
    """
    Two-socket model when needed:
      - uni_sock: bound to this instance's unicast port (unique per process)
      - disc_sock: bound to fixed DISCOVERY_PORT for multicast/broadcast discovery
    If unicast port == DISCOVERY_PORT, we reuse one socket.
    """
    def __init__(self, unicast_port: int, logger: VerboseLogger, loss_prob: float = DEFAULT_LOSS_PROB):
        self.uni_port = unicast_port
        self.log = logger
        self.loss_prob = max(0.0, min(1.0, loss_prob))

        # --- unicast socket (unique per process) ---
        self.uni_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.uni_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.uni_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except Exception:
            pass
        self.uni_sock.bind(("", self.uni_port))

        # --- discovery socket (shared fixed port) ---
        if self.uni_port == DISCOVERY_PORT:
            self.disc_sock = self.uni_sock
        else:
            self.disc_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.disc_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except Exception:
                pass
            self.disc_sock.bind(("", DISCOVERY_PORT))

        # join multicast on discovery socket (best-effort)
        try:
            join_multicast(self.disc_sock, MULTICAST_GRP, DISCOVERY_PORT)
        except Exception as e:
            self.log.warn(f"Multicast join failed: {e}")

        self.running = False

    # convenience for discovery sender to know our port
    def listen_port(self) -> int:
        return self.uni_port

    def send_unicast(self, ip: str, port: int, data: str, drop_for: str = ""):
        if drop_for in ("game", "file") and random.random() < self.loss_prob:
            self.log.drop(f"Simulated drop (unicast to {ip}:{port}) for '{drop_for}'")
            return
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(data.encode("utf-8"), (ip, port))
        self.log.send(data.strip())

    def send_broadcast(self, bcast_ip: str, data: str):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(data.encode("utf-8"), (bcast_ip, DISCOVERY_PORT))
        self.log.send(data.strip())

    def send_multicast(self, data: str):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as s:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
            # loopback so same-host peers receive it too
            s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
            s.sendto(data.encode("utf-8"), (MULTICAST_GRP, DISCOVERY_PORT))
        self.log.send(data.strip())

    def loop(self, handler: Callable[[str, Tuple[str,int]], None]):
        self.running = True

        def recv_loop(sock):
            while self.running:
                try:
                    data, addr = sock.recvfrom(BUFFER_SIZE)
                    txt = data.decode("utf-8", errors="ignore")
                    # self.log.recv(txt.strip())

                    #fix: include address in verbose log
                    self.log.recv(f"{addr[0]}:{addr[1]}\n{txt.strip()}")
                    
                    handler(txt, addr)
                except Exception as e:
                    self.log.error(f"RX error: {e}")

        threading.Thread(target=recv_loop, args=(self.uni_sock,), daemon=True).start()
        if self.disc_sock is not self.uni_sock:
            threading.Thread(target=recv_loop, args=(self.disc_sock,), daemon=True).start()

    def stop(self):
        self.running = False
        try: self.uni_sock.close()
        except: pass
        if self.disc_sock is not self.uni_sock:
            try: self.disc_sock.close()
            except: pass
