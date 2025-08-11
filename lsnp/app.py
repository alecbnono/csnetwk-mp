import threading
import argparse
from typing import Tuple, Dict
from .constants import DEFAULT_PORT, DEFAULT_DISPLAY_NAME, SUPPRESS_TYPES, ACK_TRACKED_TYPES, AUTO_ACK_IF_MESSAGE_ID
from .utils import get_local_ip, make_user_id, compute_broadcast, ip_from_user_id, now_ts
from .transport import Transport
from .logger import VerboseLogger
from .messages import parse_message, build_message, new_message_id, needs_ack
from .tokens import make_token, validate_token, revoke_token
from .peers import PeerDirectory
from .ack import AckManager
from .discovery import Discovery
from .file_transfer import FileTransfers
from .groups import GroupState
from .game import TicTacToe, render_board
from .cli import register_cli

class App:
    def __init__(self, args):
        self.verbose = args.verbose
        self.port = args.port
        self.loss_prob = args.loss
        self.ttl = args.ttl
        self.display_name = args.name or DEFAULT_DISPLAY_NAME

        # self.local_ip = get_local_ip()
        #fix: determine IP / user_id
        self.local_ip = get_local_ip()
        # if args.loopback or self.local_ip.startswith("127."):
        #     self.local_ip = "127.0.0.1"

        #fix of fix: if loopback mode, set local_ip to 127 localhost
        self.loopback_mode = bool(args.loopback or self.local_ip.startswith("127."))
        if self.loopback_mode:
            self.local_ip = "127.0.0.1"            

        self.user_id = make_user_id(self.display_name, self.local_ip)
        self.broadcast_ip = compute_broadcast(self.local_ip)

        self.log = VerboseLogger(self.verbose)
        self.tx = Transport(self.port, self.log, loss_prob=self.loss_prob)
        self.peers = PeerDirectory()
        self.groups = GroupState()

        #fix: add local state (follows and likes)
        self.following = set()
        self.followers = set()
        self.sent_likes = set()       # {(to_uid, post_ts)} – to avoid re-sending duplicates via CLI
        self._likes_by_post = {}      # post_ts -> set(user_ids) who like my post


        # ACK manager; wire resend by message_id from our resend cache
        self._resend_cache: Dict[str, Dict] = {}  # mid -> {ip, msg_dict, scope}
        def resend(mid: str):
            ent = self._resend_cache.get(mid)
            # if not ent: return
            # # ip, msg, scope = ent["ip"], ent["msg"], ent["scope"]
            # # self.tx.send_unicast(ip, build_message(msg), drop_for=("game" if msg["TYPE"].startswith("TICTACTOE") else "file" if msg["TYPE"].startswith("FILE_") else ""))

            # #fix: include port in resend cache            
            # ip, port, msg, scope = ent["ip"], ent["port"], ent["msg"], ent["scope"]
            # kind = "game" if msg["TYPE"].startswith("TICTACTOE") else "file" if msg["TYPE"].startswith("FILE_") else ""
            # self.tx.send_unicast(ip, port, build_message(msg), drop_for=kind)

            #fix: ack retries dont actually resend game messages/file messages
            if ent:
                ip, port, msg, scope = ent["ip"], ent["port"], ent["msg"], ent["scope"]
                kind = "game" if msg["TYPE"].startswith("TICTACTOE") else "file" if msg["TYPE"].startswith("FILE_") else ""
                self.tx.send_unicast(ip, port, build_message(msg), drop_for=kind)
                return
            cb = self.files._resenders.get(mid) or self.game._resenders.get(mid)
            if cb:
                try: cb()
                except Exception as e: self.log.error(f"Resend error for {mid}: {e}")



        def on_fail(mid: str):
            # nothing special; already logged
            pass

        self.ack_mgr = AckManager(resend_fn=resend, on_fail=on_fail, log=self.log)
        self.files = FileTransfers(self.user_id, self.tx, self.peers, self.ack_mgr, self.log)
        self.game = TicTacToe(self.user_id, self.tx, self.peers, self.ack_mgr, self.log)

        register_cli(self)  # installs self.commands

        # discovery
        self.discovery = Discovery(
            self.user_id, 
            self.display_name, 
            self.tx, 
            self.broadcast_ip,
            self.log, 
            include_multicast=True, 

            #fix: added loopback mode
            loopback_mode=(self.local_ip == "127.0.0.1")
        )


        # start receiver loop
        self.tx.loop(self._on_packet)

    # ---- sending with ACK tracking ----
    def _send_with_ack(self, ip: str, port: int, msg_dict: Dict[str,str], scope: str = ""):
        if "MESSAGE_ID" not in msg_dict:
            msg_dict["MESSAGE_ID"] = new_message_id()
        mid = msg_dict["MESSAGE_ID"]
        self._resend_cache[mid] = {"ip": ip, "port": port, "msg": dict(msg_dict), "scope": scope}
        raw = build_message(msg_dict)
        kind = "game" if scope=="game" else "file" if scope=="file" else ""
        self.tx.send_unicast(ip, port, raw, drop_for=kind)
        self.ack_mgr.track(mid)

    # ---- packet dispatcher ----
    def _on_packet(self, raw: str, addr: Tuple[str,int]):
        # ip = addr[0]

        #fix: include source port in address tuple
        ip, src_port = addr

        msg = parse_message(raw)
        mtype = msg.get("TYPE","")

        # Security: match IP in FROM/USER_ID if present
        sender_uid = msg.get("FROM") or msg.get("USER_ID") or ""
        if sender_uid:
            declared_ip = ip_from_user_id(sender_uid)
            if declared_ip and declared_ip != ip:
                # self.log.warn(f"IP mismatch: header {declared_ip} vs actual {ip} for TYPE={mtype}")
                # return  # discard per security considerations

                #fix: allow loopback mode to tolerate IP mismatch
                if self.loopback_mode and declared_ip == "127.0.0.1":
                    # Same host, different interface—allowed in loopback tests.
                    self.log.warn(f"Loopback: tolerating IP mismatch (header {declared_ip} vs actual {ip}) for TYPE={mtype}")
                else:
                    self.log.warn(f"IP mismatch: header {declared_ip} vs actual {ip} for TYPE={mtype}")
                    return

        # fix: only ACK if addressed to me, and send to sender's endpoint (ip, port)
        to_uid = msg.get("TO", "")
        addressed_to_me = (not to_uid) or (to_uid == self.user_id)
        if addressed_to_me and msg.get("MESSAGE_ID") and mtype in {"TICTACTOE_INVITE","TICTACTOE_MOVE","FILE_CHUNK","FILE_OFFER","DM"}:
            sender_uid = msg.get("FROM") or msg.get("USER_ID") or ""
            ack_ip, ack_port = self.peers.endpoint_of(sender_uid)
            if not ack_ip:
                ack_ip = ip
            if not ack_port:
                # last resort: reply to the sender's source port we observed
                ack_port = src_port
            ack = build_message({"TYPE": "ACK","MESSAGE_ID": msg["MESSAGE_ID"],"STATUS":"RECEIVED"})
            self.tx.send_unicast(ack_ip, ack_port, ack)

        #fix: bad ack send due to missing port; remove 
        # # auto-ACK on tracked types
        # if AUTO_ACK_IF_MESSAGE_ID and msg.get("MESSAGE_ID") and mtype in ACK_TRACKED_TYPES:
        #     ack = build_message({"TYPE": "ACK", "MESSAGE_ID": msg["MESSAGE_ID"], "STATUS": "RECEIVED"})
        #     self.tx.send_unicast(ip, ack)

        # handle ACK for our pending
        if mtype == "ACK":
            mid = msg.get("MESSAGE_ID")
            if mid:
                self.ack_mgr.acked(mid)
            return

        #fix: dont call pretty_print for stateful types
        # Only pretty print simple, stateless stuff
        if mtype not in SUPPRESS_TYPES and mtype in {"PROFILE"}:
            self._pretty_print(msg)


        # fix: call handler with (msg, ip, src_port) when possible
        handler = getattr(self, f"_on_{mtype}", None)
        if handler:
            try:
                handler(msg, ip, src_port)   # new signature
            except TypeError:
                handler(msg, ip)             # backwards-compat

    # ---- non-verbose pretty printing ----
    #fix: proper formatting of displayed texts
    #fix2: runs before handlers, so seeing things twice; cant de-dupe
    def _pretty_print(self, msg: Dict[str,str]):
        t = msg.get("TYPE","").upper()

        # def hr(txt=""):
        #     if txt:
        #         print("\n" + txt)
        #     print("-" * 48)

        if t == "PROFILE":
            name = msg.get("DISPLAY_NAME") or msg.get("USER_ID","")
            st = msg.get("STATUS","")
            print(f"\n[{name}] {st}")
            return

    # ---- per-type handlers ----
    def _on_PROFILE(self, msg, ip, src_port):
        # self.peers.upsert_from_profile(msg, ip)

        #fix: include source port in peer profile
        self.peers.upsert_from_profile(msg, ip, src_port)

    def _on_PING(self, msg, ip, src_port=None):
        prof = build_message({
            "TYPE": "PROFILE",
            "USER_ID": self.user_id,
            "DISPLAY_NAME": self.display_name,
            "STATUS": "Exploring LSNP!",
            "PORT": str(self.tx.listen_port()),
        })
        self.tx.send_broadcast(self.broadcast_ip, prof)
        self.tx.send_multicast(prof)

    #fix: print dm only after validation
    def _on_DM(self, msg, ip):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "chat", sender):
            self.log.warn("Rejected DM due to invalid token")
            return
        dn = (self.peers.get(sender) or {}).get("display_name") or sender
        content = msg.get("CONTENT","")
        print("\n✉️  DIRECT MESSAGE")
        print("-" * 48)
        print(f"From: {dn} ({sender})\n")
        print(content)
        print("-" * 48)


    #fix: show only if it's mine or I follow the author
    def _on_POST(self, msg, ip):
        uid = msg.get("USER_ID","")
        token = msg.get("TOKEN","")
        if not validate_token(token, "broadcast", uid):
            self.log.warn("Rejected POST due to invalid token")
            return
        ts = int(msg.get("TIMESTAMP","0") or "0")
        ttl = int(msg.get("TTL","0") or "0") or self.ttl
        if now_ts() > ts + ttl:
            self.log.warn("Rejected POST due to TTL expiry")
            return

        # show only if it's mine or I follow the author
        if uid != self.user_id and uid not in self.following:
            return

        dn = (self.peers.get(uid) or {}).get("display_name") or uid
        content = msg.get("CONTENT","")

        print("\n📣 POST")
        print("-" * 48)
        print(f"From: {dn} ({uid})\n")
        print(content)
        print("-" * 48)


    def _on_FOLLOW(self, msg, ip):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "follow", sender):
            self.log.warn("Rejected FOLLOW due to invalid token")
            return
        if sender in self.followers:
            return  # already following you; ignore duplicate
        self.followers.add(sender)
        print(f"\n💖  {sender.split('@')[0]} followed you")

    def _on_UNFOLLOW(self, msg, ip):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "follow", sender):
            self.log.warn("Rejected UNFOLLOW due to invalid token")
            return
        if sender not in self.followers:
            return  # already not following; ignore duplicate
        self.followers.discard(sender)
        print(f"\n💔  {sender.split('@')[0]} unfollowed you")

    #fix: do validation + de-dupe and print only when the state 
    def _on_LIKE(self, msg, ip):
        sender = msg.get("FROM","")
        to = msg.get("TO","")
        if not validate_token(msg.get("TOKEN",""), "broadcast", sender):
            self.log.warn("Rejected LIKE due to invalid token")
            return
        if to != self.user_id:
            return  # not for me

        post_ts = msg.get("POST_TIMESTAMP","")
        action = (msg.get("ACTION","LIKE") or "LIKE").upper()
        liked = self._likes_by_post.setdefault(post_ts, set())

        if action == "LIKE":
            if sender in liked:
                return  # duplicate
            liked.add(sender)
            print(f"\n👍  {sender.split('@')[0]} likes your post [{post_ts}]")
        else:  # UNLIKE
            if sender not in liked:
                return
            liked.discard(sender)
            print(f"\n👎  {sender.split('@')[0]} unliked your post [{post_ts}]")

    def _on_FILE_OFFER(self, msg, ip):
        self.files.on_offer(msg, ip)

    def _on_FILE_CHUNK(self, msg, ip):
        self.files.on_chunk(msg, ip)

    def _on_FILE_RECEIVED(self, msg, ip): pass

    def _on_REVOKE(self, msg, ip, src_port=None):
        tok = msg.get("TOKEN","")
        if tok:
            revoke_token(tok)

    def _on_GROUP_CREATE(self, msg, ip, src_port=None):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "group", sender):
            self.log.warn("Rejected GROUP_CREATE due to invalid token"); return
        members = [m.strip() for m in (msg.get("MEMBERS","").split(",") if msg.get("MEMBERS") else []) if m.strip()]
        gid = msg.get("GROUP_ID","")
        gname = msg.get("GROUP_NAME", gid)
        self.groups.create(gid, gname, members)
        creator = (sender.split("@")[0] or "Someone")
        print(f'\n🫂  Added to group "{gname}" (id={gid}) by {creator}. Members: {", ".join(members) if members else "(none)"}')

    def _on_GROUP_UPDATE(self, msg, ip, src_port=None):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "group", sender):
            self.log.warn("Rejected GROUP_UPDATE due to invalid token"); return
        gid = msg.get("GROUP_ID","")
        add = [s.strip() for s in (msg.get("ADD","").split(",") if msg.get("ADD") else []) if s.strip()]
        rem = [s.strip() for s in (msg.get("REMOVE","").split(",") if msg.get("REMOVE") else []) if s.strip()]
        self.groups.update(gid, add, rem)
        gname = self.groups.name_of(gid)
        print(f'\n❕  The group "{gname}" member list was updated.')

    def _on_GROUP_MESSAGE(self, msg, ip, src_port=None):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "group", sender):
            self.log.warn("Rejected GROUP_MESSAGE due to invalid token"); return
        gid = msg.get("GROUP_ID","")
        gname = self.groups.name_of(gid)
        fr = sender.split("@")[0]
        text = msg.get("CONTENT","")
        print(f'\n📩  [{gname}] {fr}: {text}')

    def _on_TICTACTOE_INVITE(self, msg, ip):
        self.game.on_invite(msg, ip)

    def _on_TICTACTOE_MOVE(self, msg, ip):
        self.game.on_move(msg, ip)

    def _on_TICTACTOE_RESULT(self, msg, ip, src_port=None):
        gid = msg.get("GAMEID","")
        st = self.game.games.get(gid, {"board": " "*9})
        print("\n" + render_board(st.get("board"," "*9)))
        result = msg.get("RESULT","").upper()
        sym = msg.get("SYMBOL","")
        line = msg.get("WINNING_LINE","")
        if result:
            extra = f" (line {line})" if line else ""
            print(f"Game over: {result} as {sym}{extra}")

    # ---- main loop (CLI) ----
    def run(self):
        print(f"{self.display_name} running as {self.user_id} on {self.local_ip}:{self.port}")
        print("Type 'help' for commands. Ctrl+C to quit.")
        while True:
            try:
                line = input("> ").strip()
                print(f"\n▶︎ CMD: {line}")

            except (EOFError, KeyboardInterrupt):
                print("\nShutting down...")
                break
            if not line: continue
            if line.lower() in ("quit","exit"): break

            #fix: proper formatting of displayed texts
            if line.lower() == "help":
                cmds = [
                    ("peers",                      "List known peers"),
                    ("post <msg>",                 "Broadcast a post"),
                    ("dm <user_id> <msg>",         "Send a direct message"),
                    ("follow <user_id>",           "Follow a user"),
                    ("unfollow <user_id>",         "Unfollow a user"),
                    ("like <user_id> <ts> [UNLIKE]","Like/unlike a post"),
                    ('group_create <id> "<name>" a,b', "Create a group"),
                    ("group_update <id> add=a,b remove=c", "Modify group members"),
                    ("group_msg <id> <text>",      "Send a group message"),
                    ("file_send <user_id> <path>", "Send a file"),
                    ("accept <fileid>",            "Accept incoming file"),
                    ("ignore <fileid>",            "Ignore incoming file"),
                    ("revoke <token>",             "Revoke a token"),
                    ("ttt_invite <user> [X|O] [gameid]", "Invite to Tic-Tac-Toe"),
                    ("ttt_move <user> <gid> <pos> <turn> <symbol>", "Make a move"),
                    ("verbose <on/off>",           "Toggle verbose logs"),
                    ("help",                       "Show this help"),
                    ("exit / quit",                "Quit"),
                ]
                w = max(len(c[0]) for c in cmds)
                print("\nCommands:")
                for k, desc in cmds:
                    print(f"  {k:<{w}}  {desc}")
                print()
                continue

            cmd, *rest = line.split(" ", 1)
            args = rest[0] if rest else ""
            fn = self.commands.get(cmd.lower())
            if fn:
                try:
                    fn(args)
                except Exception as e:
                    self.log.error(f"Command error: {e}")
            else:
                print(f"Unknown command: {cmd}")

def main(argv=None):
    p = argparse.ArgumentParser(description="LSNP peer")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--name", type=str, default=DEFAULT_DISPLAY_NAME)
    p.add_argument("--ttl", type=int, default=3600, help="default token TTL seconds")
    p.add_argument("--loss", type=float, default=0.0, help="induced packet loss probability (0..1) for game/file")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--loopback", action="store_true", help="force single-machine loopback testing (user_id uses 127.0.0.1)")
    args = p.parse_args(argv)
    app = App(args)
    app.run()

if __name__ == "__main__":
    main()
