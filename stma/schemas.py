from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")
    last_name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")
    school_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")
    last_name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")
    school_id: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=256)
    role: Literal["evaluator"] = "evaluator"


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: str
    first_name: str | None = None
    last_name: str | None = None
    school_id: str | None = None


class TokenView(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RelationshipCreate(BaseModel):
    student_id: str
    evaluator_id: str


class RelationshipView(BaseModel):
    id: str
    student_id: str
    evaluator_id: str
    student_username: str
    evaluator_username: str
    student_name: str
    evaluator_name: str


class PublicKeyCreate(BaseModel):
    purpose: Literal["signing", "encryption"]
    public_key_pem: str = Field(min_length=100, max_length=4096)


class PublicKeyView(BaseModel):
    id: str
    user_id: str
    purpose: str
    version: int
    public_key_pem: str
    created_at: datetime


class MessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class MessageView(BaseModel):
    id: str
    relationship_id: str
    sender_id: str
    body: str
    created_at: datetime


class DocumentUpload(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    ciphertext_b64: str = Field(min_length=1)
    iv_b64: str = Field(min_length=1, max_length=32)
    wrapped_des_key_b64: str = Field(min_length=1, max_length=4096)
    recipient_key_id: str
    signing_key_id: str


class DocumentView(BaseModel):
    id: str
    relationship_id: str
    sender_id: str
    filename: str
    ciphertext_size: int
    iv_b64: str
    wrapped_des_key_b64: str
    recipient_key_id: str
    signing_key_id: str
    ciphertext_b64: str
    created_at: datetime
