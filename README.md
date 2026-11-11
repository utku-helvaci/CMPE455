# STMA

Summer Training Management Application: a Python API for student–evaluator chat and exchange of signed, DES-encrypted reports. The server stores encrypted document bytes; clients retain their private RSA keys.

## Current implementation

- FastAPI and Uvicorn provide the HTTP API.
- PostgreSQL is the intended shared database. SQLite is the local-development default.
- SQLAlchemy manages database records.
- Argon2id hashes account passwords; login tokens are random, expire after 12 hours, and are stored only as SHA-256 digests.
- Client-side document processing uses RSA-PSS/SHA-256 signatures, DES-CBC with PKCS#7 padding, and RSA-OAEP/SHA-256 to protect the DES key. There is no HMAC or second document cipher.
- The recipient verifies the signature after decryption. A failed decryption or signature check is an error, not a successful receipt.
- Clients can generate 3072-bit RSA key pairs with `stma.crypto.generate_rsa_key_pair()`. Publish only the public key, keep private keys on the client computer, and restrict local access to their files.
- Chat is sent over HTTPS/WSS when deployed behind TLS. This initial version stores chat text in PostgreSQL, so it is not end-to-end encrypted.
- Sysadmin health endpoints expose service counts, not chat or document contents. Database administrators can still access database records; restrict database credentials accordingly.

DES is used because the course assignment requires it. DES has a short effective key and is not appropriate for real sensitive documents.

## Local development

Use Python 3.12 or newer. Create a virtual environment and install dependencies:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For a quick single-computer run, leave `DATABASE_URL` unset to use a local SQLite database. To use PostgreSQL, create a database and role, then set the connection string (see `.env.example` for its format). `DATABASE_URL` and `STMA_STORAGE_DIR` are read from the process environment.

Create the initial Sysadmin account; the password is requested interactively and is not placed in shell history:

```sh
python -m stma.cli create-admin sysadmin
```

Start the API:

```sh
uvicorn stma.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/docs` to explore the API. For a two-computer demonstration, set the server host address reachable from the client computers and use a TLS reverse proxy such as Nginx. Do not expose the development server directly to an untrusted network.

## Initial workflow

1. Register student and evaluator accounts at `POST /api/auth/register`, or have a Sysadmin create them at `POST /api/admin/users`.
2. Log in at `POST /api/auth/login` and use the returned bearer token for subsequent calls.
3. The Sysadmin assigns the client accounts using `POST /api/admin/relationships`.
4. Each participant generates separate signing and encryption RSA key pairs locally and publishes the public keys to `POST /api/relationships/{id}/keys`. Verify key fingerprints out of band before relying on them.
5. The sender signs and encrypts the report locally, wraps the DES key for the recipient, then sends the ciphertext and key references to `POST /api/relationships/{id}/documents`.
6. The recipient downloads the encrypted package from `GET /api/relationships/{id}/documents`, unwraps the DES key locally, decrypts the report, and verifies its signature with the sender's signing public key.
7. Participants send and read chat messages at the relationship's `/messages` endpoints. Delivery is confirmed by the API response.
8. A Sysadmin checks `GET /api/admin/health`.

Participants manually rotate their RSA keys every 90 days. Each newly published key gets a higher version, and older public-key versions remain available so archived exchanges can identify the corresponding recipient private key. The server does not enforce the schedule or revoke compromised keys. The project still needs an explicit key-fingerprint verification screen/process, automated rotation reminders, revocation policy, database migrations, and a user interface beyond the API explorer.

## Tests

```sh
pytest
```
