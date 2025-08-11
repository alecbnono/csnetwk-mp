import os
import base64
from typing import Dict
from .messages import build_message, default_post_fields, new_message_id
from .tokens import make_token, validate_token, revoke_token
from .utils import now_ts
from .constants import DEFAULT_TTL_SEC

def register_cli(app):  # app exposes: tx, peers, files, game, groups, log, user_id, display_name, ttl, loss_prob
    def _send_broadcast(msg_fields: Dict[str,str]):
        raw = build_message(msg_fields)
        app.tx.send_broadcast(app.broadcast_ip, raw)
        app.tx.send_multicast(raw)

    def cmd_peers(args: str):
        peers = app.peers.list()
        if not peers:
            print("No peers discovered yet.")
            return

        # build rows
        rows = []
        for uid, d in sorted(peers.items(), key=lambda kv: kv[1].get("display_name","").lower()):
            ep = f"{d.get('address','?')}:{d.get('port','?')}"
            rows.append([d.get("display_name", uid), uid, ep, d.get("status","")])

        headers = ["Name", "User ID", "Endpoint", "Status"]
        widths = [max(len(str(x[i])) for x in ([headers] + rows)) for i in range(len(headers))]
        fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
        sep = "  ".join("-" * w for w in widths)

        print("\nKnown Peers")
        print(sep)
        print(fmt.format(*headers))
        print(sep)
        for r in rows:
            print(fmt.format(*r))
        print(sep)

    def cmd_post(args: str):
        content = args.strip()
        if not content:
            print("Usage: post <message>")
            return

        f = default_post_fields(app.user_id, content, ttl=app.ttl)
        f["TOKEN"] = make_token(app.user_id, now_ts()+app.ttl, "broadcast")

        followers = list(app.followers)  # people who followed me
        if not followers:
            #fix: send both broadcast and multicast
                #fallback for solo demo
            _send_broadcast(f) # sends broadcast + multicast
        else:
            raw = build_message(f)
            for m in followers:
                ip, port = app.peers.endpoint_of(m)
                if not ip or not port:
                    continue
                app.tx.send_unicast(ip, port, raw)
        print("Post sent.")

    def cmd_dm(args: str):
        parts = args.split(" ", 1)
        if len(parts) < 2:
            print("Usage: dm <user_id> <message>")
            return
        to, content = parts[0], parts[1]
        # ip = app.peers.address_of(to)

        #fix: use endpoint_of to get both ip and port
        ip, port = app.peers.endpoint_of(to)
        if not ip or not port:
            print("Don't know where to send that yet. Try 'peers' and wait for PROFILEs.")
            return

        ts = now_ts()
        msg = {
            "TYPE": "DM",
            "FROM": app.user_id,
            "TO": to,
            "CONTENT": content,
            "TIMESTAMP": str(ts),
            "MESSAGE_ID": new_message_id(),
            "TOKEN": make_token(app.user_id, ts+app.ttl, "chat")
        }
        
        # app._send_with_ack(ip, msg, scope="chat")

        #fix: include port in send_with_ack
        app._send_with_ack(ip, port, msg, scope="chat")

        print(f"DM sent to {to}.")

    #fix: idempotent FOLLOW / UNFOLLOW (no ACKs, no spam)    
    def cmd_follow(args: str, type_="FOLLOW"):
        to = args.strip()
        if not to:
            print(f"Usage: {type_.lower()} <user_id>")
            return
        ip, port = app.peers.endpoint_of(to)
        if not ip or not port:
            print("Don't know where to send that yet. Try 'peers' and wait for PROFILEs.")
            return

        # Local gating
        if type_ == "FOLLOW" and to in app.following:
            print(f"You're already following {to}.")
            return
        if type_ == "UNFOLLOW" and to not in app.following:
            print(f"You're not following {to}.")
            return

        ts = now_ts()
        msg = {
            "TYPE": type_,
            "MESSAGE_ID": new_message_id(),
            "FROM": app.user_id,
            "TO": to,
            "TIMESTAMP": str(ts),
            "TOKEN": make_token(app.user_id, ts+app.ttl, "follow")
        }

        # Send WITHOUT ack tracking (no retries/spam)
        app.tx.send_unicast(ip, port, build_message(msg))

        # Optimistic local state update
        if type_ == "FOLLOW":
            app.following.add(to)
        else:
            app.following.discard(to)

        print(f"{type_.title()} sent to {to}.")

    #fix: idempotent LIKE / UNLIKE
    def cmd_like(args: str):
        parts = args.split(" ", 2)
        if len(parts) < 2:
            print("Usage: like <user_id> <post_timestamp> [UNLIKE]")
            return
        to = parts[0]; post_ts = parts[1]; action = parts[2].upper() if len(parts) > 2 else "LIKE"

        ip, port = app.peers.endpoint_of(to)
        if not ip or not port:
            print("Don't know where to send that yet. Try 'peers' and wait for PROFILEs.")
            return

        key = (to, post_ts)
        if action == "LIKE" and key in app.sent_likes:
            print("You already liked that post.")
            return
        if action == "UNLIKE" and key not in app.sent_likes:
            print("You haven't liked that post yet.")
            return

        ts = now_ts()
        msg = {
            "TYPE": "LIKE",
            "FROM": app.user_id,
            "TO": to,
            "POST_TIMESTAMP": post_ts,
            "ACTION": action,
            "TIMESTAMP": str(ts),
            "TOKEN": make_token(app.user_id, ts+app.ttl, "broadcast")
        }
        app.tx.send_unicast(ip, port, build_message(msg))

        # optimistic local mark
        if action == "LIKE":
            app.sent_likes.add(key)
        else:
            app.sent_likes.discard(key)

        print(f"{action} sent to {to} for post {post_ts}.")


    def cmd_group_create(args: str):
        # group_create <group_id> "<group name>" <comma_members>
        try:
            group_id, rest = args.split(" ", 1)
            if rest.strip().startswith('"'):
                name = rest.strip().split('"')[1]
                after = rest.strip().split('"',2)[2].strip()
            else:
                name, after = group_id, rest
            
            #update local state, including self
            members = [m.strip() for m in after.split(",") if m.strip()]
            local_members = sorted(set(members + [app.user_id]))
            app.groups.create(group_id, name, local_members)
        except Exception:
            print('Usage: group_create <group_id> "<group name>" member1,member2')
            return
        ts = now_ts()
        msg = {
            "TYPE": "GROUP_CREATE",
            "FROM": app.user_id,
            "GROUP_ID": group_id,
            "GROUP_NAME": name,
            "MEMBERS": ",".join(members),
            "TIMESTAMP": str(ts),
            "TOKEN": make_token(app.user_id, ts+app.ttl, "group")
        }
        
        #fix: send to OTHER members only, not self
        for m in members:
            ip, port = app.peers.endpoint_of(m)
            if not ip or not port:
                print(f"Don't know where to send group creation to {m}. Try 'peers' and wait for PROFILEs.")
                continue
            app.tx.send_unicast(ip, port, build_message(msg))
        print("\n🟧 GROUP • CREATE")
        print("────────────────────────────────────────────────")
        print(f'ID: {group_id}')
        print(f'Name: {name}')
        print(f'Members: {", ".join(members) if members else "(none)"}')
        print("Result: created locally and notified members.\n")

    def cmd_group_update(args: str):
        # group_update <group_id> add=a,b remove=c
        try:
            parts = args.split()
            group_id = parts[0]
            add = []; remove = []
            for p in parts[1:]:
                if p.startswith("add="):
                    add = [x.strip() for x in p[4:].split(",") if x.strip()]
                elif p.startswith("remove="):
                    remove = [x.strip() for x in p[7:].split(",") if x.strip()]
        except Exception:
            print('Usage: group_update <group_id> add=a,b remove=c')
            return
        ts = now_ts()
        msg = {
            "TYPE": "GROUP_UPDATE",
            "FROM": app.user_id,
            "GROUP_ID": group_id,
            "ADD": ",".join(add),
            "REMOVE": ",".join(remove),
            "TIMESTAMP": str(ts),
            "TOKEN": make_token(app.user_id, ts+app.ttl, "group")
        }
        app.groups.update(group_id, add, remove)

        #fix: notify everyone we currently in the group
        for m in app.groups.members(group_id):
            ip, port = app.peers.endpoint_of(m)
            if not ip or not port:
                print(f"Don't know where to send group update to {m}. Try 'peers' and wait for PROFILEs.")
                continue
            app.tx.send_unicast(ip, port, build_message(msg))
        print(f'Group "{app.groups.name_of(group_id)}" member list updated.')

    def cmd_group_msg(args: str):
        # group_msg <group_id> <text...>
        parts = args.split(" ", 1)
        if len(parts) < 2:
            print("Usage: group_msg <group_id> <message>")
            return
        group_id, content = parts[0], parts[1]
        ts = now_ts()
        msg = {
            "TYPE": "GROUP_MESSAGE",
            "FROM": app.user_id,
            "GROUP_ID": group_id,
            "CONTENT": content,
            "TIMESTAMP": str(ts),
            "TOKEN": make_token(app.user_id, ts+app.ttl, "group")
        }

        #fix: warn if the group has no known members
        recips = [m for m in app.groups.members(group_id) if m != app.user_id]
        if not recips:
            print(f'No known members for group "{group_id}".')
            return
        for m in recips:
            if m == app.user_id: continue
            # ip = app.peers.address_of(m)
            # app.tx.send_unicast(ip, build_message(msg))

            #fix: use endpoint_of to get both ip and port
            ip, port = app.peers.endpoint_of(m)
            if not ip or not port:
                print(f"Don't know where to send group creation to {m}. Try 'peers' and wait for PROFILEs.")
                continue
            app.tx.send_unicast(ip, port, build_message(msg))
            
        print("\n👥 GROUP • MESSAGE")
        print("────────────────────────────────────────────────")
        print(f'Group: {group_id}')
        print(f'Text: {content}')
        print("Result: delivered to members (UDP best effort).\n")

    def cmd_file_send(args: str):
        # file_send <user_id> <path>
        parts = args.split(" ", 1)
        if len(parts) < 2:
            print("Usage: file_send <user_id> <path>")
            return
        to, path = parts[0], parts[1]

        path = path.strip().strip('"').strip("'")
        if not os.path.isfile(path):
            # helpful fallback to a common folder
            alt = os.path.join("client-files", os.path.basename(path))
            if os.path.isfile(alt):
                path = alt
            else:
                print(f"File not found: {path}")
                return

        if not os.path.isfile(path):
            print(f"File not found: {path}")
            return
        data = open(path, "rb").read()
        filesize = len(data)
        fileid = new_message_id()[:8]
        fname = os.path.basename(path)
        app.files.send_offer(to, fileid, fname, filesize, "application/octet-stream", "File via LSNP", ttl=app.ttl)
        # chunking
        # chunk_size = 1024 * 8

        #fix: use a smaller chunk size to avoid fragmentation issues
            # ~1200B payload keeps UDP datagrams well under typical MTU 1500 after headers
        chunk_size = 1200

        chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
        total = len(chunks)
        for i, ch in enumerate(chunks):
            app.files.send_chunk(to, fileid, i, total, ch, chunk_size, ttl=app.ttl)

    def cmd_accept(args: str):
        fileid = args.strip()
        if not fileid:
            print("Usage: accept <FILEID>")
            return
        app.files.accept(fileid)

    def cmd_ignore(args: str):
        fileid = args.strip()
        if not fileid:
            print("Usage: ignore <FILEID>")
            return
        app.files.ignore(fileid)

    def cmd_revoke(args: str):
        token = args.strip()
        if not token:
            print("Usage: revoke <token>")
            return
        revoke_token(token)
        print("Token revoked.")

    def cmd_ttt_invite(args: str):
        # ttt_invite <user_id> [X|O] [gameid]
        parts = args.split()
        if not parts:
            print("Usage: ttt_invite <user_id> [X|O] [gameid]")
            return
        to = parts[0]
        symbol = parts[1].upper() if len(parts) > 1 else "X"
        gameid = parts[2] if len(parts) > 2 else f"g{new_message_id()[:2]}"
        app.game.invite(to, gameid, symbol, ttl=app.ttl)

    def cmd_ttt_move(args: str):
        # ttt_move <user_id> <gameid> <pos> <turn> <symbol>
        parts = args.split()
        if len(parts) < 5:
            print("Usage: ttt_move <user_id> <gameid> <pos> <turn> <symbol>")
            return
        to, gid, pos, turn, sym = parts[0], parts[1], int(parts[2]), int(parts[3]), parts[4].upper()
        app.game.move(to, gid, pos, sym, turn, ttl=app.ttl)

    def cmd_verbose(args: str):
        v = args.strip().lower() in ("1", "true", "yes", "on")
        app.log.set_verbose(v)
        print(f"Verbose set to {v}")

    app.commands = {
        "peers": cmd_peers,
        "post": cmd_post,
        "dm": cmd_dm,
        "follow": lambda a: cmd_follow(a, "FOLLOW"),
        "unfollow": lambda a: cmd_follow(a, "UNFOLLOW"),
        "like": cmd_like,
        "group_create": cmd_group_create,
        "group_update": cmd_group_update,
        "group_msg": cmd_group_msg,
        "file_send": cmd_file_send,
        "accept": cmd_accept,
        "ignore": cmd_ignore,
        "revoke": cmd_revoke,
        "ttt_invite": cmd_ttt_invite,
        "ttt_move": cmd_ttt_move,
        "verbose": cmd_verbose,
    }
