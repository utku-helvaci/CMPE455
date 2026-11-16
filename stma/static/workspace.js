const workspace = document.querySelector("#workspace");
const workspaceLoginView = document.querySelector("#login-view");
const loginForm = document.querySelector("#login-form");
const clientWorkspace = document.querySelector("#client-workspace");
const adminWorkspace = document.querySelector("#admin-workspace");
const relationshipList = document.querySelector("#relationship-list");
const emptyWorkspace = document.querySelector("#workspace-empty");
const relationshipWorkspace = document.querySelector("#relationship-workspace");
const chatMessages = document.querySelector("#chat-messages");
const chatForm = document.querySelector("#chat-form");
const chatInput = document.querySelector("#chat-input");
const documentList = document.querySelector("#document-list");
const documentInput = document.querySelector("#document-file");
const keyList = document.querySelector("#key-list");
const logoutButton = document.querySelector("#logout-button");
const logoutMessage = document.querySelector("#logout-message");
const addStudentForm = document.querySelector("#add-student-form");

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

const state = {
  token: null,
  user: null,
  relationships: [],
  relationship: null,
  keys: [],
  documentIds: "",
  pollTimer: null,
  worker: null,
  operationId: 0,
  pendingCrypto: new Map(),
  loadId: 0,
  signingPrivatePem: null,
  encryptionPrivatePem: null,
};

function showInlineMessage(id, message, success = false) {
  const element = document.querySelector(`#${id}`);
  element.textContent = message;
  element.hidden = false;
  element.classList.toggle("success-message", success);
}

function hideInlineMessage(id) {
  const element = document.querySelector(`#${id}`);
  element.hidden = true;
  element.classList.remove("success-message");
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        Authorization: `Bearer ${state.token}`,
        ...options.headers,
      },
    });
  } catch {
    throw new Error("Could not reach STMA. Check your connection and try again.");
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    if (response.status === 401) {
      throw new ApiError("Your session expired. Please sign in again.", 401);
    }
    throw new ApiError(
      typeof body?.detail === "string" ? body.detail : "The request failed.",
      response.status,
    );
  }
  if (response.status === 204) return null;
  return response.json();
}

function startCryptoWorker() {
  state.worker = new Worker("/static/document-crypto.js");
  state.worker.addEventListener("message", (event) => {
    const pending = state.pendingCrypto.get(event.data.id);
    if (!pending) return;
    state.pendingCrypto.delete(event.data.id);
    if (event.data.error) {
      pending.reject(new Error(event.data.error));
    } else {
      pending.resolve(event.data.result);
    }
  });
  state.worker.addEventListener("error", () => {
    for (const pending of state.pendingCrypto.values()) {
      pending.reject(new Error("Document cryptography failed in the browser."));
    }
    state.pendingCrypto.clear();
  });
}

function cryptoRequest(action, payload, transfer = []) {
  if (!state.worker) startCryptoWorker();
  const id = ++state.operationId;
  return new Promise((resolve, reject) => {
    state.pendingCrypto.set(id, { resolve, reject });
    state.worker.postMessage({ id, action, payload }, transfer);
  });
}

function initials(name) {
  return name
    .split(/[_. -]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function counterpartFor(relationship) {
  const isStudent = state.user.role === "student";
  return {
    id: isStudent ? relationship.evaluator_id : relationship.student_id,
    name: isStudent ? relationship.evaluator_name : relationship.student_name,
    role: isStudent ? "Evaluator" : "Student",
  };
}

function renderRelationships() {
  relationshipList.replaceChildren();
  for (const relationship of state.relationships) {
    const counterpart = counterpartFor(relationship);
    const button = document.createElement("button");
    button.className = "relationship-item";
    button.type = "button";
    button.dataset.relationshipId = relationship.id;
    button.classList.toggle("active", state.relationship?.id === relationship.id);

    const avatar = document.createElement("span");
    avatar.className = "avatar";
    avatar.textContent = initials(counterpart.name);
    const copy = document.createElement("span");
    copy.className = "relationship-copy";
    const name = document.createElement("span");
    name.className = "relationship-name";
    name.textContent = counterpart.name;
    const role = document.createElement("span");
    role.className = "relationship-role";
    role.textContent = counterpart.role;
    copy.append(name, role);
    button.append(avatar, copy);
    button.addEventListener("click", () => selectRelationship(relationship.id));
    relationshipList.append(button);
  }

  if (state.relationships.length === 0) {
    setEmptyWorkspace();
  }
}

function setEmptyWorkspace(message = "") {
  const isEvaluator = state.user?.role === "evaluator";
  const hasRelationships = state.relationships.length > 0;
  let title;
  let description;
  if (message) {
    title = "Relationship ended";
    description = message;
  } else if (hasRelationships) {
    title = "Your workspace is ready";
    description = isEvaluator
      ? "Choose a student on the left to view messages and shared reports, or add another student by School ID."
      : "Choose your teacher on the left to view messages and shared reports.";
  } else if (isEvaluator) {
    title = "Choose a student to work with";
    description = "Add a student using their exact School ID. You can end a relationship at any time.";
  } else {
    title = "No teacher has selected you yet";
    description =
      "A teacher can add you using your School ID. Once they do, your conversation and report exchange will appear here.";
  }
  document.querySelector("#empty-title").textContent = title;
  document.querySelector("#empty-description").textContent = description;
  emptyWorkspace.hidden = false;
  relationshipWorkspace.hidden = true;
  document.querySelector("#disown-student").hidden = true;
}

async function startWorkspace(token, user) {
  state.token = token;
  state.user = user;
  state.relationship = null;
  state.relationships = [];
  state.keys = [];
  state.signingPrivatePem = null;
  state.encryptionPrivatePem = null;
  workspaceLoginView.hidden = true;
  workspace.hidden = false;
  document.querySelector("#workspace-account-name").textContent =
    [user.first_name, user.last_name].filter(Boolean).join(" ") || user.username;
  document.querySelector("#workspace-account-role").textContent = user.role;
  document.title = `STMA Workspace · ${user.username}`;

  if (user.role === "sysadmin") {
    addStudentForm.hidden = true;
    clientWorkspace.hidden = true;
    adminWorkspace.hidden = false;
    await refreshAdminDashboard();
    return;
  }

  adminWorkspace.hidden = true;
  clientWorkspace.hidden = false;
  addStudentForm.hidden = user.role !== "evaluator";
  state.relationships = await api("/api/relationships");
  renderRelationships();
  setEmptyWorkspace();
}

async function stopWorkspace() {
  clearInterval(state.pollTimer);
  state.pollTimer = null;
  state.worker?.terminate();
  state.worker = null;
  for (const pending of state.pendingCrypto.values()) {
    pending.reject(new Error("Signed out."));
  }
  state.pendingCrypto.clear();
  state.token = null;
  state.user = null;
  window.clearAccessToken?.();
  state.relationship = null;
  state.relationships = [];
  state.keys = [];
  state.signingPrivatePem = null;
  state.encryptionPrivatePem = null;
  document.querySelector("#signing-private-key").value = "";
  document.querySelector("#encryption-private-key").value = "";
  workspace.hidden = true;
  document.title = "Sign in · STMA";
  logoutMessage.hidden = true;
  workspaceLoginView.hidden = false;
  loginForm.reset();
  document.querySelector("#username").focus();
}

async function selectRelationship(relationshipId) {
  state.relationship = state.relationships.find((item) => item.id === relationshipId) || null;
  if (!state.relationship) return;
  const requestId = ++state.loadId;
  clearInterval(state.pollTimer);
  renderRelationships();
  const counterpart = counterpartFor(state.relationship);
  document.querySelector("#counterpart-role").textContent = counterpart.role;
  document.querySelector("#counterpart-name").textContent = counterpart.name;
  document.querySelector("#disown-student").hidden = state.user.role !== "evaluator";
  emptyWorkspace.hidden = true;
  relationshipWorkspace.hidden = false;
  setActivePanel("chat-panel");
  hideInlineMessage("chat-message");
  hideInlineMessage("document-message");
  hideInlineMessage("key-message");

  try {
    const [keys, messages, documents] = await Promise.all([
      api(`/api/relationships/${relationshipId}/keys`),
      api(`/api/relationships/${relationshipId}/messages`),
      api(`/api/relationships/${relationshipId}/documents`),
    ]);
    if (requestId !== state.loadId) return;
    state.keys = keys;
    renderKeys();
    renderMessages(messages);
    renderDocuments(documents);
    setConnectionStatus(true);
    state.pollTimer = setInterval(() => refreshMessages(relationshipId), 3000);
  } catch (error) {
    if (requestId === state.loadId) {
      showInlineMessage("chat-message", error.message);
    }
  }
}

function setActivePanel(panelId) {
  for (const tab of document.querySelectorAll(".workspace-tab")) {
    const active = tab.dataset.panel === panelId;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  }
  for (const panel of document.querySelectorAll(".workspace-panel")) {
    panel.hidden = panel.id !== panelId;
  }
}

function setConnectionStatus(connected) {
  const status = document.querySelector(".connection-status");
  status.classList.toggle("offline", !connected);
  status.textContent = connected ? "Connected" : "Connection lost · retrying";
  const indicator = document.createElement("span");
  indicator.setAttribute("aria-hidden", "true");
  status.prepend(indicator);
}

function renderMessages(messages) {
  const wasNearBottom =
    chatMessages.scrollHeight - chatMessages.scrollTop - chatMessages.clientHeight < 100;
  chatMessages.replaceChildren();
  if (messages.length === 0) {
    const empty = document.createElement("p");
    empty.className = "chat-empty";
    empty.textContent = "No messages yet. Send a message to start the conversation.";
    chatMessages.append(empty);
    return;
  }

  for (const message of messages) {
    const own = message.sender_id === state.user.id;
    const row = document.createElement("article");
    row.className = `chat-row${own ? " own" : ""}`;
    const bubble = document.createElement("div");
    bubble.className = "chat-bubble";
    const meta = document.createElement("div");
    meta.className = "chat-meta";
    const author = document.createElement("span");
    author.textContent = own ? "You" : counterpartFor(state.relationship).name;
    const date = new Date(message.created_at);
    const time = document.createElement("time");
    time.dateTime = message.created_at;
    time.textContent = date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    meta.append(author, time);
    const body = document.createElement("div");
    body.textContent = message.body;
    bubble.append(meta, body);
    row.append(bubble);
    chatMessages.append(row);
  }
  if (wasNearBottom) chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function refreshMessages(relationshipId) {
  if (state.relationship?.id !== relationshipId) return;
  try {
    const base = `/api/relationships/${relationshipId}`;
    const [messages, keys, documentIds] = await Promise.all([
      api(`${base}/messages`),
      api(`${base}/keys`),
      api(`${base}/documents/ids`),
    ]);
    if (state.relationship?.id !== relationshipId) return;
    setConnectionStatus(true);
    hideInlineMessage("chat-message");
    renderMessages(messages);
    // Re-render only on change so in-progress buttons and key download links survive polling.
    const keysChanged =
      keys.map((key) => key.id).join(",") !== state.keys.map((key) => key.id).join(",");
    if (keysChanged) {
      state.keys = keys;
      renderKeys();
    }
    if (documentIds.join(",") !== state.documentIds) {
      const documents = await api(`${base}/documents`);
      if (state.relationship?.id === relationshipId) renderDocuments(documents);
    }
  } catch (error) {
    setConnectionStatus(false);
    if (error instanceof ApiError && error.status === 404) {
      try {
        state.relationships = await api("/api/relationships");
        const stillAssigned = state.relationships.some((item) => item.id === relationshipId);
        renderRelationships();
        if (!stillAssigned && state.relationship?.id === relationshipId) {
          state.relationship = null;
          clearInterval(state.pollTimer);
          state.pollTimer = null;
          setEmptyWorkspace("This relationship has ended. Its history remains stored.");
        }
      } catch (refreshError) {
        showInlineMessage("chat-message", refreshError.message);
      }
    } else if (error instanceof ApiError && error.status === 401) {
      await stopWorkspace();
    } else {
      showInlineMessage("chat-message", error.message);
    }
  }
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function renderDocuments(documents) {
  state.documentIds = documents.map((item) => item.id).join(",");
  document.querySelector("#document-count").textContent = String(documents.length);
  documentList.replaceChildren();
  if (documents.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-list";
    empty.textContent = "No reports have been shared in this relationship yet.";
    documentList.append(empty);
    return;
  }
  for (const documentRecord of documents) {
    const item = document.createElement("article");
    item.className = "document-item";
    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = "▤";
    const info = document.createElement("div");
    info.className = "document-info";
    const name = document.createElement("div");
    name.className = "document-name";
    name.textContent = documentRecord.filename;
    const subtitle = document.createElement("div");
    subtitle.className = "document-subtitle";
    const senderName =
      documentRecord.sender_id === state.user.id ? "You" : counterpartFor(state.relationship).name;
    const recipientKey = state.keys.find((key) => key.id === documentRecord.recipient_key_id);
    const recipientKeyVersion = recipientKey
      ? ` · Recipient encryption key v${recipientKey.version}`
      : "";
    subtitle.textContent = `${senderName} · ${formatBytes(
      documentRecord.ciphertext_size,
    )}${recipientKeyVersion} · ${new Date(documentRecord.created_at).toLocaleDateString()}`;
    const sentByCurrentUser = documentRecord.sender_id === state.user.id;
    const download = document.createElement("span");
    download.className = sentByCurrentUser ? "document-state" : "download-button";
    if (sentByCurrentUser) {
      download.textContent = "Sent";
    } else {
      const downloadButton = document.createElement("button");
      downloadButton.type = "button";
      downloadButton.className = "download-button";
      downloadButton.textContent = "Verify & download";
      downloadButton.addEventListener("click", () => receiveDocument(documentRecord, downloadButton));
      info.append(name, subtitle);
      item.append(icon, info, downloadButton);
      documentList.append(item);
      continue;
    }
    info.append(name, subtitle);
    item.append(icon, info, download);
    documentList.append(item);
  }
}

function pemToBytes(pem) {
  const body = pem.replace(/-----BEGIN [^-]+-----|-----END [^-]+-----|\s/g, "");
  const binary = atob(body);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function base64ToBytes(value) {
  const binary = atob(value);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

async function receiveDocument(record, button) {
  hideInlineMessage("document-message");
  button.disabled = true;
  const originalLabel = button.textContent;
  button.textContent = "Verifying…";
  try {
    if (!state.encryptionPrivatePem) {
      throw new Error(
        "Load your decryption private key in the Security keys tab, then verify this report again.",
      );
    }
    const signerKey = state.keys.find((key) => key.id === record.signing_key_id);
    if (!signerKey) throw new Error("The sender's signing public key is unavailable.");
    const ciphertext = base64ToBytes(record.ciphertext_b64);
    const decrypted = await cryptoRequest(
      "decrypt",
      {
        ciphertext,
        iv: base64ToBytes(record.iv_b64),
        wrappedKey: base64ToBytes(record.wrapped_des_key_b64),
        recipientPrivatePem: state.encryptionPrivatePem,
        signerPublicPem: signerKey.public_key_pem,
      },
      [ciphertext.buffer],
    );
    const blob = new Blob([decrypted]);
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = record.filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    showInlineMessage("document-message", "Signature verified. The report was downloaded.", true);
  } catch (error) {
    showInlineMessage("document-message", error.message);
  } finally {
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function renderKeys() {
  keyList.replaceChildren();
  if (state.keys.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-list";
    empty.textContent = "No public keys have been published for this relationship.";
    keyList.append(empty);
    return;
  }
  const latest = new Map();
  for (const key of state.keys) {
    const slot = `${key.user_id}:${key.purpose}`;
    if (!latest.has(slot) || latest.get(slot).version < key.version) latest.set(slot, key);
  }

  for (const key of [...latest.values()].sort((a, b) => a.created_at.localeCompare(b.created_at))) {
    const item = document.createElement("article");
    item.className = "key-item";
    const icon = document.createElement("span");
    icon.className = "file-icon";
    icon.textContent = "⌑";
    const info = document.createElement("div");
    info.className = "key-info";
    const title = document.createElement("div");
    title.className = "key-title";
    const owner = key.user_id === state.user.id ? "You" : counterpartFor(state.relationship).name;
    title.textContent = `${owner} · ${key.purpose} key · v${key.version}`;
    const subtitle = document.createElement("div");
    subtitle.className = "key-subtitle";
    subtitle.textContent = "Fingerprint: calculating…";
    info.append(title, subtitle);
    const copy = document.createElement("button");
    copy.type = "button";
    copy.className = "copy-button";
    copy.textContent = "Copy public key";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(key.public_key_pem);
        showInlineMessage("key-message", "Public key copied. Share fingerprints through a trusted channel.", true);
      } catch {
        showInlineMessage("key-message", "Clipboard access is unavailable in this browser.");
      }
    });
    item.append(icon, info, copy);
    keyList.append(item);
    fingerprint(key.public_key_pem)
      .then((value) => {
        subtitle.textContent = `Fingerprint: ${value}`;
      })
      .catch(() => {
        subtitle.textContent = "Fingerprint unavailable";
      });
  }
}

async function fingerprint(pem) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", pemToBytes(pem)));
  return [...digest].map((byte) => byte.toString(16).padStart(2, "0")).join(":");
}

function downloadPrivateKey(filename, pem) {
  const blob = new Blob([pem], { type: "application/x-pem-file" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.textContent = `Download ${filename}`;
  link.className = "key-download-link";
  link.addEventListener(
    "click",
    () => {
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    { once: true },
  );
  return link;
}

async function generateAndPublishKeys() {
  const button = document.querySelector("#generate-keys-button");
  hideInlineMessage("key-message");
  button.disabled = true;
  button.textContent = "Generating RSA keys…";
  try {
    const keys = await cryptoRequest("generate", {});
    state.signingPrivatePem = keys.signingPrivatePem;
    state.encryptionPrivatePem = keys.encryptionPrivatePem;

    const path = `/api/relationships/${state.relationship.id}/keys`;
    const publishedSigning = await api(path, {
      method: "POST",
      body: JSON.stringify({ purpose: "signing", public_key_pem: keys.signingPublicPem }),
    });
    try {
      await api(path, {
        method: "POST",
        body: JSON.stringify({ purpose: "encryption", public_key_pem: keys.encryptionPublicPem }),
      });
    } catch (error) {
      showInlineMessage(
        "key-message",
        `Signing key v${publishedSigning.version} was published, but the encryption key failed: ${error.message}. Your private keys were downloaded.`,
      );
      return;
    }
    state.keys = await api(path);
    renderKeys();
    const downloads = document.createElement("div");
    downloads.className = "private-key-downloads";
    downloads.append(
      downloadPrivateKey(`${state.user.username}-signing-private.pem`, keys.signingPrivatePem),
      downloadPrivateKey(`${state.user.username}-encryption-private.pem`, keys.encryptionPrivatePem),
    );
    keyList.prepend(downloads);
    showInlineMessage(
      "key-message",
      "New public keys published. Download both private-key files now. You will need them to sign and decrypt reports. Protect them and keep a secure backup.",
      true,
    );
  } catch (error) {
    showInlineMessage("key-message", error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = "<span>Generate keys</span>";
  }
}

async function uploadDocument(file) {
  hideInlineMessage("document-message");
  const button = document.querySelector("#upload-document-button");
  button.disabled = true;
  button.textContent = "Encrypting…";
  try {
    if (file.size > 14 * 1024 * 1024) {
      throw new Error("Please choose a report smaller than 14 MiB.");
    }
    if (!state.signingPrivatePem) {
      throw new Error("Load your signing private key in the Security keys tab before sending a report.");
    }
    const counterpart = counterpartFor(state.relationship);
    const recipientKey = state.keys
      .filter((key) => key.user_id === counterpart.id && key.purpose === "encryption")
      .sort((a, b) => b.version - a.version)[0];
    const signingKey = state.keys
      .filter((key) => key.user_id === state.user.id && key.purpose === "signing")
      .sort((a, b) => b.version - a.version)[0];
    if (!recipientKey || !signingKey) {
      throw new Error("Both participants need published public keys before exchanging reports.");
    }
    const documentBytes = await file.arrayBuffer();
    const encrypted = await cryptoRequest(
      "encrypt",
      {
        document: documentBytes,
        signingPrivatePem: state.signingPrivatePem,
        signingPublicPem: signingKey.public_key_pem,
        recipientPublicPem: recipientKey.public_key_pem,
      },
      [documentBytes],
    );
    await api(`/api/relationships/${state.relationship.id}/documents`, {
      method: "POST",
      body: JSON.stringify({
        filename: file.name,
        ...encrypted,
        recipient_key_id: recipientKey.id,
        signing_key_id: signingKey.id,
      }),
    });
    const documents = await api(`/api/relationships/${state.relationship.id}/documents`);
    renderDocuments(documents);
    showInlineMessage(
      "document-message",
      "Report encrypted, signed, and uploaded successfully.",
      true,
    );
  } catch (error) {
    showInlineMessage("document-message", error.message);
  } finally {
    button.disabled = false;
    button.innerHTML = "<span aria-hidden=\"true\">＋</span><span>Send a report</span>";
    documentInput.value = "";
  }
}

async function refreshHealth() {
  hideInlineMessage("health-message");
  try {
    const health = await api("/api/admin/health");
    const stats = document.querySelector("#health-stats");
    stats.replaceChildren();
    for (const [label, value] of [
      ["Service", health.status === "ok" ? "Online" : health.status],
      ["User accounts", health.users],
      ["Relationships", health.relationships],
      ["Stored documents", health.documents],
    ]) {
      const card = document.createElement("div");
      card.className = "health-stat";
      const strong = document.createElement("strong");
      strong.textContent = String(value);
      const caption = document.createElement("span");
      caption.textContent = label;
      card.append(strong, caption);
      stats.append(card);
    }
  } catch (error) {
    showInlineMessage("health-message", error.message);
  }
}

async function refreshAdminUsers() {
  hideInlineMessage("admin-users-message");
  try {
    const users = await api("/api/admin/users");
    const list = document.querySelector("#admin-user-list");
    list.replaceChildren();
    if (users.length === 0) {
      const empty = document.createElement("p");
      empty.className = "admin-users-empty";
      empty.textContent = "No student or evaluator accounts have registered yet.";
      list.append(empty);
      return;
    }

    for (const account of users) {
      const row = document.createElement("div");
      row.className = "admin-user-row";
      const identity = document.createElement("div");
      identity.className = "admin-user-identity";
      const name = document.createElement("strong");
      name.textContent =
        [account.first_name, account.last_name].filter(Boolean).join(" ") || account.username;
      const schoolId = document.createElement("span");
      schoolId.textContent = account.school_id || account.username;
      identity.append(name, schoolId);
      row.append(identity);

      const roleSelect = document.createElement("select");
      roleSelect.setAttribute("aria-label", `Role for ${name.textContent}`);
      roleSelect.innerHTML =
        '<option value="">Select role</option><option value="student">Student</option><option value="evaluator">Teacher / evaluator</option>';
      roleSelect.value = ["student", "evaluator"].includes(account.role) ? account.role : "";
      const assignButton = document.createElement("button");
      assignButton.type = "button";
      assignButton.className = "secondary-button";
      assignButton.textContent = account.role === "pending" ? "Assign role" : "Save role";
      assignButton.disabled = account.role === roleSelect.value;
      roleSelect.addEventListener("change", () => {
        assignButton.disabled = !roleSelect.value || account.role === roleSelect.value;
      });
      assignButton.addEventListener("click", async () => {
        if (!roleSelect.value) {
          showInlineMessage("admin-users-message", "Select a role before assigning it.");
          return;
        }
        assignButton.disabled = true;
        hideInlineMessage("admin-users-message");
        try {
          await api(`/api/admin/users/${account.id}/role`, {
            method: "PATCH",
            body: JSON.stringify({ role: roleSelect.value }),
          });
          await refreshAdminUsers();
        } catch (error) {
          showInlineMessage("admin-users-message", error.message);
          assignButton.disabled = false;
        }
      });
      const deleteButton = document.createElement("button");
      deleteButton.type = "button";
      deleteButton.className = "admin-delete-button";
      deleteButton.textContent = "Delete user";
      deleteButton.setAttribute("aria-label", `Delete ${name.textContent}`);
      deleteButton.addEventListener("click", async () => {
        const confirmed = window.confirm(
          `Permanently delete ${name.textContent} (${schoolId.textContent})? This also deletes all of their relationships, messages, public keys, reports, and stored encrypted report files. This cannot be undone.`,
        );
        if (!confirmed) return;
        deleteButton.disabled = true;
        hideInlineMessage("admin-users-message");
        try {
          await api(`/api/admin/users/${account.id}`, { method: "DELETE" });
          await refreshAdminDashboard();
          showInlineMessage(
            "admin-users-message",
            `${name.textContent} and associated data were permanently deleted.`,
            true,
          );
        } catch (error) {
          if (error instanceof ApiError && error.status === 500) {
            await refreshAdminDashboard();
            showInlineMessage("admin-users-message", error.message);
          } else {
            showInlineMessage("admin-users-message", error.message);
            deleteButton.disabled = false;
          }
        }
      });
      row.append(roleSelect, assignButton, deleteButton);
      list.append(row);
    }
  } catch (error) {
    showInlineMessage("admin-users-message", error.message);
  }
}

async function refreshAdminDashboard() {
  const button = document.querySelector("#refresh-admin-data");
  button.disabled = true;
  try {
    await Promise.all([refreshAdminUsers(), refreshHealth()]);
  } finally {
    button.disabled = false;
  }
}

for (const tab of document.querySelectorAll(".workspace-tab")) {
  tab.addEventListener("click", () => setActivePanel(tab.dataset.panel));
}

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.relationship) return;
  const button = document.querySelector("#send-button");
  const body = chatInput.value.trim();
  if (!body) return;
  hideInlineMessage("chat-message");
  button.disabled = true;
  try {
    await api(`/api/relationships/${state.relationship.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ body }),
    });
    chatInput.value = "";
    await refreshMessages(state.relationship.id);
  } catch (error) {
    showInlineMessage("chat-message", error.message);
  } finally {
    button.disabled = false;
    chatInput.focus();
  }
});

document.querySelector("#upload-document-button").addEventListener("click", () => {
  documentInput.click();
});
documentInput.addEventListener("change", () => {
  if (documentInput.files[0] && state.relationship) uploadDocument(documentInput.files[0]);
});

document.querySelector("#generate-keys-button").addEventListener("click", generateAndPublishKeys);
document.querySelector("#refresh-admin-data").addEventListener("click", refreshAdminDashboard);

addStudentForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const schoolIdInput = document.querySelector("#student-school-id");
  const addButton = addStudentForm.querySelector("button");
  const message = document.querySelector("#add-student-message");
  message.hidden = true;
  addButton.disabled = true;
  try {
    const relationship = await api("/api/relationships", {
      method: "POST",
      body: JSON.stringify({ school_id: schoolIdInput.value.trim() }),
    });
    state.relationships = [
      ...state.relationships.filter((item) => item.id !== relationship.id),
      relationship,
    ];
    schoolIdInput.value = "";
    renderRelationships();
    await selectRelationship(relationship.id);
  } catch (error) {
    message.textContent = error.message;
    message.hidden = false;
  } finally {
    addButton.disabled = false;
  }
});

document.querySelector("#disown-student").addEventListener("click", async (event) => {
  if (!state.relationship || state.user.role !== "evaluator") return;
  const relationship = state.relationship;
  const student = counterpartFor(relationship);
  if (
    !window.confirm(
      `End your relationship with ${student.name}? They will lose access to this conversation and its reports. History will be retained. You can add them again later using their School ID.`,
    )
  ) {
    return;
  }

  const button = event.currentTarget;
  button.disabled = true;
  hideInlineMessage("chat-message");
  try {
    await api(`/api/relationships/${relationship.id}`, { method: "DELETE" });
    state.relationships = state.relationships.filter((item) => item.id !== relationship.id);
    state.relationship = null;
    clearInterval(state.pollTimer);
    state.pollTimer = null;
    renderRelationships();
    setEmptyWorkspace(
      `${student.name} was removed from your active relationships. Past messages and encrypted reports remain stored.`,
    );
  } catch (error) {
    showInlineMessage("chat-message", error.message);
  } finally {
    button.disabled = false;
  }
});

document.querySelector("#signing-private-key").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    state.signingPrivatePem = await file.text();
    showInlineMessage("key-message", "Signing private key loaded in this tab only.", true);
  } catch {
    showInlineMessage("key-message", "Could not read the selected signing key file.");
  }
});

document.querySelector("#encryption-private-key").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    state.encryptionPrivatePem = await file.text();
    showInlineMessage("key-message", "Decryption private key loaded in this tab only.", true);
  } catch {
    showInlineMessage("key-message", "Could not read the selected decryption key file.");
  }
});

logoutButton.addEventListener("click", async () => {
  logoutMessage.hidden = true;
  logoutButton.disabled = true;
  let logoutWarning = null;
  try {
    await api("/api/auth/logout", { method: "POST" });
  } catch (error) {
    if (!(error instanceof ApiError && error.status === 401)) {
      logoutWarning =
        "You were signed out on this device, but the server could not confirm session revocation. The session will expire automatically.";
    }
  } finally {
    await stopWorkspace();
    logoutButton.disabled = false;
  }
  if (logoutWarning) {
    const message = document.querySelector("#login-message");
    message.textContent = logoutWarning;
    message.hidden = false;
  }
});

window.startWorkspace = startWorkspace;
