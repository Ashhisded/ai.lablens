/**
 * LabLens – Progressive Enhancement JS
 *
 * This file only enhances the experience. The form works fully without JS.
 * Features:
 *  - Loading state with aria-busy on form submit
 *  - Inline validation feedback
 *  - Focus management on results page
 */

(function () {
  "use strict";

  // --- Focus results heading after navigation ---
  var resultsHeading = document.getElementById("results-heading");
  if (resultsHeading) {
    resultsHeading.focus();
  }

  // --- Error summary focus ---
  var errorSummary = document.getElementById("error-summary");
  if (errorSummary) {
    errorSummary.focus();
  }

  // --- Form submit loading state ---
  var form = document.getElementById("lab-form");
  var submitBtn = document.getElementById("submit-btn");

  if (form && submitBtn) {
    form.addEventListener("submit", function (event) {
      // Basic client-side validation: sex must be selected
      var sexChecked = form.querySelector('input[name="sex"]:checked');
      if (!sexChecked) {
        event.preventDefault();
        var msg = document.getElementById("sex-error");
        if (!msg) {
          msg = document.createElement("p");
          msg.id = "sex-error";
          msg.setAttribute("role", "alert");
          msg.setAttribute("aria-live", "polite");
          msg.style.color = "var(--color-critical)";
          msg.style.fontWeight = "600";
          msg.style.marginTop = "0.25rem";
          msg.textContent = "Please select a biological sex before submitting.";
          var radioGroup = form.querySelector(".radio-group");
          if (radioGroup) {
            radioGroup.parentNode.insertBefore(msg, radioGroup.nextSibling);
          }
        }
        msg.focus();
        return;
      }

      // Loading state
      submitBtn.disabled = true;
      submitBtn.classList.add("btn-loading");
      submitBtn.textContent = "Analysing\u2026";
      form.setAttribute("aria-busy", "true");
    });
  }
})();
