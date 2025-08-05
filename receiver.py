import socket
from file_transfer import receive_file_chunks

# Bind listener to localhost and LSNP port
listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
listener.bind(('127.0.0.1', 50999))

# Match FILEID from sender (will be printed there)
expected_fileid = "testfileid123"
receive_file_chunks(listener, expected_fileid)
