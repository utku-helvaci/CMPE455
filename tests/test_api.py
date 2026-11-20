import base64

import pytest
from fastapi.testclient import TestClient

from stma.crypto import (
    EncryptedMessage,
    decrypt_and_verify_document,
    decrypt_and_verify_message,
    encrypt_document,
    encrypt_message,
    generate_rsa_key_pair,
)
from stma.main import MAX_MESSAGE_CIPHERTEXT_BYTES, create_app
from stma.models import ChatMessage, Document, LoginSession, PublicKey, Relationship, User
from stma.security import hash_password


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def message_payload(
    sealed: EncryptedMessage, recipient_key_id: str, sender_key_id: str, signing_key_id: str
) -> dict[str, str]:
    return {
        "ciphertext_b64": b64(sealed.ciphertext),
        "iv_b64": b64(sealed.iv),
        "wrapped_des_key_b64": b64(sealed.wrapped_key),
        "sender_wrapped_des_key_b64": b64(sealed.sender_wrapped_key),
        "recipient_key_id": recipient_key_id,
        "sender_key_id": sender_key_id,
        "signing_key_id": signing_key_id,
    }


def received_message(view: dict) -> EncryptedMessage:
    return EncryptedMessage(
        iv=base64.b64decode(view["iv_b64"]),
        ciphertext=base64.b64decode(view["ciphertext_b64"]),
        wrapped_key=base64.b64decode(view["wrapped_des_key_b64"]),
        sender_wrapped_key=base64.b64decode(view["sender_wrapped_des_key_b64"]),
    )


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
        assert 'id="signup-form"' in page.text
        assert "Assign account roles" in page.text
        assert 'id="account-role"' not in page.text

        student = client.post(
            "/api/auth/register",
            json={
                "first_name": "Stu",
                "last_name": "Dent",
                "school_id": "student1",
                "password": "student password long",
            },
        )
        outsider = client.post(
            "/api/auth/register",
            json={
                "first_name": "Other",
                "last_name": "Student",
                "school_id": "student2",
                "password": "another password long",
            },
        )
        assert student.status_code == outsider.status_code == 201
        assert student.json()["role"] == "pending"
        assert student.json()["first_name"] == "Stu"
        assert student.json()["last_name"] == "Dent"
        assert student.json()["school_id"] == "student1"
        self_assigned_role = client.post(
            "/api/auth/register",
            json={
                "first_name": "Self",
                "last_name": "Assigned",
                "school_id": "selfassigned",
                "password": "another student password",
                "role": "evaluator",
            },
        )
        assert self_assigned_role.status_code == 422
        duplicate_school_id = client.post(
            "/api/auth/register",
            json={
                "first_name": "Duplicate",
                "last_name": "Student",
                "school_id": "student1",
                "password": "another student password",
            },
        )
        assert duplicate_school_id.status_code == 409
        evaluator = client.post(
            "/api/auth/register",
            json={
                "first_name": "Terry",
                "last_name": "Teacher",
                "school_id": "teacher123",
                "password": "teacher password long",
            },
        )
        assert evaluator.status_code == 201
        assert evaluator.json()["role"] == "pending"
        assert evaluator.json()["school_id"] == "teacher123"

        admin_login = client.post(
            "/api/auth/login",
            json={"username": "sysadmin", "password": "admin password long"},
        )
        assert admin_login.status_code == 200
        admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
        with app.state.session_factory() as db:
            admin_id = db.query(User.id).filter_by(username="sysadmin").scalar()

        pending_login = client.post(
            "/api/auth/login",
            json={"username": "student1", "password": "student password long"},
        )
        assert pending_login.status_code == 403
        assert "awaiting role assignment" in pending_login.json()["detail"]
        pending_accounts = client.get("/api/admin/users", headers=admin_headers)
        assert pending_accounts.status_code == 200
        assert len(pending_accounts.json()) == 3
        assert {account["role"] for account in pending_accounts.json()} == {"pending"}
        assert all(account["username"] != "sysadmin" for account in pending_accounts.json())

        assigned_student = client.patch(
            f"/api/admin/users/{student.json()['id']}/role",
            headers=admin_headers,
            json={"role": "student"},
        )
        assigned_evaluator = client.patch(
            f"/api/admin/users/{evaluator.json()['id']}/role",
            headers=admin_headers,
            json={"role": "evaluator"},
        )
        assigned_outsider = client.patch(
            f"/api/admin/users/{outsider.json()['id']}/role",
            headers=admin_headers,
            json={"role": "student"},
        )
        assert assigned_student.status_code == assigned_outsider.status_code == 200
        assert assigned_student.json()["role"] == assigned_outsider.json()["role"] == "student"
        assert assigned_evaluator.status_code == 200
        assert assigned_evaluator.json()["role"] == "evaluator"
        role_change = client.patch(
            f"/api/admin/users/{outsider.json()['id']}/role",
            headers=admin_headers,
            json={"role": "evaluator"},
        )
        assert role_change.status_code == 200
        assert role_change.json()["role"] == "evaluator"
        same_role = client.patch(
            f"/api/admin/users/{student.json()['id']}/role",
            headers=admin_headers,
            json={"role": "student"},
        )
        assert same_role.status_code == 409

        evaluator_login = client.post(
            "/api/auth/login",
            json={
                "username": "teacher123",
                "password": "teacher password long",
            },
        )
        evaluator_headers = {"Authorization": f"Bearer {evaluator_login.json()['access_token']}"}
        student_login = client.post(
            "/api/auth/login",
            json={"username": "student1", "password": "student password long"},
        )
        student_headers = {"Authorization": f"Bearer {student_login.json()['access_token']}"}
        denied_account_list = client.get("/api/admin/users", headers=student_headers)
        assert denied_account_list.status_code == 403
        denied_role_assignment = client.patch(
            f"/api/admin/users/{outsider.json()['id']}/role",
            headers=student_headers,
            json={"role": "evaluator"},
        )
        assert denied_role_assignment.status_code == 403
        denied_account_deletion = client.delete(
            f"/api/admin/users/{outsider.json()['id']}",
            headers=student_headers,
        )
        assert denied_account_deletion.status_code == 403
        student_cannot_choose_teacher = client.post(
            "/api/relationships",
            headers=student_headers,
            json={"school_id": "teacher123"},
        )
        assert student_cannot_choose_teacher.status_code == 403
        unknown_student = client.post(
            "/api/relationships",
            headers=evaluator_headers,
            json={"school_id": "unknown-school-id"},
        )
        assert unknown_student.status_code == 404
        relation = client.post(
            "/api/relationships",
            headers=evaluator_headers,
            json={"school_id": "student1"},
        )
        assert relation.status_code == 201
        assert relation.json()["student_username"] == "student1"
        assert relation.json()["student_name"] == "Stu Dent"
        assert relation.json()["evaluator_username"] == "teacher123"
        assert relation.json()["evaluator_name"] == "Terry Teacher"
        relationship_id = relation.json()["id"]
        role_change_with_relationship = client.patch(
            f"/api/admin/users/{student.json()['id']}/role",
            headers=admin_headers,
            json={"role": "evaluator"},
        )
        assert role_change_with_relationship.status_code == 409
        assert "active relationship" in role_change_with_relationship.json()["detail"]
        duplicate_relationship = client.post(
            "/api/relationships",
            headers=evaluator_headers,
            json={"school_id": "student1"},
        )
        assert duplicate_relationship.status_code == 409

        student_relationships = client.get("/api/relationships", headers=student_headers)
        assert student_relationships.status_code == 200
        assert student_relationships.json()[0]["evaluator_username"] == "teacher123"
        assert student_relationships.json()[0]["evaluator_name"] == "Terry Teacher"

        signing_private, signing_public = generate_rsa_key_pair(2048)
        recipient_private, recipient_public = generate_rsa_key_pair(2048)
        _, student_encryption_public = generate_rsa_key_pair(2048)
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
        student_encryption_key = client.post(
            f"/api/relationships/{relationship_id}/keys",
            headers=student_headers,
            json={
                "purpose": "encryption",
                "public_key_pem": student_encryption_public.decode("ascii"),
            },
        )
        assert signing_key.status_code == encryption_key.status_code == 201
        assert student_encryption_key.status_code == 201

        sealed = encrypt_message(
            "Hello, evaluator.", signing_private, recipient_public, student_encryption_public
        )
        message = client.post(
            f"/api/relationships/{relationship_id}/messages",
            headers=student_headers,
            json=message_payload(
                sealed,
                encryption_key.json()["id"],
                student_encryption_key.json()["id"],
                signing_key.json()["id"],
            ),
        )
        assert message.status_code == 201
        assert "body" not in message.json()
        listed = client.get(
            f"/api/relationships/{relationship_id}/messages",
            headers=evaluator_headers,
        ).json()
        assert [item["id"] for item in listed] == [message.json()["id"]]
        assert (
            decrypt_and_verify_message(
                received_message(listed[0]), recipient_private, signing_public
            )
            == "Hello, evaluator."
        )

        disown_denied = client.delete(
            f"/api/relationships/{relationship_id}",
            headers=student_headers,
        )
        assert disown_denied.status_code == 403
        disowned = client.delete(
            f"/api/relationships/{relationship_id}",
            headers=evaluator_headers,
        )
        assert disowned.status_code == 204
        assert (
            client.get(
                f"/api/relationships/{relationship_id}/messages",
                headers=student_headers,
            ).status_code
            == 404
        )
        assert client.get("/api/relationships", headers=student_headers).json() == []
        with app.state.session_factory() as db:
            retained_message = db.query(ChatMessage).filter_by(id=message.json()["id"]).one()
            assert retained_message.ciphertext == sealed.ciphertext
            assert db.get(Relationship, relationship_id).active is False

        rejoined = client.post(
            "/api/relationships",
            headers=evaluator_headers,
            json={"school_id": "student1"},
        )
        assert rejoined.status_code == 200
        assert rejoined.json()["id"] == relationship_id
        assert (
            client.get("/api/relationships", headers=student_headers).json()[0]["id"]
            == relationship_id
        )

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
        document_ids = client.get(
            f"/api/relationships/{relationship_id}/documents/ids",
            headers=evaluator_headers,
        )
        assert document_ids.json() == [received["id"]]

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
        denied_document_ids = client.get(
            f"/api/relationships/{relationship_id}/documents/ids",
            headers=outsider_headers,
        )
        assert denied_document_ids.status_code == 404

        admin_cannot_read_chat = client.get(
            f"/api/relationships/{relationship_id}/messages",
            headers=admin_headers,
        )
        assert admin_cannot_read_chat.status_code == 404

        health = client.get("/api/admin/health", headers=admin_headers)
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        with app.state.session_factory() as db:
            stored_document = db.query(Document).filter_by(relationship_id=relationship_id).one()
            stored_path = tmp_path / "encrypted" / stored_document.storage_name
            assert stored_path.exists()
        delete_account = client.delete(
            f"/api/admin/users/{student.json()['id']}",
            headers=admin_headers,
        )
        assert delete_account.status_code == 204
        assert not stored_path.exists()
        assert client.get("/api/relationships", headers=student_headers).status_code == 401
        with app.state.session_factory() as db:
            assert db.get(User, student.json()["id"]) is None
            assert db.query(Relationship).filter_by(id=relationship_id).count() == 0
            assert db.query(ChatMessage).filter_by(relationship_id=relationship_id).count() == 0
            assert db.query(Document).filter_by(relationship_id=relationship_id).count() == 0
            assert db.query(PublicKey).filter_by(user_id=student.json()["id"]).count() == 0
            assert db.query(LoginSession).filter_by(user_id=student.json()["id"]).count() == 0
        delete_admin_account = client.delete(
            f"/api/admin/users/{admin_id}",
            headers=admin_headers,
        )
        assert delete_admin_account.status_code == 404


def test_login_logout_and_session_revocation(tmp_path):
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'logout.db'}",
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
        db.add(
            User(
                username="student",
                password_hash=hash_password("student password long"),
                role="student",
            )
        )

    with TestClient(app) as client:
        for username, password in (
            ("sysadmin", "admin password long"),
            ("student", "student password long"),
        ):
            login = client.post(
                "/api/auth/login",
                json={"username": username, "password": password},
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            assert client.get("/api/me", headers=headers).status_code == 200
            assert client.post("/api/auth/logout", headers=headers).status_code == 204
            assert client.get("/api/me", headers=headers).status_code == 401
            assert client.post("/api/auth/logout", headers=headers).status_code == 401


@pytest.fixture(scope="module")
def chat_keys():
    return {
        name: generate_rsa_key_pair(2048)
        for name in (
            "student_signing",
            "student_encryption",
            "teacher_signing",
            "teacher_encryption",
        )
    }


def test_chat_messages_are_end_to_end_encrypted(tmp_path, chat_keys):
    database_path = tmp_path / "chat.db"
    app = create_app(database_url=f"sqlite:///{database_path}", storage_dir=tmp_path / "encrypted")
    with app.state.session_factory.begin() as db:
        for username, role in (
            ("sysadmin", "sysadmin"),
            ("student1", "student"),
            ("teacher1", "evaluator"),
            ("outsider1", "student"),
        ):
            db.add(
                User(
                    username=username,
                    school_id=None if role == "sysadmin" else username,
                    password_hash=hash_password(f"{username} password long"),
                    role=role,
                )
            )

    with TestClient(app) as client:
        headers = {}
        for username in ("sysadmin", "student1", "teacher1", "outsider1"):
            login = client.post(
                "/api/auth/login",
                json={"username": username, "password": f"{username} password long"},
            )
            headers[username] = {"Authorization": f"Bearer {login.json()['access_token']}"}
        relationship = client.post(
            "/api/relationships", headers=headers["teacher1"], json={"school_id": "student1"}
        )
        base = f"/api/relationships/{relationship.json()['id']}"

        key_ids = {}
        for name, owner in (
            ("student_signing", "student1"),
            ("student_encryption", "student1"),
            ("teacher_signing", "teacher1"),
            ("teacher_encryption", "teacher1"),
        ):
            published = client.post(
                f"{base}/keys",
                headers=headers[owner],
                json={
                    "purpose": name.split("_")[1],
                    "public_key_pem": chat_keys[name][1].decode("ascii"),
                },
            )
            assert published.status_code == 201
            key_ids[name] = published.json()["id"]

        def private(name: str) -> bytes:
            return chat_keys[name][0]

        def public(name: str) -> bytes:
            return chat_keys[name][1]

        question = "Hocam, staj raporum hazır mı? ğüşıöç"
        answer = "Yes, your report is approved."
        from_student = encrypt_message(
            question,
            private("student_signing"),
            public("teacher_encryption"),
            public("student_encryption"),
        )
        student_payload = message_payload(
            from_student,
            key_ids["teacher_encryption"],
            key_ids["student_encryption"],
            key_ids["student_signing"],
        )
        sent = client.post(f"{base}/messages", headers=headers["student1"], json=student_payload)
        assert sent.status_code == 201
        from_teacher = encrypt_message(
            answer,
            private("teacher_signing"),
            public("student_encryption"),
            public("teacher_encryption"),
        )
        reply = client.post(
            f"{base}/messages",
            headers=headers["teacher1"],
            json=message_payload(
                from_teacher,
                key_ids["student_encryption"],
                key_ids["teacher_encryption"],
                key_ids["teacher_signing"],
            ),
        )
        assert reply.status_code == 201

        for reader in ("student1", "teacher1"):
            listed = client.get(f"{base}/messages", headers=headers[reader])
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [sent.json()["id"], reply.json()["id"]]
        student_view, teacher_view = (
            received_message(item)
            for item in client.get(f"{base}/messages", headers=headers["student1"]).json()
        )
        # Each participant opens the partner's message with their own key, and their own
        # message through the copy of the DES key wrapped for themselves.
        assert (
            decrypt_and_verify_message(
                student_view, private("teacher_encryption"), public("student_signing")
            )
            == question
        )
        assert (
            decrypt_and_verify_message(
                student_view,
                private("student_encryption"),
                public("student_signing"),
                own_copy=True,
            )
            == question
        )
        assert (
            decrypt_and_verify_message(
                teacher_view, private("student_encryption"), public("teacher_signing")
            )
            == answer
        )

        def rejected(changes: dict, sender: str = "student1") -> int:
            return client.post(
                f"{base}/messages", headers=headers[sender], json={**student_payload, **changes}
            ).status_code

        assert rejected({"recipient_key_id": key_ids["student_encryption"]}) == 422
        assert rejected({"sender_key_id": key_ids["teacher_encryption"]}) == 422
        assert rejected({"signing_key_id": key_ids["student_encryption"]}) == 422
        assert rejected({"iv_b64": b64(from_student.iv[:7])}) == 422
        assert rejected({"ciphertext_b64": b64(from_student.ciphertext[:-1])}) == 422
        assert rejected({"wrapped_des_key_b64": b64(from_student.wrapped_key[:-1])}) == 422
        assert (
            rejected({"sender_wrapped_des_key_b64": b64(from_student.sender_wrapped_key[1:])})
            == 422
        )
        assert rejected({"ciphertext_b64": "not base64!"}) == 422
        assert rejected({"ciphertext_b64": b64(bytes(MAX_MESSAGE_CIPHERTEXT_BYTES + 8))}) == 413
        assert (
            client.post(
                f"{base}/messages", headers=headers["student1"], json={"body": "plain text"}
            ).status_code
            == 422
        )
        assert rejected({}, sender="outsider1") == 404
        assert rejected({}, sender="sysadmin") == 404
        assert client.get(f"{base}/messages", headers=headers["sysadmin"]).status_code == 404

    with app.state.session_factory() as db:
        assert db.query(ChatMessage).count() == 2
    app.state.engine.dispose()
    stored = database_path.read_bytes()
    for text in (question, answer):
        assert text.encode("utf-8") not in stored
