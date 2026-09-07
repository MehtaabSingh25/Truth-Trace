const API = "http://127.0.0.1:8002";


// ========================================
// CREATE USER
// ========================================

async function createUser() {

    const username =
        document.getElementById("username")
            .value
            .trim();

    const result =
        document.getElementById("userResult");


    if (!username) {

        result.textContent =
            "Please enter a username.";

        return;
    }


    try {

        const response =
            await fetch(
                `${API}/api/users`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        username: username
                    })
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            result.textContent =
                data.detail ||
                "Failed to create user.";

            return;
        }


        result.textContent =
            `Account created! Your User ID is ${data.id}`;


        document.getElementById(
            "username"
        ).value = "";


        document.getElementById(
            "userId"
        ).value = data.id;


    } catch (error) {

        result.textContent =
            "Cannot connect to FaceMock backend.";

        console.error(error);
    }
}


// ========================================
// CREATE POST
// ========================================

async function createPost() {

    const userId =
        document.getElementById("userId")
            .value;

    const caption =
        document.getElementById("caption")
            .value
            .trim();

    const mediaInput =
        document.getElementById("media");

    const media =
        mediaInput.files[0];

    const result =
        document.getElementById("postResult");


    if (!userId) {

        result.textContent =
            "Please enter your User ID.";

        return;
    }


    if (!caption && !media) {

        result.textContent =
            "Write something or upload media.";

        return;
    }


    const formData =
        new FormData();


    formData.append(
        "user_id",
        userId
    );

    formData.append(
        "caption",
        caption
    );


    if (media) {

        formData.append(
            "media",
            media
        );
    }


    try {

        const response =
            await fetch(
                `${API}/api/posts`,
                {
                    method: "POST",

                    body: formData
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            result.textContent =
                data.detail ||
                "Failed to create post.";

            return;
        }


        result.textContent =
            "Post published successfully!";


        document.getElementById(
            "caption"
        ).value = "";

        mediaInput.value = "";


        loadFeed();


    } catch (error) {

        result.textContent =
            "Cannot connect to FaceMock backend.";

        console.error(error);
    }
}


// ========================================
// LOAD FEED
// ========================================

async function loadFeed() {

    const feed =
        document.getElementById("feed");


    try {

        const response =
            await fetch(
                `${API}/api/posts`
            );


        if (!response.ok) {

            throw new Error(
                "Failed to load posts"
            );
        }


        const posts =
            await response.json();


        feed.innerHTML = "";


        if (posts.length === 0) {

            feed.innerHTML = `
                <p class="loading">
                    No posts yet.
                </p>
            `;

            return;
        }


        posts.forEach(post => {

            const container =
                document.createElement(
                    "article"
                );

            container.className =
                "post";


            const firstLetter =
                post.username
                    .charAt(0)
                    .toUpperCase();


            let html = `

                <div class="post-header">

                    <div class="avatar">
                        ${firstLetter}
                    </div>

                    <div>

                        <div class="username">
                            ${escapeHtml(
                                post.username
                            )}
                        </div>

                        <div class="date">
                            ${escapeHtml(
                                post.created_at
                            )}
                        </div>

                    </div>

                </div>

            `;


            if (post.caption) {

                html += `

                    <div class="caption">
                        ${escapeHtml(
                            post.caption
                        )}
                    </div>

                `;
            }


            if (post.media_url) {

                if (
                    post.media_type &&
                    post.media_type.startsWith(
                        "image"
                    )
                ) {

                    html += `

                        <img
                            src="${API}${post.media_url}"
                            alt="Post media"
                        >

                    `;

                } else if (
                    post.media_type &&
                    post.media_type.startsWith(
                        "video"
                    )
                ) {

                    html += `

                        <video controls>

                            <source
                                src="${API}${post.media_url}"
                                type="${post.media_type}"
                            >

                        </video>

                    `;
                }
            }

            html += `
                <div class="post-actions">
                    ${post.media_url ? `<a href="${API}${post.media_url}" download>Download</a>` : ""}
                    <button type="button" onclick="deletePost(${post.id})">Delete</button>
                </div>
            `;


            container.innerHTML =
                html;


            feed.appendChild(
                container
            );

        });


    } catch (error) {

        feed.innerHTML = `

            <p class="loading">
                Unable to load feed.
                Make sure FaceMock backend
                is running on port 8002.
            </p>

        `;

        console.error(error);
    }

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


// ========================================
// ESCAPE HTML
// ========================================

function escapeHtml(value) {

    const div =
        document.createElement("div");

    div.textContent =
        value ?? "";

    return div.innerHTML;
}


// ========================================
// INITIAL LOAD
// ========================================

loadFeed();