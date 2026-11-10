"use strict";

const outline = document.querySelector("#outline");
const outlineToggle = document.querySelector(".outline-toggle");
const backdrop = document.querySelector(".outline-backdrop");
const chapterLinks = [...document.querySelectorAll(".outline nav a")];
const chapters = [...document.querySelectorAll(".notebook-cell")];
const codeCells = [...document.querySelectorAll("details.code-cell")];
const expandButton = document.querySelector("#expand-code");
const statusMessage = document.querySelector("#status-message");

function setOutline(open, returnFocus = false) {
  outline.dataset.open = String(open);
  outlineToggle.setAttribute("aria-expanded", String(open));
  outlineToggle.setAttribute("aria-label", open ? "Close notebook outline" : "Open notebook outline");
  backdrop.hidden = !open;
  if (open) document.querySelector("#section-search").focus();
  if (returnFocus) outlineToggle.focus();
}
outlineToggle.addEventListener("click", () => setOutline(outline.dataset.open !== "true"));
backdrop.addEventListener("click", () => setOutline(false, true));
chapterLinks.forEach((link) => link.addEventListener("click", () => {
  if (window.innerWidth <= 900) setOutline(false);
}));
window.matchMedia("(max-width: 900px)").addEventListener("change", () => setOutline(false));

const search = document.querySelector("#section-search");
search.addEventListener("input", () => {
  const query = search.value.toLowerCase().trim();
  chapterLinks.forEach((link) => { link.hidden = !link.textContent.toLowerCase().includes(query); });
  document.querySelector("#outline-empty").hidden = chapterLinks.some((link) => !link.hidden);
});
document.addEventListener("keydown", (event) => {
  const editing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
  if (event.key === "/" && !editing && !event.metaKey && !event.ctrlKey && !event.altKey && !dialog.open) {
    event.preventDefault();
    if (window.innerWidth <= 900) setOutline(true);
    else search.focus();
  }
  if (event.key === "Escape" && outline.dataset.open === "true") setOutline(false, true);
});

let scrollQueued = false;
function updateReadingPosition() {
  let active = chapters[0];
  chapters.forEach((chapter) => {
    if (chapter.getBoundingClientRect().top <= 150) active = chapter;
  });
  chapterLinks.forEach((link) => {
    if (link.hash === `#${active.id}`) link.setAttribute("aria-current", "location");
    else link.removeAttribute("aria-current");
  });
  const distance = document.documentElement.scrollHeight - innerHeight;
  const percentage = distance > 0 ? Math.max(0, Math.min(100, Math.round(scrollY / distance * 100))) : 0;
  document.querySelector("#reading-progress").value = percentage;
  document.querySelector("#reading-percent").textContent = `${percentage}%`;
  scrollQueued = false;
}
window.addEventListener("scroll", () => {
  if (!scrollQueued) { scrollQueued = true; requestAnimationFrame(updateReadingPosition); }
}, { passive: true });
window.addEventListener("resize", updateReadingPosition);
updateReadingPosition();

function updateCodeControl() {
  const allOpen = codeCells.every((cell) => cell.open);
  expandButton.textContent = allOpen ? "Collapse code" : "Expand code";
  expandButton.setAttribute("aria-pressed", String(allOpen));
}
expandButton.addEventListener("click", () => {
  const open = !codeCells.every((cell) => cell.open);
  codeCells.forEach((cell) => { cell.open = open; });
  updateCodeControl();
});
codeCells.forEach((cell) => cell.addEventListener("toggle", updateCodeControl));
document.querySelectorAll("[data-copy]").forEach((button) => {
  button.addEventListener("click", async () => {
    const text = button.closest(".code-cell").querySelector("code").textContent;
    try {
      await navigator.clipboard.writeText(text);
      button.textContent = "Copied";
      statusMessage.textContent = "Source excerpt copied.";
    } catch {
      button.textContent = "Select code to copy";
      statusMessage.textContent = "Clipboard unavailable. Select the source excerpt to copy it.";
    }
    setTimeout(() => { button.textContent = "Copy code"; }, 1800);
  });
});
document.querySelector("#print-notebook").addEventListener("click", () => window.print());

async function loadResults() {
  const response = await fetch("assets/results.json");
  if (!response.ok) throw new Error("The recorded cohort snapshot could not be loaded.");
  const results = await response.json();
  document.querySelectorAll("[data-cohort]").forEach((button) => {
    button.addEventListener("click", () => {
      const cohort = results.cohorts[button.dataset.cohort];
      document.querySelectorAll("[data-cohort]").forEach((item) => item.setAttribute("aria-pressed", String(item === button)));
      document.querySelector("#cohort-auc").textContent = cohort.auc.toFixed(4);
      document.querySelector("#cohort-caption").textContent = `${cohort.name} / ${cohort.rows.toLocaleString("en-US")} loans`;
      document.querySelector("#cohort-brier").textContent = cohort.brier.toFixed(4);
      document.querySelector("#cohort-ap").textContent = cohort.average_precision.toFixed(4);
      const path = cohort.curve.map(([x, y], index) => `${index ? "L" : "M"}${(48 + x * 384).toFixed(2)},${(252 - y * 208).toFixed(2)}`).join(" ");
      document.querySelector("#cohort-roc").setAttribute("d", path);
      document.querySelector(".roc-chart").setAttribute("aria-label", `Selected model ROC curve for ${cohort.name}; AUC ${cohort.auc.toFixed(4)}.`);
    });
  });
}
loadResults().catch((error) => {
  statusMessage.textContent = error.message;
  document.querySelectorAll("[data-cohort]").forEach((button) => { button.disabled = true; });
});

const dialog = document.querySelector("#figure-dialog");
document.querySelectorAll("[data-figure]").forEach((button) => {
  button.addEventListener("click", () => {
    const image = document.querySelector("#dialog-image");
    image.src = button.dataset.figure;
    image.alt = button.closest("figure").querySelector("img").alt;
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
