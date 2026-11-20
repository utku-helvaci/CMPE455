Yes, the teacher and student share **public keys**, but a public key is for locking something *for its owner*—it does not let the other person decrypt that owner’s files.

### How the relationship’s keys are used

```text
Student                                      Teacher
-------                                      -------
Public encryption key  --------------------> Used to encrypt something for student
Private encryption key (kept secret)         Used by student to decrypt it

Used to encrypt something for teacher  <---- Public encryption key
Teacher's private encryption key               Used by teacher to decrypt it
```

They also share **signing public keys** so each can check the other person’s signatures. Signing private keys stay with their owners.

### Student sends a report to the teacher

```text
STUDENT'S BROWSER                             SERVER                         TEACHER'S BROWSER

Report
  │
  ├─ Sign with student's private signing key
  │
  ├─ Encrypt report + signature with a new DES key
  │
  └─ Lock that DES key with teacher's public encryption key
       │
       └──────── encrypted report + locked DES key ────────>
                                                   Store and forward package
                                                                 │
                                                                 └───────>
                                                         Teacher unlocks DES key
                                                         with teacher's private
                                                         encryption key
                                                                 │
                                                         Decrypt report
                                                         Verify using student's
                                                         public signing key
```

When the teacher sends a report to the student, the process is reversed: the teacher signs with their private signing key, and the DES key is locked with the **student’s public encryption key**.

### Chat messages

Chat uses the **same scheme as reports**. The browser signs each message with the sender's private signing key, encrypts it with a new DES key, and locks that DES key with RSA. The only difference is that the DES key is locked **twice**: once with the partner's public encryption key and once with the sender's own public encryption key. That way both people can read the conversation later, each with their own private key. The server stores and forwards only ciphertext.

So: **the server doesn’t encrypt files or messages when sending them back**. It stores and forwards packages already encrypted by the sender’s browser.
