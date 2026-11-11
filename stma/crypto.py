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
    """Raised when an encrypted document cannot be decrypted or verified."""


@dataclass(frozen=True)
class EncryptedDocument:
    iv: bytes
    ciphertext: bytes
    wrapped_key: bytes


def _import_rsa_key(key: bytes | str) -> RSA.RsaKey:
    try:
        return RSA.import_key(key)
    except (ValueError, IndexError, TypeError) as exc:
        raise ValueError("Invalid RSA key.") from exc


def generate_rsa_key_pair(bits: int = 3072) -> tuple[bytes, bytes]:
    if bits < 2048:
        raise ValueError("RSA keys must be at least 2048 bits.")
    key = RSA.generate(bits)
    private_key = key.export_key(format="PEM")
    return private_key, key.public_key().export_key(format="PEM")


def encrypt_document(
    document: bytes,
    signing_private_key: bytes | str,
    recipient_public_key: bytes | str,
) -> EncryptedDocument:
    signer = _import_rsa_key(signing_private_key)
    recipient = _import_rsa_key(recipient_public_key)
    if not signer.has_private():
        raise ValueError("A private signing key is required.")
    if recipient.has_private():
        raise ValueError("The recipient public key must not contain a private key.")

    signature = pss.new(signer).sign(SHA256.new(document))
    payload = struct.pack(">I", len(signature)) + signature + document

    des_key = get_random_bytes(8)
    iv = get_random_bytes(8)
    ciphertext = DES.new(des_key, DES.MODE_CBC, iv).encrypt(pad(payload, DES.block_size))
    wrapped_key = PKCS1_OAEP.new(recipient, hashAlgo=SHA256).encrypt(des_key)
    return EncryptedDocument(iv=iv, ciphertext=ciphertext, wrapped_key=wrapped_key)


def decrypt_and_verify_document(
    encrypted: EncryptedDocument,
    recipient_private_key: bytes | str,
    signer_public_key: bytes | str,
) -> bytes:
    recipient = _import_rsa_key(recipient_private_key)
    signer = _import_rsa_key(signer_public_key)
    if not recipient.has_private():
        raise ValueError("A private decryption key is required.")
    if signer.has_private():
        raise ValueError("The sender public key must not contain a private key.")

    try:
        des_key = PKCS1_OAEP.new(recipient, hashAlgo=SHA256).decrypt(encrypted.wrapped_key)
        if len(des_key) != 8 or len(encrypted.iv) != DES.block_size:
            raise ValueError("Invalid DES key or initialization vector.")
        payload = unpad(
            DES.new(des_key, DES.MODE_CBC, encrypted.iv).decrypt(encrypted.ciphertext),
            DES.block_size,
        )
        if len(payload) < 4:
            raise ValueError("Malformed signed document.")
        signature_size = struct.unpack(">I", payload[:4])[0]
        signature_end = 4 + signature_size
        if signature_size == 0 or signature_end > len(payload):
            raise ValueError("Malformed signed document.")
        signature = payload[4:signature_end]
        document = payload[signature_end:]
        pss.new(signer).verify(SHA256.new(document), signature)
    except (ValueError, TypeError, struct.error) as exc:
        raise DocumentVerificationError(
            "Document decryption or signature verification failed."
        ) from exc
    return document
