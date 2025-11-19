// Toggle visibility of line numbers
function toggleLineNumbers(save = true) {
    const show = document.getElementById('toggleLineNumbers').checked;
    document.querySelectorAll('.line-number').forEach(el => {
        el.classList.toggle('d-none', !show);
    });

    if (save) {
        localStorage.setItem('showLineNumbers', show ? 'true' : 'false');
    }
}

// Toggle visibility of Python code overlay
function toggleCodeOverlay(state = null) {
    const overlay = document.getElementById("pythonCodeOverlay");
    const checkbox = document.getElementById("showPythonCodeSwitch");

    const isVisible = overlay.classList.contains("show");
    const newState = state !== null ? state : !isVisible;

    if (newState) {
        overlay.classList.add("show");
        checkbox.checked = true;
    } else {
        overlay.classList.remove("show");
        checkbox.checked = false;
    }

    // Save state to session via PATCH
    fetch(scriptUIStateUrl, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ show_code: newState })
    });
}


function setScriptPhase(stype) {
    // console.log("Setting editing type to", stype);
    fetch(scriptUIStateUrl, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ editing_type: stype })
    })
    .then(res => res.json())
    .then(data => {
        if (data.html) {
            document.getElementById("canvas-wrapper").innerHTML = data.html;
            initializeCanvas(); // Reinitialize the canvas functionality
        }
    })
    .catch(error => console.error("Failed to update editing type", error));
}



function changeDeck(deck) {
    fetch(scriptUIStateUrl, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ deck_name: deck })
    })
    .then(res => res.json())
    .then(data => {
        if (data.html) {
            document.getElementById("sidebar-wrapper").innerHTML = data.html;
        }
    })
    .catch(error => console.error("Failed to change deck", error));
}



function toggleAutoFill() {
    const instrumentValue = document.querySelector('.form-check.form-switch').dataset.instrument;

    fetch(scriptUIStateUrl, {
        method: "PATCH",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            autofill: document.getElementById("autoFillCheck").checked,
            instrument: instrumentValue
        })
    })
    .then(res => res.json())
    .then(data => {
        if (data.html) {
            document.getElementById("instrument-panel").innerHTML = data.html;
            initializeDragHandlers()
        }
    })
}
// Restore state on page load
document.addEventListener('DOMContentLoaded', () => {
    const savedState = localStorage.getItem('showLineNumbers');
    const checkbox = document.getElementById('toggleLineNumbers');

    if (savedState === 'true') {
        checkbox.checked = true;
    }
    if (checkbox) {
        toggleLineNumbers(false);  // don't overwrite localStorage on load
        checkbox.addEventListener('change', () => toggleLineNumbers());
    }

});