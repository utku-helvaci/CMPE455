import base64

from fastapi.testclient import TestClient

from stma.crypto import decrypt_and_verify_document, encrypt_document, generate_rsa_key_pair
from stma.main import create_app
from stma.models import User
from stma.security import hash_password


def test_registration_login_and_relationship_access(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        storage_dir=tmp_path / "encrypted",
    )
    with app.state.session_factory.begin() as db:
        db.add(
            User(
                username="sysadmin",
                password_hash=hash_password("admin password long"),
                role="sysadmin",
            )
        )

    with TestClient(app) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "Sign in to STMA" in page.text
        assert client.get("/static/login.css").status_code == 200
        assert client.get("/static/login.js").status_code == 200
        assert client.get("/static/workspace.js").status_code == 200
        assert client.get("/static/document-crypto.js").status_code == 200

        student = client.post(
            "/api/auth/register",
            json={"username": "student1", "password": "student password long", "role": "student"},
        )
        evaluator = client.post(
            "/api/auth/register",
            json={
                "username": "evaluator1",
                "password": "evaluator password long",
                "role": "evaluator",
            },
        )
        outsider = client.post(
            "/api/auth/register",
            json={"username": "student2", "password": "another password long", "role": "student"},
        )
        assert student.status_code == evaluator.status_code == outsider.status_code == 201

        admin_login = client.post(
            "/api/auth/login",
            json={"username": "sysadmin", "password": "admin password long"},
        )
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

        relation = client.post(
            "/api/admin/relationships",
            headers=admin_headers,
            json={
                "student_id": student.json()["id"],
                "evaluator_id": evaluator.json()["id"],
            },
        )
        assert relation.status_code == 201
        assert relation.json()["student_username"] == "student1"
        assert relation.json()["evaluator_username"] == "evaluator1"
        relationship_id = relation.json()["id"]

        student_login = client.post(
            "/api/auth/login",
            json={"username": "student1", "password": "student password long"},
        )
        student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}
        student_relationships = client.get("/api/relationships", headers=student_headers)
        assert student_relationships.status_code == 200
        assert student_relationships.json()[0]["evaluator_username"] == "evaluator1"
        evaluator_login = client.post(
            "/api/auth/login",
            json={"username": "evaluator1", "password": "evaluator password long"},
        )
        evaluator_headers = {"Authorization": f"Bearer {evaluator_login.json()['access_token']}"}

        message = client.post(
            f"/api/relationships/{relationship_id}/messages",
            headers=student_headers,
            json={"body": "Hello, evaluator."},
        )
        assert message.status_code == 201
        assert message.json()["body"] == "Hello, evaluator."

        signing_private, signing_public = generate_rsa_key_pair(2048)
        recipient_private, recipient_public = generate_rsa_key_pair(2048)
        signing_key = client.post(
            f"/api/relationships/{relationship_id}/keys",
            headers=student_headers,
            json={
                "purpose": "signing",
                "public_key_pem": signing_public.decode("ascii"),
            },
        )
        encryption_key = client.post(
            f"/api/relationships/{relationship_id}/keys",
            headers=evaluator_headers,
            json={
                "purpose": "encryption",
                "public_key_pem": recipient_public.decode("ascii"),
            },
        )
        assert signing_key.status_code == encryption_key.status_code == 201
        rotated_key = client.post(
            f"/api/relationships/{relationship_id}/keys",
            headers=evaluator_headers,
            json={
                "purpose": "encryption",
                "public_key_pem": recipient_public.decode("ascii"),
            },
        )
        assert rotated_key.status_code == 201
        assert rotated_key.json()["version"] == encryption_key.json()["version"] + 1

        report = b"Student training report"
        encrypted = encrypt_document(report, signing_private, recipient_public)
        uploaded = client.post(
            f"/api/relationships/{relationship_id}/documents",
            headers=student_headers,
            json={
                "filename": "training-report.pdf",
                "ciphertext_b64": base64.b64encode(encrypted.ciphertext).decode("ascii"),
                "iv_b64": base64.b64encode(encrypted.iv).decode("ascii"),
                "wrapped_des_key_b64": base64.b64encode(encrypted.wrapped_key).decode("ascii"),
                "recipient_key_id": encryption_key.json()["id"],
                "signing_key_id": signing_key.json()["id"],
            },
        )
        assert uploaded.status_code == 201
        assert report not in b"".join(
            path.read_bytes() for path in (tmp_path / "encrypted").iterdir()
        )

        downloaded = client.get(
            f"/api/relationships/{relationship_id}/documents",
            headers=evaluator_headers,
        )
        assert downloaded.status_code == 200
        received = downloaded.json()[0]
        decrypted = decrypt_and_verify_document(
            encrypted,
            recipient_private,
            signing_public,
        )
        assert decrypted == report
        assert base64.b64decode(received["ciphertext_b64"]) == encrypted.ciphertext

        outsider_login = client.post(
            "/api/auth/login",
            json={"username": "student2", "password": "another password long"},
        )
        outsider_headers = {"Authorization": f"Bearer {outsider_login.json()['access_token']}"}
        denied = client.get(
            f"/api/relationships/{relationship_id}/messages",
            headers=outsider_headers,
        )
        assert denied.status_code == 404
        denied_documents = client.get(
            f"/api/relationships/{relationship_id}/documents",
            headers=outsider_headers,
        )
        assert denied_documents.status_code == 404

        admin_cannot_read_chat = client.get(
            f"/api/relationships/{relationship_id}/messages",
            headers=admin_headers,
        )
        assert admin_cannot_read_chat.status_code == 404

        health = client.get("/api/admin/health", headers=admin_headers)
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
