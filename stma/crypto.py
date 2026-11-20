"""Reference implementation of STMA's document and chat encryption.

The browser does the real work (stma/static/document-crypto.js); this module performs the
same steps in Python so the tests can prove the format round-trips and that tampering is
detected. Reports and chat messages use the same scheme: sign with RSA-PSS, encrypt the
signature and the data with a fresh DES-CBC key, then wrap that DES key with RSA-OAEP.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from Crypto.Cipher import DES, PKCS1_OAEP
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from Crypto.Signature import pss
from Crypto.Util.Padding import pad, unpad


class DocumentVerificationError(ValueError):
    """Raised when an encrypted document or message cannot be decrypted or verified."""


@dataclass(frozen=True)
class EncryptedDocument:
    iv: bytes
    ciphertext: bytes
    wrapped_key: bytes


@dataclass(frozen=True)
class EncryptedMessage:
    iv: bytes
    ciphertext: bytes
    # The DES key wrapped with the recipient's encryption public key.
    wrapped_key: bytes
    # The same DES key wrapped with the sender's own encryption public key, so the sender
    # can read their sent messages later.
    sender_wrapped_key: bytes


def _import_rsa_key(key: bytes | str) -> RSA.RsaKey:
    try:
        return RSA.import_key(key)
    except (ValueError, IndexError, TypeError) as exc:
        raise ValueError("Invalid RSA key.") from exc


def _import_public_key(key: bytes | str) -> RSA.RsaKey:
    public_key = _import_rsa_key(key)
    if public_key.has_private():
        raise ValueError("A public key must not contain a private key.")
    return public_key


def generate_rsa_key_pair(bits: int = 3072) -> tuple[bytes, bytes]:
    if bits < 2048:
        raise ValueError("RSA keys must be at least 2048 bits.")
    key = RSA.generate(bits)
    private_key = key.export_key(format="PEM")
    return private_key, key.public_key().export_key(format="PEM")


def _sign_and_encrypt(
    data: bytes,
    signing_private_key: bytes | str,
    *recipient_public_keys: bytes | str,
) -> tuple[bytes, bytes, list[bytes]]:
    """Returns the IV, the ciphertext and one wrapped DES key per recipient."""
    signer = _import_rsa_key(signing_private_key)
    if not signer.has_private():
        raise ValueError("A private signing key is required.")
    recipients = [_import_public_key(key) for key in recipient_public_keys]

    signature = pss.new(signer).sign(SHA256.new(data))
    payload = struct.pack(">I", len(signature)) + signature + data

    des_key = get_random_bytes(8)
    iv = get_random_bytes(8)
    ciphertext = DES.new(des_key, DES.MODE_CBC, iv).encrypt(pad(payload, DES.block_size))
    wrapped_keys = [
        PKCS1_OAEP.new(recipient, hashAlgo=SHA256).encrypt(des_key) for recipient in recipients
    ]
    return iv, ciphertext, wrapped_keys


def _decrypt_and_verify(
    iv: bytes,
    ciphertext: bytes,
    wrapped_key: bytes,
    private_key: bytes | str,
    signer_public_key: bytes | str,
) -> bytes:
    recipient = _import_rsa_key(private_key)
    if not recipient.has_private():
        raise ValueError("A private decryption key is required.")
    signer = _import_public_key(signer_public_key)

    try:
        des_key = PKCS1_OAEP.new(recipient, hashAlgo=SHA256).decrypt(wrapped_key)
        if len(des_key) != 8 or len(iv) != DES.block_size:
            raise ValueError("Invalid DES key or initialization vector.")
        payload = unpad(DES.new(des_key, DES.MODE_CBC, iv).decrypt(ciphertext), DES.block_size)
        if len(payload) < 4:
            raise ValueError("Malformed signed payload.")
        signature_size = struct.unpack(">I", payload[:4])[0]
        signature_end = 4 + signature_size
        if signature_size == 0 or signature_end > len(payload):
            raise ValueError("Malformed signed payload.")
        signature = payload[4:signature_end]
        data = payload[signature_end:]
        pss.new(signer).verify(SHA256.new(data), signature)
    except (ValueError, TypeError, struct.error) as exc:
        raise DocumentVerificationError("Decryption or signature verification failed.") from exc
    return data


def encrypt_document(
    document: bytes,
    signing_private_key: bytes | str,
    recipient_public_key: bytes | str,
) -> EncryptedDocument:
    iv, ciphertext, (wrapped_key,) = _sign_and_encrypt(
        document, signing_private_key, recipient_public_key
    )
    return EncryptedDocument(iv=iv, ciphertext=ciphertext, wrapped_key=wrapped_key)


def decrypt_and_verify_document(
    encrypted: EncryptedDocument,
    recipient_private_key: bytes | str,
    signer_public_key: bytes | str,
) -> bytes:
    return _decrypt_and_verify(
        encrypted.iv,
        encrypted.ciphertext,
        encrypted.wrapped_key,
        recipient_private_key,
        signer_public_key,
    )


def encrypt_message(
    text: str,
    signing_private_key: bytes | str,
    recipient_public_key: bytes | str,
    sender_public_key: bytes | str,
) -> EncryptedMessage:
    iv, ciphertext, (wrapped_key, sender_wrapped_key) = _sign_and_encrypt(
        text.encode("utf-8"), signing_private_key, recipient_public_key, sender_public_key
    )
    return EncryptedMessage(
        iv=iv,
        ciphertext=ciphertext,
        wrapped_key=wrapped_key,
        sender_wrapped_key=sender_wrapped_key,
    )


def decrypt_and_verify_message(
    encrypted: EncryptedMessage,
    private_key: bytes | str,
    signer_public_key: bytes | str,
    *,
    own_copy: bool = False,
) -> str:
    """Opens a message with the reader's encryption private key.

    The recipient uses ``wrapped_key``; the sender reads their own message through
    ``sender_wrapped_key`` by passing ``own_copy=True``.
    """
    data = _decrypt_and_verify(
        encrypted.iv,
        encrypted.ciphertext,
        encrypted.sender_wrapped_key if own_copy else encrypted.wrapped_key,
        private_key,
        signer_public_key,
    )
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DocumentVerificationError("The message is not valid UTF-8 text.") from exc
