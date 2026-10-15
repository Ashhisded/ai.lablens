/**
 * LabLens – Progressive Enhancement JavaScript
 *
 * Designed under strict Content Security Policy (no inline scripts, no eval).
 * Fully functional without JavaScript: the form still submits, validates,
 * and renders server-side results even if JS is disabled.
 */

(function () {
  "use strict";

  // --- 1. Focus Management ---
  var resultsHeading = document.getElementById("results-heading");
  if (resultsHeading) {
    resultsHeading.focus();
  }

  var errorSummary = document.getElementById("error-summary");
  if (errorSummary) {
    errorSummary.focus();
  }

  // --- 2. Print Button Enhancement ---
  var printBtn = document.getElementById("print-btn");
  if (printBtn) {
    printBtn.addEventListener("click", function () {
      window.print();
    });
  }

  // --- 3. Form Enhancements ---
  var form = document.getElementById("lab-form");
  var submitBtn = document.getElementById("submit-btn");
  var fillSampleBtn = document.getElementById("fill-sample-btn");
  var clearFormBtn = document.getElementById("clear-form-btn");

  // Sample values data (realistic panel with normal and abnormal values for judging)
  var sampleData = {
    sex: "male",
    age_band: "18_64",
    hemoglobin: "11.2",      // LOW for male (< 13.5)
    fasting_glucose: "118",   // HIGH (> 99)
    total_cholesterol: "215", // HIGH (> 200)
    platelets: "240",         // NORMAL (150 - 450)
    tsh: "2.1",               // NORMAL (0.4 - 4.0)
    vitamin_d: "18"           // LOW (< 30)
  };

  if (fillSampleBtn && form) {
    fillSampleBtn.addEventListener("click", function () {
      // Clear existing values first
      clearInputs();

      // Check sex radio
      var sexRadio = document.getElementById("sex-male");
      if (sexRadio) {
        sexRadio.checked = true;
      }

      // Set age band
      var ageSelect = document.getElementById("age_band");
      if (ageSelect) {
        ageSelect.value = sampleData.age_band;
      }

      // Populate test inputs
      Object.keys(sampleData).forEach(function (key) {
        if (key !== "sex" && key !== "age_band") {
          var input = document.getElementById(key);
          if (input) {
            input.value = sampleData[key];
            input.classList.add("input-highlight");
            setTimeout(function () {
              input.classList.remove("input-highlight");
            }, 1000);
          }
        }
      });

      // Remove client-side error if displayed
      var existingError = document.getElementById("client-validation-error");
      if (existingError) {
        existingError.remove();
      }

      // Focus first filled field
      var firstInput = document.getElementById("hemoglobin");
      if (firstInput) {
        firstInput.focus();
      }
    });
  }

  function clearInputs() {
    if (!form) return;
    var inputs = form.querySelectorAll('input[type="number"]');
    for (var i = 0; i < inputs.length; i++) {
      inputs[i].value = "";
      inputs[i].removeAttribute("aria-invalid");
    }
    var radios = form.querySelectorAll('input[type="radio"]');
    for (var j = 0; j < radios.length; j++) {
      radios[j].checked = false;
    }
    var ageSelect = document.getElementById("age_band");
    if (ageSelect) {
      ageSelect.selectedIndex = 0;
    }
    var existingError = document.getElementById("client-validation-error");
    if (existingError) {
      existingError.remove();
    }
  }

  if (clearFormBtn && form) {
    clearFormBtn.addEventListener("click", function () {
      clearInputs();
      var firstRadio = document.getElementById("sex-male");
      if (firstRadio) {
        firstRadio.focus();
      }
    });
  }

  // --- 4. Submit Validation & Loading State ---
  if (form && submitBtn) {
    form.addEventListener("submit", function (event) {
      var sexChecked = form.querySelector('input[name="sex"]:checked');
      var numberInputs = form.querySelectorAll('input[type="number"]');
      var hasAnyValue = false;

      for (var i = 0; i < numberInputs.length; i++) {
        if (numberInputs[i].value && numberInputs[i].value.trim() !== "") {
          hasAnyValue = true;
          break;
        }
      }

      // Remove existing error banner
      var existingError = document.getElementById("client-validation-error");
      if (existingError) {
        existingError.remove();
      }

      var errorMsg = "";
      if (!sexChecked) {
        errorMsg = "Please select your biological sex.";
      } else if (!hasAnyValue) {
        errorMsg = "Please enter at least one laboratory value to analyze.";
      }

      if (errorMsg) {
        event.preventDefault();
        var alertBox = document.createElement("div");
        alertBox.id = "client-validation-error";
        alertBox.className = "error-summary";
        alertBox.setAttribute("role", "alert");
        alertBox.setAttribute("aria-live", "polite");
        alertBox.tabIndex = -1;
        alertBox.innerHTML = "<h2>Validation Notice</h2><p>" + errorMsg + "</p>";

        form.parentNode.insertBefore(alertBox, form);
        alertBox.focus();
        return;
      }

      // Enter loading state
      submitBtn.disabled = true;
      submitBtn.setAttribute("aria-busy", "true");
      submitBtn.classList.add("btn-loading");

      var btnText = submitBtn.querySelector(".btn-text");
      if (btnText) {
        btnText.textContent = "Analyzing Values\u2026";
      } else {
        submitBtn.textContent = "Analyzing Values\u2026";
      }

      form.setAttribute("aria-busy", "true");
    });
  }
})();
