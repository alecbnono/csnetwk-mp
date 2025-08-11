from typing import Dict, Tuple
from .messages import build_message, new_message_id
from .tokens import make_token, validate_token
from .utils import now_ts

WIN_LINES = [
    (0,1,2),(3,4,5),(6,7,8),
    (0,3,6),(1,4,7),(2,5,8),
    (0,4,8),(2,4,6)
]

def render_board(board: str) -> str:
    cells = [c if c in ("X","O") else " " for c in board]
    row = lambda a,b,c: f" {cells[a]} | {cells[b]} | {cells[c]} "
    sep = "\n-----------\n"
    return row(0,1,2) + sep + row(3,4,5) + sep + row(6,7,8)

class TicTacToe:
    """
    Stateless wire, stateful local: we maintain game per GAMEID.
    Duplicate detection: (GAMEID, TURN).
    """
    def __init__(self, user_id: str, tx, peers, ack_mgr, log, loss_scope="game"):
        self.user_id = user_id
        self.tx = tx
        self.peers = peers
        self.ack_mgr = ack_mgr
        self.log = log
        self.loss_scope = loss_scope
        # GAMEID -> {board:str(9), next_turn:int, my_symbol:str, opp_symbol:str, last_turn_seen:int, opponent:str}
        self.games: Dict[str, Dict] = {}
        # resend builders
        self._resenders: Dict[str, callable] = {}

    def _send_and_track(self, ip, port, msg_dict):
        if "MESSAGE_ID" not in msg_dict:
            msg_dict["MESSAGE_ID"] = new_message_id()
        mid = msg_dict["MESSAGE_ID"]
        raw = build_message(msg_dict)

        # remember how to resend this exact message
        self._resenders[mid] = lambda: self.tx.send_unicast(ip, port, build_message(msg_dict), drop_for=self.loss_scope)

        # self.tx.send_unicast(ip, raw, drop_for=self.loss_scope)
        # fix: include port in send_unicast
        self.tx.send_unicast(ip, port, raw, drop_for=self.loss_scope)

        self.ack_mgr.track(mid)

    def invite(self, to_user: str, gameid: str, symbol: str, ttl=3600):
        # ip = self.peers.address_of(to_user)
        # fix: use endpoint_of to get both ip and port
        ip, port = self.peers.endpoint_of(to_user)

        tok = make_token(self.user_id, now_ts() + ttl, "game")
        msg = {
            "TYPE": "TICTACTOE_INVITE",
            "FROM": self.user_id,
            "TO": to_user,
            "GAMEID": gameid,
            "SYMBOL": symbol,
            "TIMESTAMP": str(now_ts()),
            "TOKEN": tok
        }
        self._send_and_track(ip, port, msg)

    def move(self, to_user: str, gameid: str, position: int, symbol: str, turn: int, ttl=3600):
        # ip = self.peers.address_of(to_user)
        # fix: use endpoint_of to get both ip and port
        ip, port = self.peers.endpoint_of(to_user)

        tok = make_token(self.user_id, now_ts() + ttl, "game")
        msg = {
            "TYPE": "TICTACTOE_MOVE",
            "FROM": self.user_id,
            "TO": to_user,
            "GAMEID": gameid,
            "POSITION": str(position),
            "SYMBOL": symbol,
            "TURN": str(turn),
            "TOKEN": tok
        }
        self._send_and_track(ip, port, msg)

    # ---------- receiver side ----------
    def on_invite(self, msg: Dict[str, str], addr_ip: str):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "game", sender):
            return
        gid = msg.get("GAMEID","")
        symbol = msg.get("SYMBOL","X")
        opp_symbol = "O" if symbol == "X" else "X"
        self.games[gid] = {
            "board": " "*9,
            "next_turn": 1,
            "my_symbol": opp_symbol,
            "opp_symbol": symbol,
            "last_turn_seen": 0,
            "opponent": sender
        }
        print(f"{sender.split('@')[0]} is inviting you to play tic-tac-toe.")

    def on_move(self, msg: Dict[str, str], addr_ip: str):
        sender = msg.get("FROM","")
        if not validate_token(msg.get("TOKEN",""), "game", sender):
            return
        gid = msg.get("GAMEID","")
        st = self.games.setdefault(gid, {
            "board":" "*9, "next_turn":1, "my_symbol":"O","opp_symbol":"X","last_turn_seen":0,"opponent":sender
        })
        pos = int(msg.get("POSITION","0"))
        sym = msg.get("SYMBOL","X")
        turn = int(msg.get("TURN","1"))

        # duplicate detection (idempotent): ack but ignore if same turn already processed
        if turn <= st["last_turn_seen"]:
            # still print board (non-verbose spec: "Print the board.")
            print(render_board(st["board"]))
            return

        if pos < 0 or pos > 8: return
        b = list(st["board"])
        if b[pos] in ("X","O"):
            # conflict: ignore
            return
        b[pos] = sym
        st["board"] = "".join(b)
        st["last_turn_seen"] = turn
        st["next_turn"] = turn + 1

        print(render_board(st["board"]))
        # check win/draw
        res, line = self._result(st["board"])
        if res:
            self._send_result(sender, gid, res, sym, line)

    def _result(self, board: str) -> Tuple[str, str]:
        for a,b,c in WIN_LINES:
            if board[a] != " " and board[a] == board[b] == board[c]:
                return "WIN", f"{a},{b},{c}"
        if " " not in board:
            return "DRAW", ""
        return "", ""

    def _send_result(self, to_user: str, gid: str, result: str, symbol: str, line: str):
        # ip = self.peers.address_of(to_user)
        # fix: use endpoint_of to get both ip and port
        ip, port = self.peers.endpoint_of(to_user)

        msg = {
            "TYPE": "TICTACTOE_RESULT",
            "FROM": self.user_id,
            "TO": to_user,
            "GAMEID": gid,
            "RESULT": result,
            "SYMBOL": symbol,
            "WINNING_LINE": line,
            "TIMESTAMP": str(now_ts())
        }
        self.tx.send_unicast(ip, port, build_message(msg), drop_for=self.loss_scope)