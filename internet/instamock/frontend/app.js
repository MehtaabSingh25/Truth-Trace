const API = "http://127.0.0.1:8000";


// --------------------------------------------------
// Create user
// --------------------------------------------------

async function createUser() {

    const username =
        document.getElementById("username").value;

    if (!username) {
        alert("Enter username");
        return;
    }

    const response = await fetch(
        `${API}/api/users`,
        {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                username: username
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail);
        return;
    }

    alert(
        `User created. ID: ${data.id}`
    );

    document.getElementById("username").value = "";
}


// --------------------------------------------------
// Create post
// --------------------------------------------------

async function createPost() {

    const userId =
        document.getElementById("userId").value;

    const caption =
        document.getElementById("caption").value;

    const media =
        document.getElementById("media").files[0];

    if (!userId || !media) {
        alert("User ID and media are required");
        return;
    }

    const formData = new FormData();

    formData.append("user_id", userId);
    formData.append("caption", caption);
    formData.append("media", media);

    const response = await fetch(
        `${API}/api/posts`,
        {
            method: "POST",
            body: formData
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail);
        return;
    }

    alert("Post uploaded");

    document.getElementById("caption").value = "";
    document.getElementById("media").value = "";

    loadFeed();
}


// --------------------------------------------------
// Load feed
// --------------------------------------------------

async function loadFeed() {

    const response = await fetch(
        `${API}/api/posts`
    );

    const posts = await response.json();

    const feed =
        document.getElementById("feed");

    feed.innerHTML = "";

    posts.forEach(post => {

        const container =
            document.createElement("div");

        container.className = "post";

        let mediaElement = "";

        if (post.media_type.startsWith("image")) {

            mediaElement = `
                <img
                    src="${API}${post.media_url}"
                    alt="Post media"
                >
            `;

        } else if (post.media_type.startsWith("video")) {

            mediaElement = `
                <video controls>
                    <source
                        src="${API}${post.media_url}"
                        type="${post.media_type}"
                    >
                </video>
            `;
        }

        container.innerHTML = `
            <h3>@${post.username}</h3>

            ${mediaElement}

            <p>${post.caption}</p>

            <small>
                ${post.created_at}
            </small>
            <div class="post-actions">
                ${post.media_url ? `<a href="${API}${post.media_url}" download>Download</a>` : ""}
                <button type="button" onclick="deletePost(${post.id})">Delete</button>
            </div>
        `;

        feed.appendChild(container);
    });
}

async function deletePost(postId) {
    if (!confirm("Delete this post and its media?")) return;
    const response = await fetch(`${API}/api/posts/${postId}`, { method: "DELETE" });
    const data = await response.json();
    if (!response.ok) {
        alert(data.detail || "Failed to delete post.");
        return;
    }
    loadFeed();
}


// --------------------------------------------------
// Initial load
// --------------------------------------------------

loadFeed();