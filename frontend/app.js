document.getElementById("uploadForm").addEventListener("submit", async (e) => {
  e.preventDefault();

  const fileInput = document.getElementById("taskFile");
  const file = fileInput.files[0];
  if (!file) return alert("Please select a .txt file!");

  const formData = new FormData();
  formData.append("task", file);

  const resultElement = document.getElementById("result");
  const plotImage = document.getElementById("plot");

  resultElement.textContent = "Analyzing...";
  plotImage.style.display = "none";
  plotImage.src = "";

  try {
    const response = await fetch("/api/", {
      method: "POST",
      body: formData,
    });

    const result = await response.json();
    const text = result.response;

    // Check if it's a base64 image or plain text
    if (text.startsWith("data:image/")) {
      plotImage.src = text;
      plotImage.style.display = "block";
      resultElement.textContent = "Image output:";
    } else {
      resultElement.textContent = text;
    }
  } catch (err) {
    resultElement.textContent = "❌ Error: " + err.message;
  }
});
