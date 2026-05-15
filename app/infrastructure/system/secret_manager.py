# app/infrastructure/system/secret_manager.py
"""SecretManager — encrypts and decrypts sensitive values using Fernet."""
import os

from cryptography.fernet import Fernet, InvalidToken


class SecretManager:
    """Encrypts/decrypts secrets using Fernet symmetric encryption.

    The encryption key is read from the ``SECRET_ENCRYPTION_KEY`` environment
    variable at instantiation time. If the variable is missing, a clear
    ``RuntimeError`` is raised.
    """

    def __init__(self) -> None:
        key = os.environ.get("SECRET_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError(
                "SECRET_ENCRYPTION_KEY is not set. "
                "Add it to .env.secret (not in git) and restart the application."
            )
        self._fernet = Fernet(key.encode())

    def encrypt(self, value: str) -> str:
        """Return the base64-encoded ciphertext for *value*."""
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        """Return the plaintext for *encrypted*.

        Raises ``InvalidToken`` if the ciphertext cannot be decrypted (e.g.
        because the encryption key has been rotated).
        """
        return self._fernet.decrypt(encrypted.encode()).decode()

    def is_encrypted(self, value: str) -> bool:
        """Heuristic: returns True if *value* looks like a Fernet token."""
        # Fernet tokens are base64-url-safe strings with a fixed prefix
        return value.startswith("gAAAA") and len(value) > 20
