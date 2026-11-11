import pytest

from stma.crypto import (
    DocumentVerificationError,
    EncryptedDocument,
    decrypt_and_verify_document,
    encrypt_document,
    generate_rsa_key_pair,
)


@pytest.fixture(scope="module")
def keys():
    signer_private, signer_public = generate_rsa_key_pair(2048)
    recipient_private, recipient_public = generate_rsa_key_pair(2048)
    return signer_private, signer_public, recipient_private, recipient_public


def test_document_round_trip_and_signature_verification(keys):
    signer_private, signer_public, recipient_private, recipient_public = keys
    original = b"Student summer training report\n"

    encrypted = encrypt_document(original, signer_private, recipient_public)

    assert decrypt_and_verify_document(encrypted, recipient_private, signer_public) == original


def test_modified_ciphertext_is_rejected(keys):
    signer_private, signer_public, recipient_private, recipient_public = keys
    encrypted = encrypt_document(b"Original report", signer_private, recipient_public)
    changed = bytearray(encrypted.ciphertext)
    changed[-9] ^= 1
    tampered = EncryptedDocument(encrypted.iv, bytes(changed), encrypted.wrapped_key)

    with pytest.raises(DocumentVerificationError):
        decrypt_and_verify_document(tampered, recipient_private, signer_public)


def test_wrong_signing_key_is_rejected(keys):
    signer_private, _, recipient_private, recipient_public = keys
    _, other_signer_public = generate_rsa_key_pair(2048)
    encrypted = encrypt_document(b"Report", signer_private, recipient_public)

    with pytest.raises(DocumentVerificationError):
        decrypt_and_verify_document(encrypted, recipient_private, other_signer_public)
