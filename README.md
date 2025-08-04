# csnetwk-mp

# Python Socket File Transfer System

A lightweight file transfer system built using Python's `socket` and `threading` libraries. It supports **uploading**, **downloading**, and **listing** files between a client and server over TCP.

## 📦 Features

- 📤 Upload files from client to server  
- 📥 Download files from server to client  
- 📂 List available files on the server  
- 🧵 Multi-threaded server to handle concurrent clients  
- 🔒 Simple protocol with structured commands and metadata

---

## 🏗️ Project Structure

```

project/
│
├── server.py          # Server application
├── client.py          # Client application
├── server-files/      # Server-side file storage (auto-created)
└── client-files/      # Client-side file storage (must exist or be created)

````

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd <your-repo-name>
````

### 2. Run the Server

```bash
python server.py
```

This starts the server on `localhost:5001`. It creates a `server-files/` directory if it doesn't exist.

### 3. Run the Client

In a new terminal:

```bash
python client.py
```

The client shows a command prompt like:

```
Available Commands:
UPLOAD | DOWNLOAD | LIST | EXIT
```

---

## 📘 Usage Guide

### 📤 Upload

```bash
UPLOAD
Enter Filename (with extension): example.txt
```

* The file must be inside the `client-files/` directory.

---

### 📥 Download

```bash
DOWNLOAD
Enter Filename (with extension): report.pdf
```

* The file will be saved into the `client-files/` directory.

---

### 📂 List

```bash
LIST
```

* Displays all files currently stored on the server.

---

### ❌ Exit

```bash
EXIT
```

* Closes the client interface.

---

## 🧠 Protocol Format

The communication between client and server follows a simple line-based protocol.

### Upload Protocol

```
UPLOAD\n
filename.ext|1024\n
[binary file data...]
```

### Download Protocol

```
DOWNLOAD\n
filename.ext\n
```

Server responds:

```
OK|1024\n
[binary file data...]
```

Or:

```
ERROR|<message>\n
```

### List Protocol

```
LIST\n
```

Server responds:

```
OK|3\n
file1.txt\n
file2.pdf\n
file3.jpg\n
```

---

## ⚠️ Requirements

* Python 3.6 or later
* No external dependencies

---

