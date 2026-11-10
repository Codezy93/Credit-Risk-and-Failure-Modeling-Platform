"use strict";

const labels = {
  fico_mid: "FICO midpoint",
  annual_inc: "Annual income",
  loan_amnt: "Loan amount",
  dti: "Debt-to-income ratio",
  purpose: "Loan purpose",
};

// Content and the default chart are rendered by the Python build, too.
// JavaScript adds cohort switching, feature bars and enlarged figures.
async function loadResults() {
  const response = await fetch("assets/results.json");
  if (!response.ok) throw new Error("The recorded result snapshot could not be loaded.");
  const results = await response.json();

  document.querySelectorAll("[data-cohort]").forEach((button) => {
    button.addEventListener("click", () => {
      const cohort = results.cohorts[button.dataset.cohort];
      document.querySelectorAll("[data-cohort]").forEach((item) => {
        item.setAttribute("aria-pressed", String(item === button));
      });
      document.querySelector("#cohort-auc").textContent = cohort.auc.toFixed(4);
      document.querySelector("#cohort-caption").textContent = `${cohort.name} / ${cohort.rows.toLocaleString("en-US")} loans`;
      document.querySelector("#cohort-brier").textContent = cohort.brier.toFixed(4);
      document.querySelector("#cohort-ap").textContent = cohort.average_precision.toFixed(4);
    });
  });

  const bars = document.querySelector("#importance-bars");
  const maximum = Math.max(...results.importance.map((row) => row.value));
  results.importance.forEach((row) => {
    const item = document.createElement("div");
    item.className = "importance-row";
    const label = document.createElement("div");
    label.className = "importance-label";
    const name = document.createElement("span");
    name.textContent = labels[row.feature] || row.feature;
    const value = document.createElement("span");
    value.textContent = row.value.toFixed(4);
    label.append(name, value);
    const track = document.createElement("div");
    track.className = "importance-track";
    track.setAttribute("aria-hidden", "true");
    const fill = document.createElement("div");
    fill.className = "importance-fill";
    fill.style.width = `${(row.value / maximum) * 100}%`;
    track.append(fill);
    item.append(label, track);
    bars.append(item);
  });
}

loadResults().catch((error) => {
  document.querySelector("#status-message").textContent = error.message;
  document.querySelectorAll("[data-cohort]").forEach((button) => {
    button.disabled = true;
  });
  document.querySelector("#importance-bars").textContent = "Feature rankings are available in the explanation report below.";
});

const dialog = document.querySelector("#figure-dialog");
document.querySelectorAll("[data-figure]").forEach((button) => {
  button.addEventListener("click", () => {
    const image = document.querySelector("#dialog-image");
    image.src = button.dataset.figure;
    image.alt = button.querySelector("img").alt;
    document.querySelector("#figure-caption").textContent = button.dataset.caption;
    dialog.showModal();
  });
});
document.querySelector(".dialog-close").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", (event) => {
  if (event.target !== dialog) return;
  const bounds = dialog.getBoundingClientRect();
  if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
});
