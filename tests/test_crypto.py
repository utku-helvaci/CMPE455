import pytest

from stma.crypto import (
    DocumentVerificationError,
    EncryptedDocument,
    EncryptedMessage,
    decrypt_and_verify_document,
    decrypt_and_verify_message,
    encrypt_document,
    encrypt_message,
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


@pytest.fixture(scope="module")
def sender_encryption_keys():
    return generate_rsa_key_pair(2048)


def test_message_opens_for_recipient_and_for_sender(keys, sender_encryption_keys):
    signer_private, signer_public, recipient_private, recipient_public = keys
    sender_private, sender_public = sender_encryption_keys
    text = "Raporunuzu okudum: çok iyi, ğüşıöç"

    encrypted = encrypt_message(text, signer_private, recipient_public, sender_public)

    assert text.encode("utf-8") not in encrypted.ciphertext
    assert decrypt_and_verify_message(encrypted, recipient_private, signer_public) == text
    assert (
        decrypt_and_verify_message(encrypted, sender_private, signer_public, own_copy=True) == text
    )


def test_each_message_key_copy_opens_only_with_its_own_private_key(keys, sender_encryption_keys):
    signer_private, signer_public, recipient_private, recipient_public = keys
    sender_private, sender_public = sender_encryption_keys
    encrypted = encrypt_message("Grade: A", signer_private, recipient_public, sender_public)

    with pytest.raises(DocumentVerificationError):
        decrypt_and_verify_message(encrypted, sender_private, signer_public)
    with pytest.raises(DocumentVerificationError):
        decrypt_and_verify_message(encrypted, recipient_private, signer_public, own_copy=True)


def test_modified_message_is_rejected(keys, sender_encryption_keys):
    signer_private, signer_public, recipient_private, recipient_public = keys
    _, sender_public = sender_encryption_keys
    encrypted = encrypt_message("Grade: B", signer_private, recipient_public, sender_public)
    changed = bytearray(encrypted.ciphertext)
    changed[len(changed) // 2] ^= 1
    tampered = EncryptedMessage(
        encrypted.iv, bytes(changed), encrypted.wrapped_key, encrypted.sender_wrapped_key
    )

    with pytest.raises(DocumentVerificationError):
        decrypt_and_verify_message(tampered, recipient_private, signer_public)
