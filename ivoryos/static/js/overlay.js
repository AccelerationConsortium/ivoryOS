function addOverlayToButtons(buttonIds) {
    buttonIds.forEach(function(buttonId) {
        // Use querySelector to ensure we get the actual form, not a div with the same ID
        var form = document.querySelector('form[name="' + buttonId + '"]');
        
        if (form) {
            form.addEventListener('submit', async function(event) {
                if (form.dataset.overrideConfirmed === "true") {
                    return; // Already processed
                }

                event.preventDefault();
                
                function showOverlayAndSubmit() {
                    var overlay = document.getElementById('overlay');
                    if (overlay) {
                        overlay.style.display = 'block';
                        var textEl = document.getElementById('overlay-text');
                        if (textEl) textEl.innerText = `Processing ${buttonId}...`;
                    }
                    form.dataset.overrideConfirmed = "true";
                    HTMLFormElement.prototype.submit.call(form);
                }
                
                try {
                    // Check if system is busy
                    const response = await fetch(typeof STATUS_URL !== 'undefined' ? STATUS_URL : "/executions/status");
                    const data = await response.json();
                    
                    if (data.busy) {
                        if (typeof bootstrap !== 'undefined') {
                            try {
                                let modalEl = document.getElementById('manualOverrideModal');
                                if (!modalEl) {
                                    const modalHtml = `
                                        <div class="modal fade" id="manualOverrideModal" tabindex="-1" aria-labelledby="manualOverrideModalLabel" aria-hidden="true">
                                          <div class="modal-dialog">
                                            <div class="modal-content">
                                              <div class="modal-header">
                                                <h5 class="modal-title text-warning" id="manualOverrideModalLabel"><i class="bi bi-exclamation-triangle-fill me-2"></i>System Busy</h5>
                                                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                                              </div>
                                              <div class="modal-body">
                                                <p>The system is currently busy (a workflow might be running or paused).</p>
                                                <p><strong>Are you sure you want to override and execute this action manually?</strong></p>
                                              </div>
                                              <div class="modal-footer">
                                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                                <button type="button" class="btn btn-warning" id="manualOverrideConfirmBtn">Proceed with Override</button>
                                              </div>
                                            </div>
                                          </div>
                                        </div>
                                    `;
                                    document.body.insertAdjacentHTML('beforeend', modalHtml);
                                    modalEl = document.getElementById('manualOverrideModal');
                                }
                                
                                const confirmBtn = document.getElementById('manualOverrideConfirmBtn');
                                const newConfirmBtn = confirmBtn.cloneNode(true);
                                confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
                                
                                const modal = new bootstrap.Modal(modalEl);
                                
                                newConfirmBtn.addEventListener('click', function() {
                                    modal.hide();
                                    let overrideInput = document.createElement("input");
                                    overrideInput.type = "hidden";
                                    overrideInput.name = "override_busy";
                                    overrideInput.value = "true";
                                    form.appendChild(overrideInput);
                                    showOverlayAndSubmit();
                                });
                                
                                modal.show();
                            } catch (err) {
                                console.error("Error showing modal:", err);
                                if (confirm("System is currently busy (a workflow might be running or paused). Are you sure you want to override and execute this action manually?")) {
                                    let overrideInput = document.createElement("input");
                                    overrideInput.type = "hidden";
                                    overrideInput.name = "override_busy";
                                    overrideInput.value = "true";
                                    form.appendChild(overrideInput);
                                    showOverlayAndSubmit();
                                }
                            }
                        } else {
                            if (confirm("System is currently busy (a workflow might be running or paused). Are you sure you want to override and execute this action manually?")) {
                                let overrideInput = document.createElement("input");
                                overrideInput.type = "hidden";
                                overrideInput.name = "override_busy";
                                overrideInput.value = "true";
                                form.appendChild(overrideInput);
                                
                                showOverlayAndSubmit();
                            }
                        }
                    } else {
                        showOverlayAndSubmit();
                    }
                } catch (e) {
                    console.error("Error during status check:", e);
                    // Fallback to normal submission on error
                    showOverlayAndSubmit();
                }
            });
        }
    });
}

// buttonIds should be set dynamically in your HTML template
if (typeof buttonIds !== 'undefined') {
    addOverlayToButtons(buttonIds);
}
