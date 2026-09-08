const API = "http://127.0.0.1:8010";
const mediaInput = document.getElementById("media");
const previewCard = document.getElementById("preview-card");
const preview = document.getElementById("preview");

function setStatus(id, message, error = false) {
    const element = document.getElementById(id);
    element.textContent = message;
    element.className = `status ${error ? "error" : "success"}`;
}

mediaInput.addEventListener("change", () => {
    const file = mediaInput.files[0];
    if (!file) return;
    previewCard.classList.remove("hidden");
    preview.innerHTML = file.type.startsWith("video/")
        ? `<video controls src="${URL.createObjectURL(file)}"></video>`
        : `<img src="${URL.createObjectURL(file)}" alt="Selected media">`;
});

document.getElementById("create-user").addEventListener("click", async () => {
    const username = document.getElementById("username").value.trim();
    if (!username) return setStatus("user-status", "Enter a username first.", true);
    const form = new FormData();
    form.append("username", username);
    try {
        const response = await fetch(`${API}/api/users`, { method: "POST", body: form });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "User creation failed.");
        setStatus("user-status", "Dummy users created on InstaMock, XMock, and FaceMock.");
    } catch (error) {
        setStatus("user-status", error.message, true);
    }
});

document.getElementById("propagate").addEventListener("click", async () => {
    const file = mediaInput.files[0];
    if (!file) return setStatus("propagation-status", "Choose an image or video first.", true);
    const form = new FormData();
    form.append("media", file);
    form.append("caption", document.getElementById("caption").value);
    setStatus("propagation-status", "Applying media transformations and propagating...");
    try {
        const response = await fetch(`${API}/api/propagate`, { method: "POST", body: form });
        const data = await response.json();
        if (!response.ok || data.status === "error") throw new Error(data.detail || "Propagation failed.");
        setStatus("propagation-status", "Propagation complete. Check the platform feeds and simulator outputs.");
    } catch (error) {
        setStatus("propagation-status", error.message, true);
    }
});
