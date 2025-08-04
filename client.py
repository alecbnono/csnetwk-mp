import socket
import os


HOST = 'localhost'
PORT = 5001
BUFFER_SIZE = 1024

class Client:
    def __init__(self):
        self.host = HOST
        self.port = PORT

    def upload(self, file_name):
        """
        Uploads a file to the server by sending:
        - Command header ("UPLOAD")
        - Metadata (file name and size)
        - File content in binary chunks
        """
        try:
            file_path = os.path.join("client-files", file_name)

            # Check if file exists
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"{file_path} does not exist.")

            file_size = os.path.getsize(file_path)

            # Create socket and connect to server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))

                # TCP header looks like (in binary):
                #   =============================
                #   |          UPLOAD           |
                #   =============================
                #   | (file_name) | (file_size) |
                #   =============================
                #   |         file_data         |
                #   =============================

                # Send command header
                s.sendall(b'UPLOAD\n')

                # Send metadata: file name and file size
                metadata = f"{file_name}|{file_size}\n"
                s.sendall(metadata.encode())

                # Send file content in chunks
                with open(file_path, 'rb') as f:
                    while True:
                        data = f.read(1024)
                        if not data:
                            break
                        s.sendall(data)

                print(f"[SUCCESS] Sent '{file_name}' ({file_size} bytes) to server.")

        except Exception as e:
            print(f"[ERROR] Failed to send file: {str(e)}")

    def download(self, file_name):
        """
        Downloads a file from the server by sending:
        - Command header ("DOWNLOAD")
        - File name
        Receives:
        - Status and file size
        - File content in binary chunks
        """
        try:
            # Step 1: Connect to server
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((HOST, PORT))

                # Step 2: Send command
                s.sendall(b"DOWNLOAD\n")

                # Step 3: Send requested file name
                s.sendall(f"{file_name}\n".encode())

                # Step 4: Wait for server's response (e.g., OK|file_size or ERROR) and file size
                response = b""
                while not response.endswith(b"\n"):
                    chunk = s.recv(BUFFER_SIZE)
                    if not chunk:
                        raise ConnectionError("[ERROR] Server closed the connection before response.")
                    response += chunk

                # check server acknowledgement
                decoded = response.decode().strip()
                if not decoded.startswith("OK"):
                    raise FileNotFoundError(f"[WARN] Server response: {decoded}")

                # Extract file size from server response
                _, file_size_str = decoded.split("|")
                file_size = int(file_size_str)

                # Save file to client-files directory
                save_path = os.path.join("client-files", file_name)
                received = 0

                # Receive file content in chunks
                with open(save_path, 'wb') as f:
                    while received < file_size:
                        chunk = s.recv(min(BUFFER_SIZE, file_size - received))
                        if not chunk:
                            raise ConnectionError("Connection lost during download.")
                        f.write(chunk)
                        received += len(chunk)

                print(f"[SUCCESS] Downloaded '{file_name}' ({file_size} bytes) as '{save_path}'.")

        except Exception as e:
            print(f"[ERROR] Failed to download file: {str(e)}")

    def list(self):
        """
        Requests and displays a list of available files on the server.
        Sends:
        - Command header ("LIST")
        Receives:
        - File count and file names
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.host, self.port))
                s.sendall(b"LIST\n")

                buffer = b""
                # Read until first newline (header)
                while b"\n" not in buffer:
                    buffer += s.recv(BUFFER_SIZE)

                # Split the first line (header) from the rest
                header_line, buffer = buffer.split(b"\n", 1)
                header_decoded = header_line.decode().strip()

                # check server acknowledgement
                if not header_decoded.startswith("OK"):
                    print(f"[WARN] Server response: {header_decoded}")
                    return

                # Extract file count
                _, count_str = header_decoded.split("|")
                file_count = int(count_str)

                print(f"[INFO] Server has {file_count} file(s):")

                # Read filenames
                files = []
                while len(files) < file_count:
                    if b"\n" not in buffer:
                        buffer += s.recv(BUFFER_SIZE)
                        continue

                    line, buffer = buffer.split(b"\n", 1)
                    files.append(line.decode().strip())

                for f in files:
                    print(f"  - {f}")

        except Exception as e:
            print(f"[ERROR] Failed to list files: {str(e)}")

    def start(self):
        """
        Command loop for interacting with the client.
        Supports: UPLOAD, DOWNLOAD, LIST, EXIT
        """

        print("Available Commands:")
        print("UPLOAD | DOWNLOAD | LIST | EXIT")

        while True:
            command = input("> ").strip().upper()
            if not command:
                continue

            if command == "EXIT":
                break

            elif command == "LIST":
                self.list()

            elif command == "UPLOAD":
                file_name = input("Enter Filename (with extension): ")
                self.upload(file_name)

            elif command == "DOWNLOAD":
                file_name = input("Enter Filename (with extension): ")
                self.download(file_name)


            else:
                print("[ERROR] Invalid Command")


if __name__ == "__main__":
    client = Client()
    client.start()
