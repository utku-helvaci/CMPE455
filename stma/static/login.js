const form = document.querySelector("#login-form");
const loginView = document.querySelector("#login-view");
const submitButton = document.querySelector("#submit-button");
const loginMessage = document.querySelector("#login-message");

let accessToken = null;

function showMessage(element, message) {
  element.textContent = message;
  element.hidden = false;
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
    await window.startWorkspace(accessToken, account);
    loginView.hidden = true;
  } catch (error) {
    if (accessToken && window.stopWorkspace) await window.stopWorkspace();
    accessToken = null;
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
