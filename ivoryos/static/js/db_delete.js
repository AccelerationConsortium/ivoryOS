
function deleteWorkflow(link) {
    const url = link.dataset.deleteUrl;

    fetch(url, {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();  // or remove the row dynamically
        } else {
            alert("Failed to delete workflow: " + data.error);
        }
    })
    .catch(err => {
        console.error("Delete error:", err);
        alert("Something went wrong.");
    });
}
