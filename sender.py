import socket
import time
from file_transfer import send_file_offer, send_file_chunks

sender_id = "alice@127.0.0.1"
receiver_ip = "127.0.0.1"
receiver_id = "bob@127.0.0.1"
filepath = "cup.png"  # Create this test file in same folder
token = f"{sender_id}|{int(time.time()) + 600}|file"  # 10 min token

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Simulate sending FILE_OFFER and then chunks
fileid = "testfileid123"  # Must match receiver's expected_fileid
send_file_offer(sock, sender_id, receiver_ip, receiver_id, filepath, token)
time.sleep(1)
send_file_chunks(sock, sender_id, receiver_ip, receiver_id, filepath, fileid, token)
