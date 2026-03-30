const form = document.getElementById("compare-form");
const statusBox = document.getElementById("status");
const outputBox = document.getElementById("output");

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  const inputA = document.getElementById("fileA");
  const inputB = document.getElementById("fileB");
  const fileA = inputA.files[0];
  const fileB = inputB.files[0];

  if (!fileA || !fileB) {
    statusBox.textContent = "Please choose both files first.";
    return;
  }

  const payload = new FormData();
  payload.append("fileA", fileA);
  payload.append("fileB", fileB);

  statusBox.textContent = "Uploading and comparing...";
  outputBox.textContent = "";

  try {
    const response = await fetch("/api/compare", {
      method: "POST",
      body: payload,
    });

    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.error || "Failed to compare files.");
    }

    statusBox.textContent = `Mode: ${result.comparison.mode}. Result ID: ${result.resultId}`;
    outputBox.textContent = JSON.stringify(result, null, 2);
  } catch (error) {
    statusBox.textContent = error.message || "Failed to compare files.";
  }
});
