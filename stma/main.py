from __future__ import annotations

import base64
import binascii
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from Crypto.Cipher import DES
from Crypto.PublicKey import RSA
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from stma.database import Base, create_database
from stma.models import ChatMessage, Document, LoginSession, PublicKey, Relationship, User
from stma.schemas import (
    Credentials,
    DocumentUpload,
    DocumentView,
    MessageCreate,
    MessageView,
    PublicKeyCreate,
    PublicKeyView,
    Registration,
    RelationshipCreate,
    RelationshipView,
    TokenView,
    UserCreate,
    UserView,
)
from stma.security import (
    hash_password,
    issue_session_token,
    session_expiration,
    token_digest,
    verify_password,
)

bearer_scheme = HTTPBearer(auto_error=False)
SAFE_FILENAME = re.compile(r"^[^/\\\x00-\x1f\x7f]+$")


def _decode_b64(value: str, field: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail=f"{field} must be valid base64.") from exc


def create_app(
    database_url: str | None = None,
    storage_dir: str | Path | None = None,
    max_document_bytes: int | None = None,
    session_hours: int | None = None,
    initialize_schema: bool = True,
) -> FastAPI:
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./stma.db")
    storage_dir = Path(storage_dir or os.getenv("STMA_STORAGE_DIR", "./storage")).resolve()
    max_document_bytes = max_document_bytes or int(os.getenv("STMA_MAX_DOCUMENT_BYTES", "15728640"))
    session_hours = session_hours or int(os.getenv("STMA_SESSION_HOURS", "12"))

    engine, session_factory = create_database(database_url)
    if initialize_schema:
        Base.metadata.create_all(engine)
    storage_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="STMA", version="0.1.0")
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.storage_dir = storage_dir
    app.state.max_document_bytes = max_document_bytes
    app.state.session_hours = session_hours
    app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

    @app.get("/", include_in_schema=False)
    def login_page() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "login.html")

    def get_db(request: Request):
        with request.app.state.session_factory() as db:
            yield db

    def current_user(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
        db: Session = Depends(get_db),
    ) -> User:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required.")
        token_hash = token_digest(credentials.credentials)
        login = db.scalar(
            select(LoginSession).where(
                LoginSession.token_hash == token_hash,
                LoginSession.expires_at > datetime.now(UTC),
            )
        )
        if login is None:
            raise HTTPException(status_code=401, detail="Session is invalid or expired.")
        user = db.get(User, login.user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Session user no longer exists.")
        request.state.login_session = login
        return user

    def require_role(user: User, role: str) -> None:
        if user.role != role:
            raise HTTPException(status_code=403, detail="This operation is not permitted.")

    def get_relationship(db: Session, relationship_id: str) -> Relationship:
        relationship = db.get(Relationship, relationship_id)
        if relationship is None:
            raise HTTPException(status_code=404, detail="Relationship not found.")
        return relationship

    def require_participant(relationship: Relationship, user: User) -> None:
        if user.id not in {relationship.student_id, relationship.evaluator_id}:
            raise HTTPException(status_code=404, detail="Relationship not found.")

    def counterpart_id(relationship: Relationship, user: User) -> str:
        require_participant(relationship, user)
        return (
            relationship.evaluator_id
            if user.id == relationship.student_id
            else relationship.student_id
        )

    @app.post("/api/auth/register", response_model=UserView, status_code=201)
    def register(payload: Registration, db: Session = Depends(get_db)) -> User:
        user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
        )
        db.add(user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Username is already registered.") from exc
        db.refresh(user)
        return user

    @app.post("/api/auth/login", response_model=TokenView)
    def login(payload: Credentials, db: Session = Depends(get_db)) -> TokenView:
        user = db.scalar(select(User).where(User.username == payload.username))
        if user is None or not verify_password(user.password_hash, payload.password):
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        token, digest = issue_session_token()
        db.add(
            LoginSession(
                user_id=user.id,
                token_hash=digest,
                expires_at=session_expiration(session_hours),
            )
        )
        db.commit()
        return TokenView(access_token=token)

    @app.post("/api/auth/logout", status_code=204)
    def logout(
        request: Request,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> None:
        del user
        login_session = request.state.login_session
        db.delete(login_session)
        db.commit()

    @app.get("/api/me", response_model=UserView)
    def me(user: User = Depends(current_user)) -> User:
        return user

    @app.post("/api/admin/users", response_model=UserView, status_code=201)
    def create_user(
        payload: UserCreate,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> User:
        require_role(user, "sysadmin")
        new_user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
        )
        db.add(new_user)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail="Username is already registered.") from exc
        db.refresh(new_user)
        return new_user

    @app.post(
        "/api/admin/relationships",
        response_model=RelationshipView,
        status_code=201,
    )
    def create_relationship(
        payload: RelationshipCreate,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> RelationshipView:
        require_role(user, "sysadmin")
        student = db.get(User, payload.student_id)
        evaluator = db.get(User, payload.evaluator_id)
        if student is None or student.role != "student":
            raise HTTPException(status_code=422, detail="student_id must identify a student.")
        if evaluator is None or evaluator.role != "evaluator":
            raise HTTPException(status_code=422, detail="evaluator_id must identify an evaluator.")
        relationship = Relationship(student_id=student.id, evaluator_id=evaluator.id)
        db.add(relationship)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409, detail="This relationship already exists."
            ) from exc
        return RelationshipView(
            id=relationship.id,
            student_id=student.id,
            evaluator_id=evaluator.id,
            student_username=student.username,
            evaluator_username=evaluator.username,
        )

    @app.get("/api/relationships", response_model=list[RelationshipView])
    def list_relationships(
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> list[RelationshipView]:
        if user.role == "sysadmin":
            raise HTTPException(
                status_code=403, detail="Sysadmins do not access client workspaces."
            )
        relationships = list(
            db.scalars(
                select(Relationship).where(
                    (Relationship.student_id == user.id) | (Relationship.evaluator_id == user.id)
                )
            )
        )
        return [
            RelationshipView(
                id=relationship.id,
                student_id=relationship.student_id,
                evaluator_id=relationship.evaluator_id,
                student_username=relationship.student.username,
                evaluator_username=relationship.evaluator.username,
            )
            for relationship in relationships
        ]

    @app.post(
        "/api/relationships/{relationship_id}/keys", response_model=PublicKeyView, status_code=201
    )
    def publish_key(
        relationship_id: str,
        payload: PublicKeyCreate,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> PublicKey:
        relationship = get_relationship(db, relationship_id)
        require_participant(relationship, user)
        try:
            key = RSA.import_key(payload.public_key_pem)
        except (ValueError, IndexError, TypeError) as exc:
            raise HTTPException(status_code=422, detail="Invalid RSA public key.") from exc
        if key.has_private() or key.size_in_bits() < 2048:
            raise HTTPException(
                status_code=422,
                detail="Provide an RSA public key of at least 2048 bits; private keys must remain local.",
            )
        latest_version = db.scalar(
            select(func.max(PublicKey.version)).where(
                PublicKey.user_id == user.id,
                PublicKey.purpose == payload.purpose,
            )
        )
        record = PublicKey(
            user_id=user.id,
            purpose=payload.purpose,
            version=(latest_version or 0) + 1,
            public_key_pem=key.export_key(format="PEM").decode("ascii"),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @app.get(
        "/api/relationships/{relationship_id}/keys",
        response_model=list[PublicKeyView],
    )
    def list_public_keys(
        relationship_id: str,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> list[PublicKey]:
        relationship = get_relationship(db, relationship_id)
        require_participant(relationship, user)
        return list(
            db.scalars(
                select(PublicKey)
                .where(PublicKey.user_id.in_([relationship.student_id, relationship.evaluator_id]))
                .order_by(PublicKey.created_at)
            )
        )

    @app.post(
        "/api/relationships/{relationship_id}/messages",
        response_model=MessageView,
        status_code=201,
    )
    def send_message(
        relationship_id: str,
        payload: MessageCreate,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> ChatMessage:
        relationship = get_relationship(db, relationship_id)
        require_participant(relationship, user)
        message = ChatMessage(
            relationship_id=relationship.id,
            sender_id=user.id,
            body=payload.body,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @app.get(
        "/api/relationships/{relationship_id}/messages",
        response_model=list[MessageView],
    )
    def list_messages(
        relationship_id: str,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> list[ChatMessage]:
        relationship = get_relationship(db, relationship_id)
        require_participant(relationship, user)
        return list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.relationship_id == relationship_id)
                .order_by(ChatMessage.created_at, ChatMessage.id)
            )
        )

    @app.post(
        "/api/relationships/{relationship_id}/documents",
        response_model=DocumentView,
        status_code=201,
    )
    def upload_document(
        relationship_id: str,
        payload: DocumentUpload,
        request: Request,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> DocumentView:
        relationship = get_relationship(db, relationship_id)
        recipient_id = counterpart_id(relationship, user)
        if not SAFE_FILENAME.fullmatch(payload.filename) or payload.filename in {".", ".."}:
            raise HTTPException(status_code=422, detail="Filename must not contain a path.")
        ciphertext = _decode_b64(payload.ciphertext_b64, "ciphertext")
        iv = _decode_b64(payload.iv_b64, "iv")
        wrapped_key = _decode_b64(payload.wrapped_des_key_b64, "wrapped_des_key")
        if not ciphertext or len(ciphertext) % DES.block_size:
            raise HTTPException(
                status_code=422, detail="Ciphertext must contain complete DES blocks."
            )
        if len(ciphertext) > request.app.state.max_document_bytes:
            raise HTTPException(
                status_code=413, detail="Encrypted document exceeds the size limit."
            )
        if len(iv) != DES.block_size:
            raise HTTPException(status_code=422, detail="DES-CBC IV must be 8 bytes.")

        recipient_key = db.get(PublicKey, payload.recipient_key_id)
        signing_key = db.get(PublicKey, payload.signing_key_id)
        if (
            recipient_key is None
            or recipient_key.user_id != recipient_id
            or recipient_key.purpose != "encryption"
        ):
            raise HTTPException(status_code=422, detail="Recipient encryption key is invalid.")
        if (
            signing_key is None
            or signing_key.user_id != user.id
            or signing_key.purpose != "signing"
        ):
            raise HTTPException(status_code=422, detail="Sender signing key is invalid.")
        try:
            wrapped = RSA.import_key(recipient_key.public_key_pem)
            if len(wrapped_key) != wrapped.size_in_bytes():
                raise ValueError
        except (ValueError, TypeError, IndexError) as exc:
            raise HTTPException(
                status_code=422, detail="Wrapped key is not valid for the selected recipient key."
            ) from exc
        if len(wrapped_key) != wrapped.size_in_bytes():
            raise HTTPException(
                status_code=422, detail="Wrapped key is not valid for the selected recipient key."
            )

        storage_name = str(uuid4())
        storage_path = request.app.state.storage_dir / storage_name
        try:
            with storage_path.open("xb") as encrypted_file:
                encrypted_file.write(ciphertext)
            record = Document(
                relationship_id=relationship.id,
                sender_id=user.id,
                filename=payload.filename,
                storage_name=storage_name,
                ciphertext_size=len(ciphertext),
                iv=iv,
                wrapped_des_key=wrapped_key,
                recipient_key_id=recipient_key.id,
                signing_key_id=signing_key.id,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
        except Exception:
            db.rollback()
            storage_path.unlink(missing_ok=True)
            raise

        return DocumentView(
            id=record.id,
            relationship_id=record.relationship_id,
            sender_id=record.sender_id,
            filename=record.filename,
            ciphertext_size=record.ciphertext_size,
            iv_b64=base64.b64encode(record.iv).decode("ascii"),
            wrapped_des_key_b64=base64.b64encode(record.wrapped_des_key).decode("ascii"),
            recipient_key_id=record.recipient_key_id,
            signing_key_id=record.signing_key_id,
            ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
            created_at=record.created_at,
        )

    @app.get(
        "/api/relationships/{relationship_id}/documents",
        response_model=list[DocumentView],
    )
    def list_documents(
        relationship_id: str,
        request: Request,
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> list[DocumentView]:
        relationship = get_relationship(db, relationship_id)
        require_participant(relationship, user)
        documents = db.scalars(
            select(Document)
            .where(Document.relationship_id == relationship_id)
            .order_by(Document.created_at, Document.id)
        )
        results: list[DocumentView] = []
        for record in documents:
            try:
                ciphertext = (request.app.state.storage_dir / record.storage_name).read_bytes()
            except OSError as exc:
                raise HTTPException(
                    status_code=500, detail="Encrypted document is unavailable."
                ) from exc
            results.append(
                DocumentView(
                    id=record.id,
                    relationship_id=record.relationship_id,
                    sender_id=record.sender_id,
                    filename=record.filename,
                    ciphertext_size=record.ciphertext_size,
                    iv_b64=base64.b64encode(record.iv).decode("ascii"),
                    wrapped_des_key_b64=base64.b64encode(record.wrapped_des_key).decode("ascii"),
                    recipient_key_id=record.recipient_key_id,
                    signing_key_id=record.signing_key_id,
                    ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
                    created_at=record.created_at,
                )
            )
        return results

    @app.get("/api/admin/health")
    def admin_health(
        user: User = Depends(current_user),
        db: Session = Depends(get_db),
    ) -> dict[str, int | str]:
        require_role(user, "sysadmin")
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "users": db.scalar(select(func.count()).select_from(User)) or 0,
            "relationships": db.scalar(select(func.count()).select_from(Relationship)) or 0,
            "documents": db.scalar(select(func.count()).select_from(Document)) or 0,
        }

    return app


app = create_app()
