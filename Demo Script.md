# 10-minute live demo script

**Prep (before the meeting)**

* Open **3 terminals** in the same machine/LAN.
* Create a tiny file to send: `mkdir -p client-files && echo "hello lsnp" > client-files/hello.txt`
* You’ll substitute the exact `USER_ID`s (printed at startup or via `peers`) in a few commands below.

### 0:00 — 0:45  Start 3 peers (discovery, verbose logs, loss on Alice)

**Terminal A (Alice):**

```bash
python -m lsnp.app --name alice --port 50999 --verbose --loopback --loss 0.30
```

**Terminal B (Bob):**

```bash
python -m lsnp.app --name bob --port 51001 --verbose --loopback
```

**Terminal C (Charlie):**

```bash
python -m lsnp.app --name charlie --port 51002 --verbose --loopback
```

Say: *“We run three peers over UDP. Discovery runs via broadcast + mDNS-style multicast. Verbose mode shows timestamped SEND/RECV/DROP with addresses and the whole message.”*

### 0:45 — 1:40  Discovery & PROFILE

On any terminal:

```
peers
```

Point out that each row came from `PROFILE` (name, status, IP\:PORT). In verbose logs you’ll see PING/PROFILE flowing and the sender `addr:port` printed.

### 1:40 — 2:50  Follow graph → Post visibility + TTL & token scope

On **Bob**:

```
follow alice@127.0.0.1
```

On **Alice**:

```
post Hello followers! (token-scoped broadcast + TTL)
```

Narrate: *“Posts are delivered only to followers (we unicast to my follower set). Non-followers don’t display the post. Tokens are scope-checked (‘broadcast’) and TTL-checked on receive.”*
Show **Bob** sees 📣 POST; **Charlie** shows nothing.

### 2:50 — 3:50  DM with ACK/Retry (and address logging)

On **Alice** (replace Bob’s exact user\_id from `peers`):

```
dm bob@127.0.0.1 hey bob—this is a DM
```

Point at **Alice’s** verbose: an outbound DM with `MESSAGE_ID`; **Bob** immediately sends `ACK` (shown on both sides). If you quickly kill and unkill Bob you’d see retries, but not required now.

### 3:50 — 5:10  LIKE / UNLIKE (+ scope enforcement)

On **Bob** (use the POST’s TIMESTAMP shown in Alice’s POST; or re-post and watch the timestamp in verbose):

```
like alice@127.0.0.1 <POST_TIMESTAMP>
like alice@127.0.0.1 <POST_TIMESTAMP> UNLIKE
```

Show **Alice** gets 👍/👎 notifications. Note: token scope ‘broadcast’ is enforced for LIKE.

### 5:10 — 6:30  Groups: create / update / message

On **Alice** (substitute exact user IDs from `peers`):

```
group_create tripbuds2025 "Trip Buddies" bob@127.0.0.1,charlie@127.0.0.1
group_msg tripbuds2025 Hi team, photos coming shortly.
group_update tripbuds2025 add=  remove=charlie@127.0.0.1
```

Show **Bob** and **Charlie** prints on create/message; then group update print. Mention: *“Each peer tracks group state locally; actions require ‘group’ scope tokens.”*

### 6:30 — 8:00  File transfer with induced packet loss + ACK/Retry

On **Alice** (sender has `--loss 0.30`, so you’ll see `DROP !` and “Retry n”):

```
file_send bob@127.0.0.1 client-files/hello.txt
```

On **Bob**, you’ll see:

```
User alice is sending you a file, do you accept? Use: accept <FILEID>
```

Copy the printed `FILEID`, then:

```
accept <FILEID>
```

Observe retries + eventual completion. **Bob** prints:

```
📥 File saved to inbox/alice/hello.txt
```

Note: `FILE_RECEIVED` is sent back to Alice.

### 8:00 — 9:15  Tic-Tac-Toe with packet loss, duplicate detection, retries

On **Alice** (invite Bob; choose any short game id):

```
ttt_invite bob@127.0.0.1 X g12
```

On **Bob**, an invite notice appears. Now play a mini sequence (replace IDs exactly):

* **Alice**:

```
ttt_move bob@127.0.0.1 g12 0 1 X
```

* **Bob**:

```
ttt_move alice@127.0.0.1 g12 4 2 O
```

* **Alice**:

```
ttt_move bob@127.0.0.1 g12 1 3 X
ttt_move bob@127.0.0.1 g12 2 5 X
```

You’ll see boards after each move. Because Alice has `--loss 0.30`, watch for `DROP !` and automatic retries every 2s (up to 3). Duplicate detection (by GAMEID+TURN) will ignore repeats but still ACK.

### 9:15 — 9:40  Token expiry & revocation (local)

Restart **Alice** quickly with a tiny TTL to demo expiry:

```bash
# stop Alice, restart with short TTL
python -m lsnp.app --name alice --port 50999 --verbose --loopback --ttl 2
```

Wait 3–4 seconds so newly minted tokens expire, then try:

```
dm bob@127.0.0.1 this DM should be rejected
```

On **Bob**, you’ll see a warning in verbose (token expired) and the DM won’t display.
On **Bob**, also show local revocation:

```
revoke alice@127.0.0.1|9999999999|chat
```

Explain: *“Peers maintain an in-memory revoke list; incoming messages with revoked tokens are dropped.”*

### 9:40 — 10:00  Wrap

Flip verbose off on any peer:

```
verbose off
```

Show non-verbose UX: minimal prints (PROFILE/POST/DM/group lines, file completion, Tic-Tac-Toe board).

---

# Spec coverage → your code (quick audit)

**Legend:** ✅ implemented | ⚠️ partial/minor deviation | ⛔ missing

| Spec item                                                  | Status | Where / Notes                                                                                                                                                                                                                       |
| ---------------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| UDP sockets, broadcast & unicast                           | ✅      | `transport.py` (two-socket model; broadcast, multicast, unicast)                                                                                                                                                                    |
| mDNS-style discovery                                       | ✅      | Multicast `224.0.0.251` + broadcast; `discovery.py`, `transport.py`                                                                                                                                                                 |
| IP address logging                                         | ✅      | Verbose `recv` prints `ip:port`; `logger.py`, `transport.py`                                                                                                                                                                        |
| PROFILE (accept AVATAR\_\*)                                | ✅      | Send & parse; stores `AVATAR_TYPE/DATA`; non-verbose print name/status. `discovery.py`, `peers.py`, `app._pretty_print`                                                                                                             |
| PING (periodic, triggers PROFILE)                          | ✅      | `discovery.py` interval=300s; `app._on_PING` replies with PROFILE                                                                                                                                                                   |
| POST (TTL, token, followers-only)                          | ⚠️     | Delivery: unicast to followers **if any**; otherwise a broadcast fallback for solo demo (`cli.cmd_post`). Spec says non-followers should not receive; suggest removing fallback (see below). TTL/scope validated in `app._on_POST`. |
| DM (unicast, token, ACK/retry)                             | ✅      | `cli.cmd_dm`, `app._send_with_ack`, auto-ACK in `app._on_packet`, validate in `_on_DM`                                                                                                                                              |
| FOLLOW / UNFOLLOW                                          | ✅      | `cli.cmd_follow` (idempotent), handlers `_on_FOLLOW/_on_UNFOLLOW`                                                                                                                                                                   |
| LIKE / UNLIKE                                              | ✅      | `cli.cmd_like`, handler `_on_LIKE` with de-dup & scope check                                                                                                                                                                        |
| FILE\_OFFER / FILE\_CHUNK / FILE\_RECEIVED                 | ✅      | `file_transfer.py` (accept/ignore, chunk reassembly, completion print, FILE\_RECEIVED reply), ACK/retry wired                                                                                                                       |
| Induced packet loss (game/file only)                       | ✅      | `transport.send_unicast(..., drop_for="game"/"file")` controlled by `--loss`                                                                                                                                                        |
| ACK / Retry (2s, max 3)                                    | ✅      | `constants.py`, `ack.py`, integrated across DM/file/game; auto-ACK on receive for addressed messages                                                                                                                                |
| Tic-Tac-Toe (stateless wire, duplicate detection, retries) | ✅      | `game.py` (`last_turn_seen` idempotency, ACK/retry via `AckManager`, board rendering)                                                                                                                                               |
| Groups: create/update/message                              | ✅      | `groups.py`, handlers in `app.py`, CLI send paths                                                                                                                                                                                   |
| Token expiry, scope, revocation                            | ✅      | `tokens.py` (flexible parse, expiry, scope == expected, revoke set); `_on_REVOKE` consumes REVOKE if received                                                                                                                       |
| Verify FROM/USER\_ID IP matches                            | ✅      | `app._on_packet` drops on mismatch (tolerates loopback for localhost tests)                                                                                                                                                         |
| Verbose mode: logs, acks, retrans, drops                   | ⚠️     | You log acks/retries/drops well; token **success** validations aren’t logged (only rejects). Optionally add a verbose trace for accepted validations.                                                                               |
| Non-verbose UX requirements                                | ⚠️     | Close overall. Minor text differences (e.g., file completion line). `TICTACTOE_RESULT` print shows winner line—spec text is inconsistent; your behavior is reasonable.                                                              |
| Documentation/Milestones                                   | ⛔      | Out of code scope.                                                                                                                                                                                                                  
## Handy “what I’ll say” bullets (to keep you on time)

* *“LSNP is stateless on the wire, stateful locally. We use UDP broadcast + multicast for discovery; unicast for directed traffic.”*
* *“Tokens are human-readable (`user|exp|scope`), validated for expiry, scope, sender match, and local revocation.”*
* *“Loss is simulated for game/file only; ACK/Retry ensures eventual delivery or fail after 3 tries. Duplicate detection keeps game/file idempotent.”*
* *“Security: we compare the declared sender IP to the packet IP and drop on mismatch (except loopback demos).”*
* *“Verbose mode shows every packet sent/received, source addresses, ACKs, retries, and simulated drops.”*

If you want, I can also generate a one-page “cheat sheet” handout of the above commands with blanks for the user IDs.
