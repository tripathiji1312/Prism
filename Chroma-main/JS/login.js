'use strict';

class AuthForm {
  constructor() {
    this.loginForm = document.getElementById("loginForm");
    this.signupForm = document.getElementById("signupForm");
    this.activeForm = this.loginForm || this.signupForm;

    if (!this.activeForm) return;

    this.submitBtn = this.activeForm.querySelector('button[type="submit"]');
    this.successMessage = document.getElementById("successMessage");
    this.card = document.querySelector(".login-card");
    this.isSubmitting = false;

    this.init();
  }

  init() {
    this.setupUniversalPasswordToggle();
    this.setupEventListeners();
    this.setupSocialButtons();

    // FIX: Smoother Page Transitions
    this.setupNavigationTransitions();

    // Setup Floating Labels
    if (typeof FormUtils !== "undefined") {
      FormUtils.setupFloatingLabels(this.activeForm);
      FormUtils.addSharedAnimations();
    }

    // Re-trigger CSS animation on browser back/forward button
    window.addEventListener("pageshow", (event) => {
      if (event.persisted && this.card) {
        this.card.classList.remove("exiting");
        // Force CSS Animation restart
        this.card.style.animation = "none";
        this.card.offsetHeight; /* trigger reflow */
        this.card.style.animation =
          "fadeInUp 0.6s cubic-bezier(0.4, 0, 0.2, 1) forwards";
      }
    });
  }

  setupNavigationTransitions() {
    // Target specifically the login/signup swap links
    const links = document.querySelectorAll(".signup-link a, .forgot-password");

    links.forEach((link) => {
      link.addEventListener("click", (e) => {
        // If it's just a # link, ignore
        if (link.getAttribute("href") === "#") return;

        e.preventDefault();
        const targetUrl = link.href;

        // 1. Add class to animate OUT
        if (this.card) {
          this.card.classList.add("exiting");
        }

        // 2. Wait for animation to finish, then navigate
        setTimeout(() => {
          window.location.href = targetUrl;
        }, 250); // Slightly faster than CSS to prevent "hanging"
      });
    });
  }

  setupUniversalPasswordToggle() {
    this.activeForm.addEventListener("click", (e) => {
      const toggleBtn = e.target.closest(".password-toggle");
      if (toggleBtn) {
        e.preventDefault();
        const wrapper = toggleBtn.closest(".input-wrapper");
        const input = wrapper.querySelector("input");
        if (input) {
          const type =
            input.getAttribute("type") === "password" ? "text" : "password";
          input.setAttribute("type", type);
          const icon = toggleBtn.querySelector(".eye-icon");
          if (icon) icon.classList.toggle("show-password");
          input.focus();
        }
      }
    });
  }

  setupEventListeners() {
    this.activeForm.addEventListener("submit", (e) => this.handleSubmit(e));

    const inputs = this.activeForm.querySelectorAll("input");
    inputs.forEach((input) => {
      input.addEventListener("focus", (e) => {
        const wrapper = e.target.closest(".input-wrapper");
        if (wrapper) wrapper.classList.add("focused");
      });
      input.addEventListener("blur", (e) => {
        const wrapper = e.target.closest(".input-wrapper");
        if (wrapper) wrapper.classList.remove("focused");
      });
      input.addEventListener("input", (e) => this.clearError(e.target));
    });
  }

  setupSocialButtons() {
    const socialButtons = document.querySelectorAll(".social-btn");
    socialButtons.forEach((btn) => {
      btn.addEventListener("click", (e) => {
        const target = e.currentTarget;
        target.style.transform = "scale(0.95)";
        setTimeout(() => (target.style.transform = "scale(1)"), 200);
      });
    });
  }

  async handleSubmit(e) {
    e.preventDefault();
    if (this.isSubmitting) return;

    if (!this.validateForm()) {
      this.activeForm.style.animation = "shake 0.5s ease-in-out";
      setTimeout(() => (this.activeForm.style.animation = ""), 500);
      return;
    }

    this.isSubmitting = true;
    this.submitBtn.classList.add("loading");

    try {
      let url = "";
      let payload = {};

      // ---------- REGISTER ----------
      if (this.activeForm.id === "signupForm") {
        const username = document.getElementById("fullname").value;
        const password = document.getElementById("password").value;

        url = "http://localhost:8080/api/auth/register";
        payload = { username, password };
      }

      // ---------- LOGIN ----------
      if (this.activeForm.id === "loginForm") {
        const username = document.getElementById("username").value;
        const password = document.getElementById("password").value;

        url = "http://localhost:8080/api/auth/login";
        payload = { username, password };
      }

      const res = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      // ---------- HANDLE ERRORS ----------
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || "Request failed");
      }

      // ---------- SUCCESS ----------
      if (this.activeForm.id === "loginForm") {
        const data = await res.json();

        // 1. Save the Token (You already had this)
        localStorage.setItem("token", data.token);

        // 2. NEW: Save the Wallet Address
        // NOTE: Ensure your backend sends this key ("walletAddress" or "username")
        if (data.walletAddress) {
          localStorage.setItem("walletAddress", data.walletAddress);
        } else {
          // Fallback: Use username if wallet is not separate
          localStorage.setItem("walletAddress", data.username);
        }
      }

      this.showSuccess(); // Proceed to redirect
    } catch (err) {
      alert("❌ " + err.message);
      console.error(err);
    } finally {
      this.isSubmitting = false;
      this.submitBtn.classList.remove("loading");
    }
  }

  validateForm() {
    let isValid = true;

    const inputs = this.activeForm.querySelectorAll("input[required]");
    inputs.forEach((input) => {
      if (!input.value.trim()) {
        this.showError(input, "This field is required");
        isValid = false;
      }
    });

    const email = this.activeForm.querySelector('input[type="email"]');
    if (email && email.value) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email.value.trim())) {
        this.showError(email, "Please enter a valid email");
        isValid = false;
      }
    }

    if (this.activeForm.id === "signupForm") {
      const pass = document.getElementById("password");
      const confirm = document.getElementById("confirm-password");
      if (pass && confirm && pass.value !== confirm.value) {
        this.showError(confirm, "Passwords do not match");
        isValid = false;
      }
    }

    return isValid;
  }

  showError(input, message) {
    const wrapper = input.closest(".form-group");
    const errorSpan = wrapper.querySelector(".error-message");
    if (errorSpan) {
      errorSpan.textContent = message;
      errorSpan.classList.add("show");
      wrapper.classList.add("error");
    }
  }

  clearError(input) {
    const wrapper = input.closest(".form-group");
    const errorSpan = wrapper.querySelector(".error-message");
    if (errorSpan) {
      errorSpan.classList.remove("show");
      wrapper.classList.remove("error");
    }
  }

  showSuccess() {
    // 1. Hide the form elements to clear the view
    this.activeForm.style.display = "none";
    const elementsToHide = document.querySelectorAll(
      ".divider, .social-login, .signup-link"
    );
    elementsToHide.forEach((el) => (el.style.display = "none"));

    // 2. Set the success message based on the action
    if (this.activeForm.id === "signupForm") {
      this.successMessage.textContent =
        "Registration Successful! Redirecting to Login...";
    } else {
      this.successMessage.textContent = "Login Successful! Redirecting...";
    }

    // 3. Show the message
    this.successMessage.classList.add("show");

    // 4. Wait 2 seconds, then redirect to the correct page
    setTimeout(() => {
      this.activeForm.reset();

      if (this.activeForm.id === "signupForm") {
        // --- Redirect after REGISTER ---
        window.location.href = "loginpage.html";
      } else {
        // --- Redirect after LOGIN ---
        window.location.href = "postLoginMain.html";
      }
    }, 2000);
  }
}

document.addEventListener('DOMContentLoaded', () => {
    new AuthForm();
});