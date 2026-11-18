// forms.js -- small behaviours shared by every server-rendered form
// (log in, sign up, profile, password reset, log out).

(function () {
  "use strict";

  // 1. Feedback while a form is being sent: the button says what is happening and
  //    is disabled, so the user can see something is going on and can't double-submit.
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || form.hasAttribute("data-no-lock")) return;

    var button = form.querySelector('button[type="submit"]');
    if (!button || button.disabled) return;

    var label = button.getAttribute("data-loading") || form.getAttribute("data-loading") || "Please wait…";
    button.setAttribute("data-original-label", button.textContent);
    button.textContent = label;
    // Disable on the next tick: disabling inside the submit event itself can cancel the submission.
    setTimeout(function () { button.disabled = true; }, 0);
  });

  // The Back button can restore a page whose button is still stuck on "Please wait…".
  window.addEventListener("pageshow", function () {
    document.querySelectorAll("button[data-original-label]").forEach(function (button) {
      button.textContent = button.getAttribute("data-original-label");
      button.removeAttribute("data-original-label");
      button.disabled = false;
    });
  });

  // 2. "Show password" checkbox: reveals or hides every password box in that form.
  document.addEventListener("change", function (event) {
    var box = event.target;
    if (!box.matches || !box.matches("[data-show-password]")) return;
    var form = box.closest("form");
    form.querySelectorAll("input[data-password], input[type='password']").forEach(function (input) {
      input.setAttribute("data-password", "");
      input.type = box.checked ? "text" : "password";
    });
  });

  // 3. After a failed submit, put the cursor in the first field that has a problem.
  var firstInvalid = document.querySelector('[aria-invalid="true"]');
  if (firstInvalid) firstInvalid.focus();
})();
