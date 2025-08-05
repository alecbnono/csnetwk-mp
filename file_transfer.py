import socket
import os
import time
import base64
import hashlib
from collections import defaultdict
import threading

UDP_PORT = 50999
CHUNK_SIZE = 1024
LOCAL_USER_ID = "alice@192.168.1.11"  # change as needed
RECEIVED_DIR = "downloads"

file_metadata = {}
file_chunks = defaultdict(dict)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("", UDP_PORT))


def generate_token(user_id, ttl, scope):
    expiry = int(time.time()) + ttl
    return f"{user_id}|{expiry}|{scope}"


# ------------------------ SENDER ------------------------
def send_file_offer_and_chunks(local_user_id, to_ip, file_path):
    if not os.path.exists(file_path):
        print("[ERROR] File does not exist.")
        return

    filename = os.path.basename(file_path)
    filesize = os.path.getsize(file_path)
    fileid = hashlib.md5((filename + str(time.time())).encode()).hexdigest()
    token = generate_token(local_user_id, 600, "file")
    filetype = "application/octet-stream"
    to_user_id = f"unknown@{to_ip}"

    offer_msg = f"""TYPE: FILE_OFFER
FROM: {local_user_id}
TO: {to_user_id}
FILENAME: {filename}
FILESIZE: {filesize}
FILETYPE: {filetype}
FILEID: {fileid}
DESCRIPTION: Sent via CLI
TIMESTAMP: {int(time.time())}
TOKEN: {token}

"""
    sock.sendto(offer_msg.encode(), (to_ip, UDP_PORT))
    print(f"[SEND] FILE_OFFER sent to {to_ip} for '{filename}'")

    input("[WAIT] Press ENTER to start sending chunks...")

    with open(file_path, "rb") as f:
        data = f.read()
        total_chunks = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE

        for idx in range(total_chunks):
            chunk = data[idx * CHUNK_SIZE:(idx + 1) * CHUNK_SIZE]
            encoded = base64.b64encode(chunk).decode()

            chunk_msg = f"""TYPE: FILE_CHUNK
FROM: {local_user_id}
TO: {to_user_id}
FILEID: {fileid}
CHUNK_INDEX: {idx}
TOTAL_CHUNKS: {total_chunks}
CHUNK_SIZE: {len(chunk)}
TOKEN: {token}
DATA: {encoded}

"""
            sock.sendto(chunk_msg.encode(), (to_ip, UDP_PORT))
            time.sleep(0.05)

    print(f"[DONE] File transfer of '{filename}' complete.")


# ------------------------ RECEIVER ------------------------
def handle_file_offer(fields, addr):
    fileid = fields['FILEID']
    sender = fields['FROM']
    filename = fields['FILENAME']
    filesize = fields['FILESIZE']
    description = fields.get('DESCRIPTION', 'No description provided')

    print(f"\n📨 User {sender} is sending you a file.")
    print(f"Name: {filename} | Size: {filesize} bytes | Desc: {description}")
    accept = input("Do you accept? (y/n): ").strip().lower()

    if accept != 'y':
        print("[INFO] File offer ignored.")
        return

    file_metadata[fileid] = {
        "filename": filename,
        "from": sender,
        "total_chunks": None,
        "received_chunks": 0,
        "chunks": {}
    }

    print(f"[ACCEPTED] File offer from {sender} accepted.")


def handle_file_chunk(fields, addr):
    fileid = fields['FILEID']
    chunk_index = int(fields['CHUNK_INDEX'])
    total_chunks = int(fields['TOTAL_CHUNKS'])
    data = base64.b64decode(fields['DATA'])

    if fileid not in file_metadata:
        return  # Offer was ignored

    file_chunks[fileid][chunk_index] = data
    file_metadata[fileid]["received_chunks"] += 1
    file_metadata[fileid]["total_chunks"] = total_chunks

    if file_metadata[fileid]["received_chunks"] == total_chunks:
        save_file(fileid)


def save_file(fileid):
    info = file_metadata[fileid]
    filename = info["filename"]
    chunks = file_chunks[fileid]
    ordered = b''.join([chunks[i] for i in sorted(chunks)])

    os.makedirs(RECEIVED_DIR, exist_ok=True)
    path = os.path.join(RECEIVED_DIR, filename)

    with open(path, "wb") as f:
        f.write(ordered)

    print(f"[COMPLETE] File transfer of '{filename}' saved to '{RECEIVED_DIR}/'.")

    send_file_received(fileid, info["from"])


def send_file_received(fileid, to_user_id):
    timestamp = int(time.time())
    msg = f"""TYPE: FILE_RECEIVED
FROM: {LOCAL_USER_ID}
TO: {to_user_id}
FILEID: {fileid}
STATUS: COMPLETE
TIMESTAMP: {timestamp}

"""
    sock.sendto(msg.encode(), (to_user_id.split("@")[1], UDP_PORT))


# ------------------------ COMMON ------------------------
def parse_message(data):
    lines = data.decode(errors="ignore").splitlines()
    fields = {}
    for line in lines:
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip()
    return fields


def receiver_thread():
    print(f"[LISTENING] on UDP port {UDP_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(65535)
            fields = parse_message(data)
            msg_type = fields.get("TYPE", "")

            if msg_type == "FILE_OFFER":
                handle_file_offer(fields, addr)
            elif msg_type == "FILE_CHUNK":
                handle_file_chunk(fields, addr)
            elif msg_type == "FILE_RECEIVED":
                pass  # Optional: log it if needed
        except Exception as e:
            print(f"[ERROR] Receiver: {e}")


# ------------------------ MAIN ------------------------
def main():
    print("📡 LSNP File Transfer CLI (Send & Receive)")
    threading.Thread(target=receiver_thread, daemon=True).start()

    while True:
        try:
            command = input("LSNP> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[EXIT] Goodbye.")
            break

        if command.lower() in ("exit", "quit"):
            break
        elif command.startswith("sendfile "):
            parts = command.split(" ", 2)
            if len(parts) < 3:
                print("[ERROR] Usage: sendfile <ip> <file_path>")
            else:
                to_ip = parts[1]
                file_path = parts[2]
                send_file_offer_and_chunks(LOCAL_USER_ID, to_ip, file_path)
        else:
            print("[ERROR] Unknown command. Use: sendfile <ip> <file_path>")


if __name__ == "__main__":
    main()
