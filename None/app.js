const promptText = "??????????????? Web ??";
const actionBtn = document.getElementById("action");
const output = document.getElementById("output");

actionBtn.addEventListener("click", () => {
  output.textContent = [
    "Prompt:",
    promptText,
    "",
    "Status:",
    "Fallback template generated successfully."
  ].join("\n");
});
