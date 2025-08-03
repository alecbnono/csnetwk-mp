import os
import socket
import threading

HOST = 'localhost'
PORT = 5001
BUFFER_SIZE = 1024

class Server:
    def __init__(self):

        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.clients = {}
        self.connected_sockets = {}

        if not os.path.exists("server-files"):
            os.makedirs("server-files")

    def start(self):
        self.server.bind((HOST,PORT))
        self.server.listen()
        print(f"Server is listening on {HOST}:{PORT}")

        while True:
            client_socket, addr = self.server.accept()
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
            client_thread.daemon = True
            client_thread.start()

    def handle_upload(self, client_socket):
        try:
            # Step 1: Receive metadata (file name and size)
            metadata = b""
            while b"\n" not in metadata:
                chunk = client_socket.recv(BUFFER_SIZE)
                if not chunk:
                    raise ConnectionError("Client disconnected before sending metadata.")
                metadata += chunk

            # Split the received data into metadata and possible file data
            meta_line, remainder = metadata.split(b"\n", 1)
            decoded = meta_line.decode().strip()

            if "|" not in decoded:
                raise ValueError("Invalid metadata format. Expected 'filename|size'.")

            file_name, file_size_str = decoded.split("|")
            file_size = int(file_size_str)

            # Step 2: Prepare to receive the file
            save_path = os.path.join("server-files", file_name)
            received = len(remainder)  # We already received part of the file
            with open(save_path, 'wb') as f:
                f.write(remainder)
                while received < file_size:
                    chunk = client_socket.recv(BUFFER_SIZE)
                    if not chunk:
                        raise ConnectionError("Connection lost during file upload.")
                    f.write(chunk)
                    received += len(chunk)

            print(f"[SUCCESS] Received '{file_name}' ({file_size} bytes) from client.")

        except Exception as e:
            print(f"[ERROR] Failed to receive file: {str(e)}")

    def handle_download(self, client_socket, file_name):
        try:
            file_path = os.path.join("server-files", file_name)

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"{file_path} does not exist.")

            file_size = os.path.getsize(file_path)

            client_socket.sendall(f"OK|{file_size}\n".encode())

            with open(file_path, 'rb') as f:
                while True:
                    data = f.read(BUFFER_SIZE)
                    if not data:
                        break
                    client_socket.sendall(data)

            print(f"[SUCCESS] Sent '{file_name}' ({file_size} bytes) to client.")

        except Exception as e:
            print(f"[ERROR] Failed to send file '{file_name}': {str(e)}")
            client_socket.sendall(b"ERROR\n")

    def handle_list(self, client_socket):
        try:
            files = os.listdir("server-files")
            files = [f.strip() for f in files if os.path.isfile(os.path.join("server-files", f))]

            response = f"OK|{len(files)}\n"
            client_socket.sendall(response.encode())

            for file in files:
                client_socket.sendall((file + "\n").encode())

            print(f"[SUCCESS] Sent list of {len(files)} files to client.")

        except Exception as e:
            client_socket.sendall(f"ERROR|{str(e)}\n".encode())

    def handle_client(self, client_socket, addr):
        try:
            print(f"[CONNECTED] Client {addr} connected.")
            command = self.read_line(client_socket)

            if command == "UPLOAD":
                self.handle_upload(client_socket)

            elif command == "DOWNLOAD":
                # Wait for the filename
                file_name_data = b""
                while not file_name_data.endswith(b"\n"):
                    chunk = client_socket.recv(BUFFER_SIZE)
                    if not chunk:
                        raise ConnectionError("Client disconnected before sending filename.")
                    file_name_data += chunk

                file_name = file_name_data.decode().strip()
                if file_name:
                    self.handle_download(client_socket, file_name)
                else:
                    client_socket.sendall(b"ERROR|Missing filename for download\n")

            elif command == "LIST":
                self.handle_list(client_socket)

            else:
                client_socket.sendall(b"ERROR|Unknown command\n")

        except Exception as e:
            print(f"[ERROR] Client {addr}: {str(e)}")
            client_socket.sendall(f"ERROR|{str(e)}\n".encode())
        finally:
            client_socket.close()
            print(f"[DISCONNECTED] Client {addr} disconnected.")

    def read_line(self, sock):
        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(1)
            if not chunk:
                break
            data += chunk
        return data.decode().strip()

if __name__ == "__main__":
    server = Server()
    server.start()
