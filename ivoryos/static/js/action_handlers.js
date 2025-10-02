



function saveWorkflow(link) {
    const url = link.dataset.postUrl;

    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // flash a success message
            // flash("Workflow saved successfully", "success");
            window.location.reload();  // or update the UI dynamically
        } else {
            alert("Failed to save workflow: " + data.error);
        }
    })
    .catch(err => {
        console.error("Save error:", err);
        alert("Something went wrong.");
    });
}


function updateInstrumentPanel(link) {
    const url = link.dataset.getUrl;
    fetch(url)
    .then(res => res.json())
    .then(data => {
        if (data.html) {
            document.getElementById("sidebar-wrapper").innerHTML = data.html;
            initializeDragHandlers()
        }
    })
}

function addMethodToDesign(event, form) {
    event.preventDefault(); // Prevent default form submission

    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateActionCanvas(data.html);
            hideModal();
        } else {
            alert("Failed to add method: " + data.error);
        }
    })
    .catch(error => console.error('Error:', error));
}


function updateActionCanvas(html) {
    document.getElementById("canvas-action-wrapper").innerHTML = html;
    initializeCanvas(); // Reinitialize canvas functionality
    document.querySelectorAll('#pythonCodeOverlay pre code').forEach((block) => {
        hljs.highlightElement(block);
    });
}


let lastFocusedElement = null;


function hideModal() {
    if (document.activeElement) {
        document.activeElement.blur();
    }
    $('#dropModal').modal('hide');
    if (lastFocusedElement) {
        lastFocusedElement.focus();  // Return focus to the triggering element
    }
}

function submitEditForm(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch(form.action, {
        method: 'POST',
        body: formData
    })
    .then(response => response.text())
    .then(html => {
        if (html) {
            // Update only the action list
            updateActionCanvas(html);

            if (previousHtmlState) {
                document.getElementById('instrument-panel').innerHTML = previousHtmlState;
                previousHtmlState = null;  // Clear the stored state
            }
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const warningDiv = doc.querySelector('#warning');
            if (warningDiv && warningDiv.textContent.trim()) {
                alert(warningDiv.textContent.trim()); // or use a nicer toast
            }
        }
    })
    .catch(error => {
        console.error('Error:', error);
    });
}

function clearDraft() {
    fetch(scriptDeleteUrl, {
        method: "DELETE",
        headers: {
            "Content-Type": "application/json",
        },
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            window.location.reload();
        } else {
            alert("Failed to clear draft");
        }
    })
    .catch(error => console.error("Failed to clear draft", error));
}




let previousHtmlState = null;  // Store the previous state

function duplicateAction(uuid) {
    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    fetch(scriptStepDupUrl.replace('0', uuid), {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })

    .then(response => response.text())
    .then(html => {
        updateActionCanvas(html);

        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const warningDiv = doc.querySelector('#warning');
        if (warningDiv && warningDiv.textContent.trim()) {
            alert(warningDiv.textContent.trim()); // or use a nicer toast
        }
    })
    .catch(error => console.error('Error:', error));
}

function editAction(uuid) {
    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    // Save current state before fetching new content
    previousHtmlState = document.getElementById('instrument-panel').innerHTML;

    fetch(scriptStepUrl.replace('0', uuid), {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.text())
    .then(html => {
        document.getElementById('instrument-panel').innerHTML = html;

        // Add click handler for back button
        document.getElementById('back').addEventListener('click', function(e) {
            e.preventDefault();
            if (previousHtmlState) {
                document.getElementById('instrument-panel').innerHTML = previousHtmlState;
                previousHtmlState = null;  // Clear the stored state
            }
        });
    })
    .catch(error => console.error('Error:', error));
}



function deleteAction(uuid) {
    if (!uuid) {
        console.error('Invalid UUID');
        return;
    }

    fetch(scriptStepUrl.replace('0', uuid), {
        method: 'DELETE',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(response => response.text())
    .then(html => {
        // Find the first list element's content and replace it
        updateActionCanvas(html);
        // Optionally, check if a warning element exists
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const warningDiv = doc.querySelector('#warning');
        if (warningDiv && warningDiv.textContent.trim()) {
            alert(warningDiv.textContent.trim()); // or use a nicer toast
        }
    })
    .catch(error => console.error('Error:', error));
}






