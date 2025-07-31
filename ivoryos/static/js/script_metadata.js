function editScriptName(event) {
    event.preventDefault();  // Prevent full form submission
    const newName = document.getElementById("new-name").value;
    fetch(scriptMetaUrl, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({name: newName})
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.location.reload();  // or update the title on page directly
            } else {
                alert("Failed to rename script");
            }
        })
        .catch(error => console.error("Failed to rename script", error));
}

function lockScriptEditing() {
    fetch(scriptMetaUrl, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ status: "finalized" })
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert("Failed to update script status");
        }
    })
    .catch(error => console.error("Failed to update script status", error));
}
