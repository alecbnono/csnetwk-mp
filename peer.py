import socket
import threading
import time
import random

HOST = '0.0.0.0'
PORT = 50999
BROADCAST_ADDRESS = '192.168.100.255'
BUFFER_SIZE = 1024
known_peers = {}
DISPLAY_NAME = "Test Peer"

# This function must be defined first
def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

# USER_ID is now defined AFTER the function it calls
USER_ID = f'user_{random.randint(1000, 9999)}@{get_local_ip()}'

def send_presence():
    # Create a UDP socket and enable broadcast
    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    while True:
        # PING message string
        message_string = f"TYPE: PING\nUSER_ID: {USER_ID}\n\n"
        
        # Send the message to the broadcast address
        sender_socket.sendto(message_string.encode('utf-8'), (BROADCAST_ADDRESS, PORT))
        print(f"Sent PING from {USER_ID}")

        profile_message = f"TYPE: PROFILE\nUSER_ID: {USER_ID}\nDISPLAY_NAME: {DISPLAY_NAME}\n\n"
        sender_socket.sendto(profile_message.encode('utf-8'), (BROADCAST_ADDRESS, PORT))
        print(f"Sent PROFILE from {USER_ID}")

        time.sleep(300)


def validate_token(token_string, expected_scope, sender_id):
    try:
        token_user_id, expiration_timestamp, scope = token_string.split('|')
        
        # Check if the token's user ID matches the message sender's ID
        if token_user_id != sender_id:
            print(f"Token user ID mismatch: expected '{sender_id}', got '{token_user_id}'")
            return False

        # Check if the token has expired
        if int(expiration_timestamp) < int(time.time()):
            print("Token expired!")
            return False
            
        # Check if the scope matches the message type
        if scope != expected_scope:
            print(f"Token scope mismatch: expected '{expected_scope}', got '{scope}'")
            return False

        # All checks passed
        return True
        
    except (ValueError, IndexError):
        # Handle malformed tokens
        return False
    

def parse_message(message_string):
    parsed_message = {}
    lines = message_string.strip().split('\n')

    for line in lines:
        if ':' in line:
            key, value = line.split(':', 1)
            parsed_message[key.strip()] = value.strip()
    
    return parsed_message

def receive_messages():
    receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_socket.bind((HOST, PORT))
    print(f"Listening for messages on {HOST}:{PORT}")

    while True:
        raw_data, sender_address = receiver_socket.recvfrom(BUFFER_SIZE)
        
        decoded_message = raw_data.decode('utf-8')
        parsed_message = parse_message(decoded_message)
        
        message_type = parsed_message.get('TYPE')
        if message_type == 'PROFILE':
            user_id = parsed_message.get('USER_ID')
            if user_id:
                known_peers[user_id] = {
                    'address': sender_address[0],
                    'display_name': parsed_message.get('DISPLAY_NAME', user_id),
                    'status': parsed_message.get('STATUS', '')
                }
                print(f"Discovered new/updated peer: {user_id}")
                print(f"Current known peers: {known_peers}")
        elif message_type == 'PING':
            print(f"Received PING from {sender_address[0]}, will respond with PROFILE.")
            
            profile_message = f"TYPE: PROFILE\nUSER_ID: {USER_ID}\nDISPLAY_NAME: {DISPLAY_NAME}\n\n"
            
            receiver_socket.sendto(profile_message.encode('utf-8'), sender_address)
        elif message_type == 'DM':
            # Use the RFC-compliant keys
            sender_id = parsed_message.get('FROM')
            message_content = parsed_message.get('CONTENT', '')
            
            token = parsed_message.get('TOKEN')
            if validate_token(token, 'chat', sender_id):
                display_name = known_peers.get(sender_id, {}).get('display_name', sender_id)
                
                print(f"\n--- DM from {display_name} ({sender_id}): ---")
                print(f"{message_content}")
                print("---------------------------------")
            else:
                print(f"Rejected DM from {sender_id} due to invalid token.")
            
        elif message_type == 'POST':
            sender_id = parsed_message.get('USER_ID')
            message_content = parsed_message.get('CONTENT', '')
            
            token = parsed_message.get('TOKEN')
            if validate_token(token, 'broadcast', sender_id):
                # Check if we know the sender, otherwise use the user_id
                display_name = known_peers.get(sender_id, {}).get('display_name', sender_id)
                
                print(f"\n--- New Post from {display_name}: ---")
                print(f"{message_content}")
                print("-----------------------------------")
            else:
                print(f"Rejected POST from {sender_id} due to invalid token.")
        
        else:
            print(f"\nReceived message from {sender_address}:\n{decoded_message}")


def main_loop():
    while True:
        command = input("> ")

        if command == "quit":
            print("Shutting down...")
            break # exits loop and program

        elif command == "peers":
            if known_peers:
                print("--- Known Peers ---")
                for user_id, details in known_peers.items():
                    print(f"  - {details['display_name']} (ID: {user_id}) at {details['address']}")
                print("-------------------")
            else:
                print("No peers discovered yet.")

        elif command.startswith("DM "):
            parts = command.split(' ', 2)
            if len(parts) < 3:
                print("Usage: DM <user_id> <message>")
                continue

            recipient_id = parts[1]
            message_content = parts[2]

            if recipient_id in known_peers:
                recipient_address = known_peers[recipient_id]['address']

                # Generate a simple timestamp and placeholder token as per RFC
                timestamp = int(time.time())
                token = f'{USER_ID}|{timestamp+3600}|chat'
                
                # Create the DM message string using RFC-compliant keys
                dm_message = f"TYPE: DM\nFROM: {USER_ID}\nTO: {recipient_id}\nCONTENT: {message_content}\nTIMESTAMP: {timestamp}\nTOKEN: {token}\n\n"
                
                # Create a temporary socket to send the message
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as dm_sender_socket:
                    dm_sender_socket.sendto(dm_message.encode('utf-8'), (recipient_address, PORT))
                
                print(f"DM sent to {recipient_id}.")
            else:
                print(f"Error: Peer with ID '{recipient_id}' not found.")
        
        elif command.startswith("POST "):
            content = command.split(' ', 1)[1]
            if not content:
                print("Usage: POST <message>")
                continue
            
            timestamp = int(time.time())
            # MESSAGE_ID is a randomly generated hex string
            message_id = f'{random.getrandbits(64):x}'
            # TOKEN for a POST message has a 'broadcast' scope
            token = f'{USER_ID}|{timestamp+3600}|broadcast'

            post_message = f"TYPE: POST\nUSER_ID: {USER_ID}\nCONTENT: {content}\nTTL: 3600\nMESSAGE_ID: {message_id}\nTIMESTAMP: {timestamp}\nTOKEN: {token}\n\n"
            
            # Create a temporary socket to send the broadcast message
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as post_sender_socket:
                post_sender_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                post_sender_socket.sendto(post_message.encode('utf-8'), (BROADCAST_ADDRESS, PORT))

            print(f"Post sent to the network.")

        else:
            print(f"Unknown command: '{command}'")
        


if __name__ == "__main__":
    sender_thread = threading.Thread(target=send_presence, daemon=True)
    sender_thread.start()

    receiver_thread = threading.Thread(target=receive_messages, daemon=True)
    receiver_thread.start()

    try:
        main_loop()
    except KeyboardInterrupt:
        print("\nPeer is shutting down...")
    finally:
        pass
