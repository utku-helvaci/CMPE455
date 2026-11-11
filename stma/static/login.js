const form = document.querySelector("#login-form");
const loginView = document.querySelector("#login-view");
const signedInView = document.querySelector("#signed-in-view");
const submitButton = document.querySelector("#submit-button");
const loginMessage = document.querySelector("#login-message");
const logoutButton = document.querySelector("#logout-button");
const logoutMessage = document.querySelector("#logout-message");

let accessToken = null;

function showMessage(element, message) {
  element.textContent = message;
  element.hidden = false;
}

function showLogin() {
  accessToken = null;
  signedInView.hidden = true;
  loginView.hidden = false;
  form.reset();
  document.querySelector("#username").focus();
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginMessage.hidden = true;
  submitButton.disabled = true;

  const formData = new FormData(form);
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: formData.get("username"),
        password: formData.get("password"),
      }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => null);
      const detail = typeof error?.detail === "string" ? error.detail : "Unable to sign in.";
      throw new Error(detail);
    }

    const result = await response.json();
    accessToken = result.access_token;
    const accountResponse = await fetch("/api/me", {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!accountResponse.ok) {
      accessToken = null;
      throw new Error("Signed in, but account details could not be loaded. Please try again.");
    }

    const account = await accountResponse.json();
    document.querySelector("#signed-in-title").textContent = `Welcome, ${account.username}`;
    document.querySelector("#account-summary").textContent =
      `You are signed in as ${account.role}.`;
    loginView.hidden = true;
    signedInView.hidden = false;
    logoutButton.focus();
  } catch (error) {
    showMessage(
      loginMessage,
      error instanceof TypeError
        ? "Could not reach STMA. Check your connection and try again."
        : error.message,
    );
  } finally {
    submitButton.disabled = false;
  }
});

logoutButton.addEventListener("click", async () => {
  logoutMessage.hidden = true;
  logoutButton.disabled = true;
  try {
    const response = await fetch("/api/auth/logout", {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!response.ok) {
      throw new Error("Could not end the server session. It will expire automatically.");
    }
    showLogin();
  } catch (error) {
    showMessage(logoutMessage, error.message);
  } finally {
    logoutButton.disabled = false;
  }
});
