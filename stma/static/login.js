const form = document.querySelector("#login-form");
const loginView = document.querySelector("#login-view");
const signupView = document.querySelector("#signup-view");
const signupForm = document.querySelector("#signup-form");
const loginMessage = document.querySelector("#login-message");
const signupMessage = document.querySelector("#signup-message");

let accessToken = null;

function showMessage(element, message) {
  element.classList.remove("message-success");
  element.textContent = message;
  element.hidden = false;
}

function showLogin() {
  signupView.hidden = true;
  loginView.hidden = false;
  form.reset();
  document.querySelector("#username").focus();
}

function showSignup() {
  loginView.hidden = true;
  signupView.hidden = false;
  signupForm.reset();
  document.querySelector("#first-name").focus();
}

async function signIn(username, password) {
  const response = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => null);
    const message = typeof error?.detail === "string" ? error.detail : "Unable to sign in.";
    const failure = new Error(message);
    failure.status = response.status;
    throw failure;
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
  await window.startWorkspace(accessToken, await accountResponse.json());
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginMessage.hidden = true;
  const submitButton = document.querySelector("#submit-button");
  submitButton.disabled = true;

  const formData = new FormData(form);
  try {
    await signIn(formData.get("username"), formData.get("password"));
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

signupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  signupMessage.hidden = true;
  const submitButton = document.querySelector("#signup-button");
  submitButton.disabled = true;
  const formData = new FormData(signupForm);
  const username = formData.get("school_id");

  try {
    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        first_name: formData.get("first_name"),
        last_name: formData.get("last_name"),
        school_id: username,
        password: formData.get("password"),
      }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => null);
      throw new Error(typeof error?.detail === "string" ? error.detail : "Could not create account.");
    }

    showMessage(
      signupMessage,
      "Account created. A Sysadmin must assign your role before you can sign in.",
    );
    signupMessage.classList.add("message-success");
    signupForm.reset();
  } catch (error) {
    showMessage(
      signupMessage,
      error instanceof TypeError
        ? "Could not reach STMA. Check your connection and try again."
        : error.message,
    );
  } finally {
    submitButton.disabled = false;
  }
});

document.querySelector("#show-signup").addEventListener("click", showSignup);
document.querySelector("#show-login").addEventListener("click", showLogin);
