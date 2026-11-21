/* Datacheck Quality Monitor — sign-in card behaviour.
   External file (no inline script) so a strict script-src 'self' policy holds. */
(function () {
  "use strict";

  var form = document.getElementById("signin-form");
  if (!form) {
    return;
  }

  var email = document.getElementById("email");
  var password = document.getElementById("password");
  var submit = document.getElementById("signin-submit");
  var banner = document.getElementById("signin-banner");
  var emailError = document.getElementById("email-error");
  var passwordError = document.getElementById("password-error");
  var emailField = document.getElementById("email-field");
  var passwordField = document.getElementById("password-field");
  var toggle = document.getElementById("toggle-password");
  var demoButton = document.getElementById("demo-fill");
  var nextUrl = form.getAttribute("data-next") || "/app/";
  var EMAIL_RE = /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/;
  var pending = false;

  function setBanner(message) {
    banner.textContent = message || "";
    banner.hidden = !message;
  }

  function setFieldError(input, field, node, message) {
    node.textContent = message || "";
    if (message) {
      field.classList.add("dc-field--invalid");
      input.setAttribute("aria-invalid", "true");
    } else {
      field.classList.remove("dc-field--invalid");
      input.removeAttribute("aria-invalid");
    }
  }

  function clearErrors() {
    setFieldError(email, emailField, emailError, "");
    setFieldError(password, passwordField, passwordError, "");
  }

  function validate() {
    var messages = {};
    var value = email.value.trim();
    if (!value) {
      messages.email = "Email is required.";
    } else if (!EMAIL_RE.test(value)) {
      messages.email = "Enter a valid email address.";
    }
    if (!password.value) {
      messages.password = "Password is required.";
    }
    return messages;
  }

  function setBusy(busy) {
    pending = busy;
    submit.disabled = busy;
    submit.setAttribute("aria-busy", busy ? "true" : "false");
    submit.textContent = busy ? "Signing in…" : "Sign in";
  }

  function submitForm() {
    if (pending) {
      return;
    }
    clearErrors();
    setBanner("");
    var messages = validate();
    if (messages.email || messages.password) {
      if (messages.email) {
        setFieldError(email, emailField, emailError, messages.email);
      }
      if (messages.password) {
        setFieldError(password, passwordField, passwordError, messages.password);
      }
      (messages.email ? email : password).focus();
      return;
    }

    setBusy(true);
    fetch("/api/auth/signin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({ email: email.value.trim(), password: password.value })
    })
      .then(function (response) {
        return response.json().then(function (payload) {
          return { status: response.status, payload: payload };
        });
      })
      .then(function (result) {
        if (result.status === 200) {
          window.location.assign(nextUrl);
          return;
        }
        setBusy(false);
        var error = (result.payload && result.payload.error) || {};
        var fields = error.fields || {};
        if (result.status === 422 && (fields.email || fields.password)) {
          if (fields.email) {
            setFieldError(email, emailField, emailError, fields.email);
          }
          if (fields.password) {
            setFieldError(password, passwordField, passwordError, fields.password);
          }
          return;
        }
        setBanner(error.message || "Sign-in failed. Try again.");
      })
      .catch(function () {
        setBusy(false);
        setBanner("Could not reach the server. Check your connection and try again.");
      });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    submitForm();
  });

  email.addEventListener("blur", function () {
    var message = validate().email;
    if (message) {
      setFieldError(email, emailField, emailError, message);
    }
  });

  password.addEventListener("blur", function () {
    var message = validate().password;
    if (message) {
      setFieldError(password, passwordField, passwordError, message);
    }
  });

  email.addEventListener("input", function () {
    if (emailError.textContent) {
      setFieldError(email, emailField, emailError, validate().email || "");
    }
  });

  password.addEventListener("input", function () {
    if (passwordError.textContent) {
      setFieldError(password, passwordField, passwordError, validate().password || "");
    }
  });

  toggle.addEventListener("click", function () {
    var showing = password.type === "text";
    password.type = showing ? "password" : "text";
    toggle.setAttribute("aria-pressed", showing ? "false" : "true");
    toggle.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    toggle.textContent = showing ? "Show" : "Hide";
    password.focus();
  });

  if (demoButton) {
    demoButton.addEventListener("click", function () {
      email.value = "cenius@cenius.ai";
      password.value = "cenius";
      submitForm();
    });
  }
})();
