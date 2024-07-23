from core.cryptography.encrypt import load_key
from cryptography.fernet import Fernet

def decrypt_client_id(encrypted_client_id: str) -> str:
    key = load_key()
    f = Fernet(key)
    decrypted_client_id = f.decrypt(encrypted_client_id).decode()
    return decrypted_client_id
