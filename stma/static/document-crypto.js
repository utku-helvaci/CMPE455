(() => {
  const IP = [
    58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4, 62, 54, 46, 38, 30, 22, 14,
    6, 64, 56, 48, 40, 32, 24, 16, 8, 57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11,
    3, 61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7,
  ];
  const FP = [
    40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31, 38, 6, 46, 14, 54, 22, 62,
    30, 37, 5, 45, 13, 53, 21, 61, 29, 36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19,
    59, 27, 34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25,
  ];
  const E = [
    32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13, 12, 13, 14, 15, 16, 17, 16, 17,
    18, 19, 20, 21, 20, 21, 22, 23, 24, 25, 24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1,
  ];
  const P = [
    16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10, 2, 8, 24, 14, 32, 27, 3, 9,
    19, 13, 30, 6, 22, 11, 4, 25,
  ];
  const PC1 = [
    57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18, 10, 2, 59, 51, 43, 35, 27, 19, 11,
    3, 60, 52, 44, 36, 63, 55, 47, 39, 31, 23, 15, 7, 62, 54, 46, 38, 30, 22, 14, 6, 61, 53,
    45, 37, 29, 21, 13, 5, 28, 20, 12, 4,
  ];
  const PC2 = [
    14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10, 23, 19, 12, 4, 26, 8, 16, 7, 27, 20, 13, 2, 41,
    52, 31, 37, 47, 55, 30, 40, 51, 45, 33, 48, 44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32,
  ];
  const SHIFTS = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1];
  const SBOX = [
    [
      14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7, 0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12,
      11, 9, 5, 3, 8, 4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0, 15, 12, 8, 2, 4, 9,
      1, 7, 5, 11, 3, 14, 10, 0, 6, 13,
    ],
    [
      15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10, 3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1,
      10, 6, 9, 11, 5, 0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15, 13, 8, 10, 1, 3, 15,
      4, 2, 11, 6, 7, 12, 0, 5, 14, 9,
    ],
    [
      10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8, 13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5,
      14, 12, 11, 15, 1, 13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7, 1, 10, 13, 0, 6,
      9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12,
    ],
    [
      7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15, 13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2,
      12, 1, 10, 14, 9, 10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4, 3, 15, 0, 6, 10,
      1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14,
    ],
    [
      2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9, 14, 11, 2, 12, 4, 7, 13, 1, 5, 0,
      15, 10, 3, 9, 8, 6, 4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14, 11, 8, 12, 7, 1,
      14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3,
    ],
    [
      12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11, 10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13,
      14, 0, 11, 3, 8, 9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6, 4, 3, 2, 12, 9, 5,
      15, 10, 11, 14, 1, 7, 6, 0, 8, 13,
    ],
    [
      4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1, 13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5,
      12, 2, 15, 8, 6, 1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2, 6, 11, 13, 8, 1, 4,
      10, 7, 9, 5, 0, 15, 14, 2, 3, 12,
    ],
    [
      13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7, 1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6,
      11, 0, 14, 9, 2, 7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8, 2, 1, 14, 7, 4, 10,
      8, 13, 15, 12, 9, 0, 3, 5, 6, 11,
    ],
  ];
  const SP = SBOX.map((box, boxIndex) =>
    box.map((value, index) => {
      const positioned = BigInt(value << (28 - boxIndex * 4));
      return Number(permute(positioned, P, 32));
    }),
  );

  function permute(value, table, inputBits) {
    let result = 0n;
    for (const position of table) {
      result = (result << 1n) | ((value >> BigInt(inputBits - position)) & 1n);
    }
    return result;
  }

  function makeSubkeys(keyBytes) {
    let key = 0n;
    for (const byte of keyBytes) key = (key << 8n) | BigInt(byte);
    const selected = permute(key, PC1, 64);
    let left = Number((selected >> 28n) & 0x0fffffffn);
    let right = Number(selected & 0x0fffffffn);
    const keys = [];
    for (const shift of SHIFTS) {
      left = ((left << shift) | (left >>> (28 - shift))) & 0x0fffffff;
      right = ((right << shift) | (right >>> (28 - shift))) & 0x0fffffff;
      const selectedKey = permute((BigInt(left) << 28n) | BigInt(right), PC2, 56);
      const roundKey = [];
      for (let box = 0; box < 8; box += 1) {
        roundKey.push(Number((selectedKey >> BigInt(42 - box * 6)) & 0x3fn));
      }
      keys.push(roundKey);
    }
    return keys;
  }

  function feistel(right, key) {
    let result = 0;
    for (let box = 0; box < 8; box += 1) {
      let chunk = 0;
      for (let bit = 0; bit < 6; bit += 1) {
        chunk =
          (chunk << 1) |
          ((right >>> (32 - E[box * 6 + bit])) & 1);
      }
      chunk ^= key[box];
      const row = ((chunk & 0x20) >>> 4) | (chunk & 1);
      const column = (chunk >>> 1) & 0x0f;
      result ^= SP[box][row * 16 + column];
    }
    return result >>> 0;
  }

  function cryptBlock(block, subkeys, decrypt = false) {
    const keys = decrypt ? [...subkeys].reverse() : subkeys;
    const state = permute(block, IP, 64);
    let left = Number((state >> 32n) & 0xffffffffn);
    let right = Number(state & 0xffffffffn);
    for (const key of keys) {
      [left, right] = [right, (left ^ feistel(right, key)) >>> 0];
    }
    return permute((BigInt(right) << 32n) | BigInt(left), FP, 64);
  }

  function readBlock(bytes, offset) {
    let value = 0n;
    for (let index = 0; index < 8; index += 1) {
      value = (value << 8n) | BigInt(bytes[offset + index]);
    }
    return value;
  }

  function writeBlock(bytes, offset, value) {
    for (let index = 7; index >= 0; index -= 1) {
      bytes[offset + index] = Number(value & 0xffn);
      value >>= 8n;
    }
  }

  function desCbcEncrypt(plainBytes, keyBytes, ivBytes) {
    const paddingLength = 8 - (plainBytes.length % 8);
    const padded = new Uint8Array(plainBytes.length + paddingLength);
    padded.set(plainBytes);
    padded.fill(paddingLength, plainBytes.length);
    const output = new Uint8Array(padded.length);
    const subkeys = makeSubkeys(keyBytes);
    let previous = readBlock(ivBytes, 0);
    for (let offset = 0; offset < padded.length; offset += 8) {
      const encrypted = cryptBlock(readBlock(padded, offset) ^ previous, subkeys);
      writeBlock(output, offset, encrypted);
      previous = encrypted;
    }
    return output;
  }

  function desCbcDecrypt(cipherBytes, keyBytes, ivBytes) {
    if (cipherBytes.length === 0 || cipherBytes.length % 8 !== 0) {
      throw new Error("The encrypted document has invalid DES blocks.");
    }
    const output = new Uint8Array(cipherBytes.length);
    const subkeys = makeSubkeys(keyBytes);
    let previous = readBlock(ivBytes, 0);
    for (let offset = 0; offset < cipherBytes.length; offset += 8) {
      const current = readBlock(cipherBytes, offset);
      writeBlock(output, offset, cryptBlock(current, subkeys, true) ^ previous);
      previous = current;
    }
    const paddingLength = output[output.length - 1];
    if (
      paddingLength < 1 ||
      paddingLength > 8 ||
      output.slice(-paddingLength).some((byte) => byte !== paddingLength)
    ) {
      throw new Error("The document could not be decrypted. Check your private key.");
    }
    return output.slice(0, output.length - paddingLength);
  }

  function runDesSelfTest() {
    const key = Uint8Array.from([0x13, 0x34, 0x57, 0x79, 0x9b, 0xbc, 0xdf, 0xf1]);
    const plain = 0x0123456789abcdefn;
    const encrypted = cryptBlock(plain, makeSubkeys(key));
    return encrypted.toString(16).padStart(16, "0");
  }

  function pemBytes(pem) {
    if (typeof pem !== "string") {
      throw new Error("The selected RSA key is missing or invalid.");
    }
    const body = pem.replace(/-----BEGIN [^-]+-----|-----END [^-]+-----|\s/g, "");
    const binary = atob(body);
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  }

  function encodeBase64(bytes) {
    let binary = "";
    const chunkSize = 0x8000;
    for (let index = 0; index < bytes.length; index += chunkSize) {
      binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
    }
    return btoa(binary);
  }

  // Failures carry a code so the page can explain them in context (a chat bubble needs a
  // shorter text than a report download), while the message stays readable on its own.
  class CryptoFailure extends Error {
    constructor(message, code) {
      super(message);
      this.code = code;
    }
  }

  // Web Crypto failures surface as opaque DOMExceptions ("The operation failed for an
  // operation-specific reason"), so each step is rewrapped with what the user can act on.
  async function describe(message, code, operation) {
    try {
      return await operation();
    } catch {
      throw new CryptoFailure(message, code);
    }
  }

  async function importPublicKey(pem, algorithm, usage, message, code = "public-key") {
    return describe(message, code, () =>
      crypto.subtle.importKey("spki", pemBytes(pem), algorithm, false, [usage]),
    );
  }

  async function importPrivateKey(pem, algorithm, usage, message) {
    return describe(message, "private-key", () =>
      crypto.subtle.importKey("pkcs8", pemBytes(pem), algorithm, false, [usage]),
    );
  }

  const PSS = { name: "RSA-PSS", hash: "SHA-256" };
  const OAEP = { name: "RSA-OAEP", hash: "SHA-256" };

  // The scheme shared by reports and chat messages:
  // 1. sign the data with the sender's signing private key (RSA-PSS, SHA-256)
  // 2. package = 4-byte signature length + signature + data
  // 3. encrypt the package with a fresh random DES key and IV (DES-CBC, PKCS#7 padding)
  // 4. wrap the DES key with RSA-OAEP: for the recipient, and for chat also for the sender
  async function signAndEncrypt({
    data,
    signingPrivatePem,
    signingPublicPem,
    recipientPublicPem,
    senderPublicPem,
    item,
  }) {
    const signingKey = await importPrivateKey(
      signingPrivatePem,
      PSS,
      "sign",
      "The loaded signing private key is not a valid RSA private key file. In the Security keys tab, load the “signing-private” PEM file you downloaded when generating keys.",
    );
    const recipientKey = await importPublicKey(
      recipientPublicPem,
      OAEP,
      "encrypt",
      "The recipient’s published encryption key is invalid. Ask them to generate new keys.",
    );
    const senderKey = senderPublicPem
      ? await importPublicKey(
          senderPublicPem,
          OAEP,
          "encrypt",
          "Your published encryption key is invalid. Generate new keys in the Security keys tab.",
        )
      : null;
    const signature = new Uint8Array(
      await describe(`The ${item} could not be signed with the loaded signing private key.`, "sign", () =>
        crypto.subtle.sign({ name: "RSA-PSS", saltLength: 32 }, signingKey, data),
      ),
    );
    const signingPublicKey = await importPublicKey(
      signingPublicPem,
      PSS,
      "verify",
      "Your published signing key is invalid. Generate new keys in the Security keys tab.",
    );
    const signingKeyMatches = await crypto.subtle.verify(
      { name: "RSA-PSS", saltLength: 32 },
      signingPublicKey,
      signature,
      data,
    );
    if (!signingKeyMatches) {
      throw new CryptoFailure(
        "The loaded signing private key does not match your latest published signing key. Load the “signing-private” file from your most recent key generation (not the encryption one).",
        "signing-key-mismatch",
      );
    }
    const payload = new Uint8Array(4 + signature.length + data.length);
    new DataView(payload.buffer).setUint32(0, signature.length);
    payload.set(signature, 4);
    payload.set(data, 4 + signature.length);

    const desKey = crypto.getRandomValues(new Uint8Array(8));
    const iv = crypto.getRandomValues(new Uint8Array(8));
    const ciphertext = desCbcEncrypt(payload, desKey, iv);
    const wrapFor = async (key) =>
      new Uint8Array(
        await describe(`The ${item} key could not be encrypted with RSA.`, "wrap", () =>
          crypto.subtle.encrypt({ name: "RSA-OAEP" }, key, desKey),
        ),
      );
    const sealed = {
      ciphertext_b64: encodeBase64(ciphertext),
      iv_b64: encodeBase64(iv),
      wrapped_des_key_b64: encodeBase64(await wrapFor(recipientKey)),
    };
    if (senderKey) sealed.sender_wrapped_des_key_b64 = encodeBase64(await wrapFor(senderKey));
    return sealed;
  }

  // The reverse: unwrap the DES key with the reader's encryption private key, decrypt,
  // split the package, and only return the data if the sender's signature is valid.
  async function decryptAndVerify({ ciphertext, iv, wrappedKey, privatePem, signerPublicPem, item }) {
    const privateKey = await importPrivateKey(
      privatePem,
      OAEP,
      "decrypt",
      "The loaded decryption private key is not a valid RSA private key file. In the Security keys tab, load the “encryption-private” PEM file you downloaded when generating keys.",
    );
    const signerKey = await importPublicKey(
      signerPublicPem,
      PSS,
      "verify",
      `The sender’s published signing key is invalid, so the ${item} cannot be verified.`,
      "signer-key",
    );
    const desKey = new Uint8Array(
      await describe(
        `This ${item} cannot be decrypted with the loaded decryption private key. It was encrypted for a different key: load the “encryption-private” file (not the signing one) that matches the key version shown on the ${item}.`,
        "wrong-key",
        () => crypto.subtle.decrypt({ name: "RSA-OAEP" }, privateKey, wrappedKey),
      ),
    );
    const damaged = () => new CryptoFailure(`The ${item} is damaged and cannot be decrypted.`, "damaged");
    if (desKey.length !== 8 || iv.length !== 8) throw damaged();
    let payload;
    try {
      payload = desCbcDecrypt(ciphertext, desKey, iv);
    } catch {
      throw damaged();
    }
    if (payload.length < 4) throw damaged();
    const signatureSize = new DataView(
      payload.buffer,
      payload.byteOffset,
      payload.byteLength,
    ).getUint32(0);
    if (signatureSize === 0 || signatureSize + 4 > payload.length) throw damaged();
    const signature = payload.slice(4, signatureSize + 4);
    const data = payload.slice(signatureSize + 4);
    const verified = await crypto.subtle.verify(
      { name: "RSA-PSS", saltLength: 32 },
      signerKey,
      signature,
      data,
    );
    if (!verified) {
      throw new CryptoFailure(
        `Signature verification failed; the ${item} was changed or the signer key is wrong.`,
        "signature",
      );
    }
    return data;
  }

  function toPem(label, bytes) {
    const encoded = encodeBase64(new Uint8Array(bytes));
    const lines = encoded.match(/.{1,64}/g) || [];
    return `-----BEGIN ${label}-----\n${lines.join("\n")}\n-----END ${label}-----\n`;
  }

  async function generateKeys() {
    const signingPair = await crypto.subtle.generateKey(
      {
        name: "RSA-PSS",
        modulusLength: 3072,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256",
      },
      true,
      ["sign", "verify"],
    );
    const encryptionPair = await crypto.subtle.generateKey(
      {
        name: "RSA-OAEP",
        modulusLength: 3072,
        publicExponent: new Uint8Array([1, 0, 1]),
        hash: "SHA-256",
      },
      true,
      ["encrypt", "decrypt"],
    );
    return {
      signingPublicPem: toPem(
        "PUBLIC KEY",
        await crypto.subtle.exportKey("spki", signingPair.publicKey),
      ),
      signingPrivatePem: toPem(
        "PRIVATE KEY",
        await crypto.subtle.exportKey("pkcs8", signingPair.privateKey),
      ),
      encryptionPublicPem: toPem(
        "PUBLIC KEY",
        await crypto.subtle.exportKey("spki", encryptionPair.publicKey),
      ),
      encryptionPrivatePem: toPem(
        "PRIVATE KEY",
        await crypto.subtle.exportKey("pkcs8", encryptionPair.privateKey),
      ),
    };
  }

  self.onmessage = async (event) => {
    const { id, action, payload } = event.data;
    try {
      if (action === "generate") {
        self.postMessage({ id, result: await generateKeys() });
      } else if (action === "encrypt") {
        const result = await signAndEncrypt({
          data: new Uint8Array(payload.document),
          signingPrivatePem: payload.signingPrivatePem,
          signingPublicPem: payload.signingPublicPem,
          recipientPublicPem: payload.recipientPublicPem,
          item: "report",
        });
        self.postMessage({ id, result });
      } else if (action === "decrypt") {
        const result = await decryptAndVerify({
          ciphertext: payload.ciphertext,
          iv: payload.iv,
          wrappedKey: payload.wrappedKey,
          privatePem: payload.recipientPrivatePem,
          signerPublicPem: payload.signerPublicPem,
          item: "report",
        });
        self.postMessage({ id, result }, [result.buffer]);
      } else if (action === "encrypt-message") {
        const result = await signAndEncrypt({
          data: new TextEncoder().encode(payload.text),
          signingPrivatePem: payload.signingPrivatePem,
          signingPublicPem: payload.signingPublicPem,
          recipientPublicPem: payload.recipientPublicPem,
          senderPublicPem: payload.senderPublicPem,
          item: "message",
        });
        self.postMessage({ id, result });
      } else if (action === "decrypt-message") {
        const data = await decryptAndVerify({ ...payload, item: "message" });
        let text;
        try {
          text = new TextDecoder("utf-8", { fatal: true }).decode(data);
        } catch {
          throw new CryptoFailure("The message is damaged and cannot be decrypted.", "damaged");
        }
        self.postMessage({ id, result: text });
      } else if (action === "self-test") {
        self.postMessage({ id, result: runDesSelfTest() });
      } else {
        throw new Error("Unsupported cryptographic operation.");
      }
    } catch (error) {
      self.postMessage({
        id,
        error: error instanceof Error ? error.message : "Cryptographic operation failed.",
        code: error instanceof CryptoFailure ? error.code : "failed",
      });
    }
  };
})();
