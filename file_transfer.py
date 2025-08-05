import base64
import hashlib
import os
import socket
import time
import json
from token_utils import validate_token

CHUNK_SIZE = 1024  # 1 KB
UDP_PORT = 50999

def send_file_offer(sock, sender_id, receiver_ip, receiver_id, filepath, token):
    if not validate_token(token, 'file'):
        print("[DROP] Invalid token for file offer.")
        return

    filesize = os.path.getsize(filepath)
    filetype = "application/octet-stream"  # Could infer MIME from extension
    filename = os.path.basename(filepath)
    fileid = hashlib.md5((filename + str(time.time())).encode()).hexdigest()

    offer = f"""TYPE: FILE_OFFER
FROM: {sender_id}
TO: {receiver_id}
FILENAME: {filename}
FILESIZE: {filesize}
FILETYPE: {filetype}
FILEID: {fileid}
DESCRIPTION: Auto-generated LSNP file
TIMESTAMP: {int(time.time())}
TOKEN: {token}

"""
    sock.sendto(offer.encode(), (receiver_ip, UDP_PORT))
    return fileid

def send_file_chunks(sock, sender_id, receiver_ip, receiver_id, filepath, fileid, token):
    if not validate_token(token, 'file'):
        print("[DROP] Invalid token for file chunks.")
        return

    with open(filepath, "rb") as f:
        data = f.read()
        total_chunks = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE

        for idx in range(total_chunks):
            chunk_data = data[idx * CHUNK_SIZE:(idx + 1) * CHUNK_SIZE]
            encoded_data = base64.b64encode(chunk_data).decode()

            msg = f"""TYPE: FILE_CHUNK
FROM: {sender_id}
TO: {receiver_id}
FILEID: {fileid}
CHUNK_INDEX: {idx}
TOTAL_CHUNKS: {total_chunks}
CHUNK_SIZE: {len(chunk_data)}
TOKEN: {token}
DATA: {encoded_data}

"""
            sock.sendto(msg.encode(), (receiver_ip, UDP_PORT))
            time.sleep(0.05)  # simulate spacing

def receive_file_chunks(listener, expected_fileid):
    chunks = {}
    total_chunks = None
    assembled = False

    while not assembled:
        data, _ = listener.recvfrom(65536)
        message = data.decode()

        if f"FILEID: {expected_fileid}" not in message:
            continue

        fields = dict(line.split(": ", 1) for line in message.strip().split("\n") if ": " in line)
        if not validate_token(fields["TOKEN"], "file"):
            print("[DROP] Invalid token in chunk.")
            continue

        idx = int(fields["CHUNK_INDEX"])
        total_chunks = int(fields["TOTAL_CHUNKS"])
        chunks[idx] = base64.b64decode(fields["DATA"])

        if len(chunks) == total_chunks:
            assembled = True

    # Reassemble
    filename = f"received_{expected_fileid}.bin"
    with open(filename, "wb") as f:
        for i in range(total_chunks):
            f.write(chunks[i])

    print(f"File transfer of {filename} is complete.")
import base64
import os
import socket
import time
import json
from token_utils import validate_token

CHUNK_SIZE = 1024  # 1 KB
UDP_PORT = 50999

def send_file_offer(sock, sender_id, receiver_ip, receiver_id, filepath, token):
    if not validate_token(token, 'file'):
        print("[DROP] Invalid token for file offer.")
        return

    filesize = os.path.getsize(filepath)
    filetype = "application/octet-stream"  # Could infer MIME from extension
    filename = os.path.basename(filepath)
    fileid = hashlib.md5((filename + str(time.time())).encode()).hexdigest()

    offer = f"""TYPE: FILE_OFFER
FROM: {sender_id}
TO: {receiver_id}
FILENAME: {filename}
FILESIZE: {filesize}
FILETYPE: {filetype}
FILEID: {fileid}
DESCRIPTION: Auto-generated LSNP file
TIMESTAMP: {int(time.time())}
TOKEN: {token}

"""
    sock.sendto(offer.encode(), (receiver_ip, UDP_PORT))
    return fileid

def send_file_chunks(sock, sender_id, receiver_ip, receiver_id, filepath, fileid, token):
    if not validate_token(token, 'file'):
        print("[DROP] Invalid token for file chunks.")
        return

    with open(filepath, "rb") as f:
        data = f.read()
        total_chunks = (len(data) + CHUNK_SIZE - 1) // CHUNK_SIZE

        for idx in range(total_chunks):
            chunk_data = data[idx * CHUNK_SIZE:(idx + 1) * CHUNK_SIZE]
            encoded_data = base64.b64encode(chunk_data).decode()

            msg = f"""TYPE: FILE_CHUNK
FROM: {sender_id}
TO: {receiver_id}
FILEID: {fileid}
CHUNK_INDEX: {idx}
TOTAL_CHUNKS: {total_chunks}
CHUNK_SIZE: {len(chunk_data)}
TOKEN: {token}
DATA: {encoded_data}

"""
            sock.sendto(msg.encode(), (receiver_ip, UDP_PORT))
            time.sleep(0.05)  # simulate spacing

def receive_file_chunks(listener, expected_fileid):
    chunks = {}
    total_chunks = None
    assembled = False

    while not assembled:
        data, _ = listener.recvfrom(65536)
        message = data.decode()

        if f"FILEID: {expected_fileid}" not in message:
            continue

        fields = dict(line.split(": ", 1) for line in message.strip().split("\n") if ": " in line)
        if not validate_token(fields["TOKEN"], "file"):
            print("[DROP] Invalid token in chunk.")
            continue

        idx = int(fields["CHUNK_INDEX"])
        total_chunks = int(fields["TOTAL_CHUNKS"])
        chunks[idx] = base64.b64decode(fields["DATA"])

        if len(chunks) == total_chunks:
            assembled = True

    # Reassemble
    filename = f"received_{expected_fileid}.bin"
    with open(filename, "wb") as f:
        for i in range(total_chunks):
            f.write(chunks[i])

    print(f"File transfer of {filename} is complete.")
