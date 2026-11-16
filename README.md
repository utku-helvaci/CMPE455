# STMA

Summer Training Management Application: a Python API for student–evaluator chat and exchange of signed, DES-encrypted reports. The server stores encrypted document bytes; clients retain their private RSA keys.

## Current implementation

- A responsive sign-in page and role-aware workspace are served at `/`. Students and evaluators can use assigned conversations, exchange chat messages, manage RSA public keys, and send/receive signed DES-encrypted reports. Sysadmins see operational health counts only.
- Students and teachers can register with their name, surname, school ID, and password. New accounts remain pending until a Sysadmin assigns the student or evaluator role from the admin workspace; pending users cannot sign in. Existing account roles are preserved. Student and evaluator school IDs are also their login names; Sysadmins can use a separate username.
- Teachers add students by entering the exact school ID, without browsing a directory. Teachers can end a relationship; this removes active access but retains the old messages and encrypted files. Re-adding the same student restores that relationship and its history.
- Sysadmins can permanently delete a student or evaluator account from the admin workspace. This also removes the account's relationships, messages, public keys, report records, and stored encrypted report files; the action cannot be undone. Sysadmin accounts are not exposed in the user list.
- Existing SQLite databases are updated at startup to add the new student profile columns; existing accounts remain in place.
- FastAPI and Uvicorn provide the HTTP API.
- PostgreSQL is the intended shared database. SQLite is the local-development default.
- SQLAlchemy manages database records.
- Argon2id hashes account passwords; login tokens are random, expire after 12 hours, and are stored only as SHA-256 digests.
- Client-side document processing uses RSA-PSS/SHA-256 signatures, DES-CBC with PKCS#7 padding, and RSA-OAEP/SHA-256 to protect the DES key. There is no HMAC or second document cipher.
- The recipient verifies the signature after decryption. A failed decryption or signature check is an error, not a successful receipt.
- Clients can generate 3072-bit RSA key pairs with `stma.crypto.generate_rsa_key_pair()`. Publish only the public key, keep private keys on the client computer, and restrict local access to their files.
- Chat is sent over HTTPS when deployed behind TLS and the workspace refreshes messages every three seconds. Messages are stored as plaintext in PostgreSQL, so they are not end-to-end encrypted.
- Sysadmin health endpoints expose service counts, not chat or document contents. Database administrators can still access database records; restrict database credentials accordingly.

DES is used because the course assignment requires it. DES has a short effective key and is not appropriate for real sensitive documents.

## Local development

Use Python 3.12 or newer. Create a virtual environment and install dependencies:

```sh
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
```

`requirements.txt` lists what the server needs to run; `requirements-dev.txt` adds the test tools on top of it.

| Package | Used for |
| --- | --- |
| `fastapi` | HTTP API and request validation (brings in Pydantic and Starlette) |
| `uvicorn` | ASGI server that runs the app |
| `sqlalchemy` | Database models and queries |
| `psycopg[binary]` | PostgreSQL driver; not used when running on SQLite |
| `pycryptodome` | RSA and DES for `stma.crypto` and server-side key and ciphertext validation |
| `argon2-cffi` | Argon2id password hashing |
| `pytest`, `httpx` (dev only) | Test suite and FastAPI's test client |

For a quick single-computer run, leave `DATABASE_URL` unset to use a local SQLite database. To use PostgreSQL, create a database and role, then set the connection string (see `.env.example` for its format). `DATABASE_URL` and `STMA_STORAGE_DIR` are read from the process environment.

Create the initial Sysadmin account; the password is requested interactively and is not placed in shell history:

```sh
python -m stma.cli create-admin sysadmin
```

If a Sysadmin password is forgotten, reset it interactively without changing the account or its role. Existing sessions for that Sysadmin are revoked:

```sh
python -m stma.cli reset-admin-password sysadmin
```

Start the API:

```sh
uvicorn stma.main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/` for the sign-in page and workspace, or `http://localhost:8000/docs` to explore the API. The page uses browser Web Crypto for 3072-bit RSA-PSS signatures and RSA-OAEP key wrapping, and a local JavaScript DES-CBC implementation for documents. RSA private keys are generated in the browser and downloaded only when the user clicks the provided download links. The browser keeps them in memory only for the current tab; the server receives only public keys. Downloaded private-key PEM files are not password-encrypted, so protect them with your device's access controls and keep secure backups. Verify the first client key out-of-band with its partner. Never use untrusted client devices for private keys.

For a two-computer demonstration, set the server host address reachable from the client computers and use a TLS reverse proxy such as Nginx. Do not expose the development server directly to an untrusted network.

## Headless Docker server on a LAN

The Docker Compose deployment runs the STMA app, PostgreSQL 16, and Nginx as separate containers. It persists the database and encrypted report storage in Docker volumes, publishes HTTPS on port 8000, and redirects HTTP on port 8001 to HTTPS. The app container installs only the packages in `requirements.txt`, and the Nginx container is a plain Nginx used as a TLS reverse proxy with no extra modules.

**Linux and macOS:** install Docker Engine or Docker Desktop with the Compose plugin, and OpenSSL. From the project root, run:

```sh
./deploy/start.sh
```

**Windows:** install Docker Desktop and start it. Nothing else is needed; the script runs OpenSSL inside a container. Double-click `deploy\start.bat`, or from the project root in PowerShell run:

```powershell
powershell -ExecutionPolicy Bypass -File deploy\start.ps1
```

The script generates a database password and a local certificate authority, then builds and starts the containers. To use a particular network address instead of automatic detection, set the server computer's LAN IP before the first run: `STMA_LAN_IP=192.168.1.20 ./deploy/start.sh`, or in PowerShell `$env:STMA_LAN_IP = "192.168.1.20"` followed by the command above. Create the first Sysadmin account in a terminal (the `docker compose` commands in this section are the same on every operating system):

```sh
docker compose --env-file .env.docker run --rm app python -m stma.cli create-admin sysadmin
```

To recover a forgotten Docker-deployment Sysadmin password, run:

```sh
docker compose --env-file .env.docker run --rm app python -m stma.cli reset-admin-password sysadmin
```

Open `https://<server-lan-ip>:8000/` from the server or another computer on the same trusted LAN. For browser Web Crypto to work, install `deploy/certs/ca.crt` as a trusted certificate authority on each client computer; the CA private key remains on the server and is not mounted into a container. The certificate is valid for the LAN IP chosen at setup. If that address changes, update `STMA_LAN_IP` in `.env.docker` and rerun the start script.

On Windows, `certutil -addstore -user Root deploy\certs\ca.crt` trusts the CA for Chrome and Edge. Firefox keeps its own certificate store: import `ca.crt` under Settings → Privacy & Security → Certificates → View Certificates → Authorities.

The deployment uses a Docker bridge network; PostgreSQL and the app port are not published to the host. Only Nginx is reachable externally. Allow inbound TCP ports 8000 (HTTPS) and, if desired, 8001 (HTTP redirect) in the server's firewall for the trusted LAN only. Do not forward these ports from a router to the public internet. Keep `.env.docker`, `deploy/certs/ca.key`, the database volume, and the encrypted-document volume backed up and restricted. `docker compose --env-file .env.docker down` stops the server without deleting its data; do not use `down -v` unless you intend to permanently remove the database and uploaded files.

### View the Docker database with HeidiSQL

The PostgreSQL port is intentionally not exposed on the LAN. To connect HeidiSQL on the Docker host, run this temporary relay from the project directory and leave the terminal open:

```sh
docker run --rm --name stma-db-viewer \
  --network "$(docker inspect "$(docker compose --env-file .env.docker ps -q db)" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}')" \
  -p 127.0.0.1:5433:5433 \
  alpine/socat TCP-LISTEN:5433,fork,reuseaddr TCP:db:5432
```

The command above is for Linux, macOS, or Git Bash. In Windows PowerShell, run this instead:

```powershell
$db = docker compose --env-file .env.docker ps -q db
$network = docker inspect $db --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{end}}'
docker run --rm --name stma-db-viewer --network $network -p 127.0.0.1:5433:5433 alpine/socat TCP-LISTEN:5433,fork,reuseaddr TCP:db:5432
```

In HeidiSQL, create a **PostgreSQL** session with:

- **Hostname / IP:** `127.0.0.1`
- **Port:** `5433`
- **User:** `stma`
- **Database:** `stma`
- **Password:** the value of `STMA_POSTGRES_PASSWORD` in the local `.env.docker` file

The password is a local deployment secret. Do not paste it into chat, screenshots, or this README, and do not commit `.env.docker`. The relay binds only to localhost; it does not expose PostgreSQL to other computers. Stop it with **Ctrl+C** when finished. To connect from a different computer, use an SSH tunnel to the Docker host rather than publishing PostgreSQL to the LAN.

## Initial workflow

1. Students and teachers register at `/` with name, surname, school ID, and a password of at least 12 characters. No keys or key files are needed during registration.
2. A Sysadmin signs in, opens **Assign account roles**, and assigns or updates each account as a student or teacher/evaluator. Role changes are blocked while an account has an active student–teacher relationship.
3. Students and teachers log in at `/` with their school ID and password after role assignment. Sysadmins use their provisioned username.
4. Teachers enter a student's exact school ID in the workspace to add the relationship. Sysadmins can also create relationships using `POST /api/admin/relationships`.
5. Each participant generates separate signing and encryption RSA key pairs locally and publishes the public keys to `POST /api/relationships/{id}/keys`. Verify key fingerprints out of band before relying on them.
6. The sender signs and encrypts the report locally, wraps the DES key for the recipient, then sends the ciphertext and key references to `POST /api/relationships/{id}/documents`.
7. The recipient downloads the encrypted package from `GET /api/relationships/{id}/documents`, unwraps the DES key locally, decrypts the report, and verifies its signature with the sender's signing public key.
8. Participants send and read chat messages at the relationship's `/messages` endpoints. Delivery is confirmed by the API response.
9. A Sysadmin checks `GET /api/admin/health`.

The workspace provides SHA-256 public-key fingerprints for users to compare through a trusted channel. Participants manually rotate their RSA keys every 90 days. Each newly published key gets a higher version, and older public-key versions remain available so archived exchanges can identify the corresponding recipient private key. The server does not enforce the schedule or revoke compromised keys. Key backup and compromise/revocation procedures remain manual.

## Tests

Install `requirements-dev.txt` as described under Local development, then run:

```sh
pytest
```
