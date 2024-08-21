function addOverlayToButtons(buttonIds) {
    buttonIds.forEach(function(buttonId) {
        document.getElementById(buttonId).addEventListener('submit', function() {
            // Display the overlay
            document.getElementById('overlay').style.display = 'block';
            document.getElementById('overlay-text').innerText = `Processing ${buttonId}...`;
        });
    });
}

// buttonIds should be set dynamically in your HTML template
addOverlayToButtons(buttonIds);
