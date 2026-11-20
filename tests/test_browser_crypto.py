"""Runs the browser's crypto worker (stma/static/document-crypto.js) in Node.js and checks
that it interoperates with the Python reference implementation in both directions."""

import base64
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from Crypto.PublicKey import RSA

from stma.crypto import (
    EncryptedDocument,
    EncryptedMessage,
    decrypt_and_verify_document,
    decrypt_and_verify_message,
    encrypt_document,
    encrypt_message,
)

NODE = shutil.which("node")
WORKER = Path(__file__).resolve().parent.parent / "stma" / "static" / "document-crypto.js"
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js runs the browser crypto code")

# Loads the worker as a browser would and feeds it requests; binary fields travel as base64.
HARNESS = r"""
const fs = require("node:fs");
const vm = require("node:vm");
const binary = new Set(["ciphertext", "iv", "wrappedKey", "document"]);
const replies = new Map();
globalThis.self = { postMessage: (message) => replies.get(message.id)(message) };
vm.runInThisContext(fs.readFileSync(process.argv[2], "utf8"));
(async () => {
  const results = [];
  const requests = JSON.parse(fs.readFileSync(0, "utf8"));
  for (const [id, { action, payload }] of requests.entries()) {
    for (const name of Object.keys(payload)) {
      if (binary.has(name)) payload[name] = Uint8Array.from(Buffer.from(payload[name], "base64"));
    }
    const reply = await new Promise((resolve) => {
      replies.set(id, resolve);
      self.onmessage({ data: { id, action, payload } });
    });
    if (reply.result instanceof Uint8Array) reply.result = Buffer.from(reply.result).toString("base64");
    results.push(reply);
  }
  process.stdout.write(JSON.stringify(results));
})();
"""


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def run_worker(tmp_path: Path, requests: list[dict]) -> list[dict]:
    harness = tmp_path / "harness.cjs"
    harness.write_text(HARNESS)
    completed = subprocess.run(
        [NODE, str(harness), str(WORKER)],
        input=json.dumps(requests),
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    return json.loads(completed.stdout)


@pytest.fixture(scope="module")
def keys():
    """PEM keys in the formats the browser uses: PKCS#8 private keys, SPKI public keys."""
    pairs = {}
    for name in ("signing", "sender_encryption", "recipient_encryption"):
        key = RSA.generate(2048)
        pairs[name] = (
            key.export_key(format="PEM", pkcs=8).decode("ascii"),
            key.public_key().export_key(format="PEM").decode("ascii"),
        )
    return pairs


TEXT = "Hocam, staj raporumu gönderdim. Teşekkürler! ğüşıöçİ"


def test_message_sealed_in_the_browser_opens_in_python(tmp_path, keys):
    [reply] = run_worker(
        tmp_path,
        [
            {
                "action": "encrypt-message",
                "payload": {
                    "text": TEXT,
                    "signingPrivatePem": keys["signing"][0],
                    "signingPublicPem": keys["signing"][1],
                    "recipientPublicPem": keys["recipient_encryption"][1],
                    "senderPublicPem": keys["sender_encryption"][1],
                },
            }
        ],
    )
    sealed = reply["result"]
    message = EncryptedMessage(
        iv=base64.b64decode(sealed["iv_b64"]),
        ciphertext=base64.b64decode(sealed["ciphertext_b64"]),
        wrapped_key=base64.b64decode(sealed["wrapped_des_key_b64"]),
        sender_wrapped_key=base64.b64decode(sealed["sender_wrapped_des_key_b64"]),
    )

    assert TEXT.encode("utf-8") not in message.ciphertext
    assert (
        decrypt_and_verify_message(message, keys["recipient_encryption"][0], keys["signing"][1])
        == TEXT
    )
    assert (
        decrypt_and_verify_message(
            message, keys["sender_encryption"][0], keys["signing"][1], own_copy=True
        )
        == TEXT
    )


def test_message_sealed_in_python_opens_in_the_browser(tmp_path, keys):
    message = encrypt_message(
        TEXT, keys["signing"][0], keys["recipient_encryption"][1], keys["sender_encryption"][1]
    )
    tampered = bytearray(message.ciphertext)
    tampered[len(tampered) // 2] ^= 1

    def request(ciphertext: bytes, wrapped_key: bytes, private_key: str) -> dict:
        return {
            "action": "decrypt-message",
            "payload": {
                "ciphertext": b64(ciphertext),
                "iv": b64(message.iv),
                "wrappedKey": b64(wrapped_key),
                "privatePem": private_key,
                "signerPublicPem": keys["signing"][1],
            },
        }

    recipient, sender, wrong_key, changed = run_worker(
        tmp_path,
        [
            request(message.ciphertext, message.wrapped_key, keys["recipient_encryption"][0]),
            request(message.ciphertext, message.sender_wrapped_key, keys["sender_encryption"][0]),
            request(message.ciphertext, message.wrapped_key, keys["sender_encryption"][0]),
            request(bytes(tampered), message.wrapped_key, keys["recipient_encryption"][0]),
        ],
    )

    assert recipient["result"] == TEXT
    assert sender["result"] == TEXT
    assert wrong_key["code"] == "wrong-key"
    assert changed["code"] in {"signature", "damaged"}


def test_report_sealed_in_the_browser_opens_in_python(tmp_path, keys):
    report = b"Summer training report\n" * 50
    [reply] = run_worker(
        tmp_path,
        [
            {
                "action": "encrypt",
                "payload": {
                    "document": b64(report),
                    "signingPrivatePem": keys["signing"][0],
                    "signingPublicPem": keys["signing"][1],
                    "recipientPublicPem": keys["recipient_encryption"][1],
                },
            }
        ],
    )
    sealed = reply["result"]
    document = EncryptedDocument(
        iv=base64.b64decode(sealed["iv_b64"]),
        ciphertext=base64.b64decode(sealed["ciphertext_b64"]),
        wrapped_key=base64.b64decode(sealed["wrapped_des_key_b64"]),
    )

    assert "sender_wrapped_des_key_b64" not in sealed
    assert (
        decrypt_and_verify_document(document, keys["recipient_encryption"][0], keys["signing"][1])
        == report
    )


def test_browser_refuses_a_signing_key_that_does_not_match_the_published_one(tmp_path, keys):
    [reply] = run_worker(
        tmp_path,
        [
            {
                "action": "encrypt-message",
                "payload": {
                    "text": "hello",
                    "signingPrivatePem": keys["signing"][0],
                    "signingPublicPem": keys["sender_encryption"][1],
                    "recipientPublicPem": keys["recipient_encryption"][1],
                    "senderPublicPem": keys["sender_encryption"][1],
                },
            }
        ],
    )
    assert reply["code"] == "signing-key-mismatch"


def test_report_sealed_in_python_opens_in_the_browser(tmp_path, keys):
    report = b"%PDF-1.7 evaluation report\n" * 40
    sealed = encrypt_document(report, keys["signing"][0], keys["recipient_encryption"][1])
    [reply] = run_worker(
        tmp_path,
        [
            {
                "action": "decrypt",
                "payload": {
                    "ciphertext": b64(sealed.ciphertext),
                    "iv": b64(sealed.iv),
                    "wrappedKey": b64(sealed.wrapped_key),
                    "recipientPrivatePem": keys["recipient_encryption"][0],
                    "signerPublicPem": keys["signing"][1],
                },
            }
        ],
    )
    assert base64.b64decode(reply["result"]) == report
