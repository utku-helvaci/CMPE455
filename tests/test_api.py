import base64

from fastapi.testclient import TestClient

from stma.crypto import decrypt_and_verify_document, encrypt_document, generate_rsa_key_pair
from stma.main import create_app
from stma.models import ChatMessage, Relationship, User
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
        reassignment = client.patch(
            f"/api/admin/users/{student.json()['id']}/role",
            headers=admin_headers,
            json={"role": "evaluator"},
        )
        assert reassignment.status_code == 409

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

        message = client.post(
            f"/api/relationships/{relationship_id}/messages",
            headers=student_headers,
            json={"body": "Hello, evaluator."},
        )
        assert message.status_code == 201
        assert message.json()["body"] == "Hello, evaluator."

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
            assert retained_message.body == "Hello, evaluator."
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
