// Move triggerModal to global scope
function triggerModal(formHtml, actionName, actionId, dropTargetId) {
    if (formHtml && formHtml.trim() !== "") {
        var $form = $("<div>").html(formHtml);

        var $hiddenInput = $("<input>")
            .attr("type", "hidden")
            .attr("name", "drop_target_id")
            .attr("id", "dropTargetInput")
            .val(dropTargetId);

        $form.find("button[type='submit']").before($hiddenInput);

        $("#modalFormFields").empty().append($form.children());

        const $modal = $("#dropModal");

        setTimeout(() => {
            showModal($modal);
        }, 0);

        $("#modalDropTarget").text(dropTargetId || "N/A");
        $("#modalFormFields")
            .data("action-id", actionId)
            .data("action-name", actionName)
            .data("drop-target-id", dropTargetId);
    } else {
        console.error("Form HTML is undefined or empty!");
    }
}

function showModal($modal) {
    $modal.modal({
        backdrop: 'static',
        keyboard: true,
        focus: true
    }).modal('show');
}

const state = {
    dropTargetId: ""
};

function initializeCanvas() {
    $("#list ul").sortable({
        cancel: ".unsortable",
        opacity: 0.8,
        cursor: "move",
        placeholder: "drop-placeholder",
        update: function () {
            const item_order = $("ul.reorder li").map(function () {
                return this.id;
            }).get();
            var order_string = "order=" + item_order.join(",");

            $.ajax({
                method: "POST",
                url: updateListUrl,
                data: order_string,
                cache: false,
                success: function (data) {
                    // Update the canvas content with the new HTML
                    updateActionCanvas(data)
                }
            }).fail(function (jqXHR, textStatus, errorThrown) {
                console.error("Failed to update order:", textStatus, errorThrown);
            });
        }
    });

    // Make Entire Accordion Item Draggable
    $(".accordion-item").off("dragstart").on("dragstart", function (event) {
        let formHtml = $(this).find(".accordion-body").html();
        event.originalEvent.dataTransfer.setData("form", formHtml || "");
        event.originalEvent.dataTransfer.setData("action", $(this).find(".draggable-action").data("action"));
        event.originalEvent.dataTransfer.setData("id", $(this).find(".draggable-action").attr("id"));
        $(this).addClass("dragging");
    });

    $("#list ul, .canvas").off("dragover").on("dragover", function (event) {
        event.preventDefault();
        let $target = $(event.target).closest("li");

        if ($target.length) {
            state.dropTargetId = $target.attr("id") || "";
            insertDropPlaceholder($target);
        } else if (!$("#list ul").children().length && $(this).hasClass("canvas")) {
            $(".drop-placeholder").remove();
        } else {
            state.dropTargetId = "";
        }
    });

    $("#list ul, .canvas").off("dragleave").on("dragleave", function () {
        $(".drop-placeholder").remove();
    });

    $("#list ul, .canvas").off("drop").on("drop", function (event) {
        event.preventDefault();
        var actionName = event.originalEvent.dataTransfer.getData("action");
        var actionId = event.originalEvent.dataTransfer.getData("id");
        var formHtml = event.originalEvent.dataTransfer.getData("form");
        let listLength = $("ul.reorder li").length;
        state.dropTargetId = state.dropTargetId || listLength + 1;
        $(".drop-placeholder").remove();
        document.activeElement?.blur();
        triggerModal(formHtml, actionName, actionId, state.dropTargetId);
    });
    getCodePreview();
}

function insertDropPlaceholder($target) {
    $(".drop-placeholder").remove();
    $("<li class='drop-placeholder'></li>").insertBefore($target);
}

// Add this function to sortable_design.js
function initializeDragHandlers() {
    const $cards = $(".accordion-item.design-control");

    // Toggle draggable based on mouse/touch position
    $cards.off("mousedown touchstart").on("mousedown touchstart", function (event) {
        this.setAttribute("draggable", $(event.target).closest(".input-group").length ? "false" : "true");
    });

    // Handle the actual drag
    $cards.off("dragstart dragend").on({
        dragstart: function (event) {
            if (this.getAttribute("draggable") !== "true") {
                event.preventDefault();
                return false;
            }

            const formHtml = $(this).find(".accordion-body form").prop("outerHTML");
            if (!formHtml) return false;

            event.originalEvent.dataTransfer.setData("form", formHtml);
            event.originalEvent.dataTransfer.setData("action", $(this).find(".draggable-action").data("action"));
            event.originalEvent.dataTransfer.setData("id", $(this).find(".draggable-action").attr("id"));

            $(this).addClass("dragging");
        },
        dragend: function () {
            $(this).removeClass("dragging").attr("draggable", "false");
        }
    });

    // Prevent form inputs from being draggable
    $(".accordion-item input, .accordion-item select").attr("draggable", "false");
}

// Make sure it's called in the document ready function
$(document).ready(function () {
    initializeCanvas();
    initializeDragHandlers(); // Add this line
});