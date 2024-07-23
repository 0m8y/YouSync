from cryptography.fernet import Fernet
import os

# Charger la clé
def load_key() -> bytes:
    secret_key = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'secret.key')
    return open(secret_key, 'rb').read()

# Chiffrer le client_id
def encrypt_client_id(client_id: str) -> bytes:
    key = load_key()
    f = Fernet(key)
    encrypted_client_id = f.encrypt(client_id.encode())
    return encrypted_client_id
