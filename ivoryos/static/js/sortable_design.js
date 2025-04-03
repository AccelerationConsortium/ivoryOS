$(document).ready(function () {
    let dropTargetId = ""; // Store the ID of the drop target

    $("#list ul").sortable({
        cancel: ".unsortable",
        opacity: 0.8,
        cursor: "move",
        placeholder: "drop-placeholder",
        update: function () {
            var item_order = [];
            $("ul.reorder li").each(function () {
                item_order.push($(this).attr("id"));
            });
            var order_string = "order=" + item_order.join(",");

            $.ajax({
                method: "POST",
                url: updateListUrl,
                data: order_string,
                cache: false,
                success: function (data) {
                    $("#response").html(data);
                    $("#response").slideDown("slow");
                    slideout();
                }
            });
        }
    });

    // Make Entire Accordion Item Draggable
    $(".accordion-item").on("dragstart", function (event) {
        let formHtml = $(this).find(".accordion-body").html(); // Get the correct form
        event.originalEvent.dataTransfer.setData("form", formHtml || ""); // Store form HTML
        event.originalEvent.dataTransfer.setData("action", $(this).find(".draggable-action").data("action"));
        event.originalEvent.dataTransfer.setData("id", $(this).find(".draggable-action").attr("id"));

        $(this).addClass("dragging");
    });


    $("#list ul, .canvas").on("dragover", function (event) {
        event.preventDefault();
        let $target = $(event.target).closest("li");

        // If we're over a valid <li> element in the list
        if ($target.length) {
            dropTargetId = $target.attr("id") || ""; // Store the drop target ID

            $(".drop-placeholder").remove(); // Remove existing placeholders
            $("<li class='drop-placeholder'></li>").insertBefore($target); // Insert before the target element
        } else if (!$("#list ul").children().length && $(this).hasClass("canvas")) {
            $(".drop-placeholder").remove();  // Remove any placeholder
            // $("#list ul").append("<li class='drop-placeholder'></li>"); // Append placeholder to canvas
        } else {
            dropTargetId = "";  // Append placeholder to canvas
        }
    });

    $("#list ul, .canvas").on("dragleave", function () {
        $(".drop-placeholder").remove(); // Remove placeholder on leave
    });

    $("#list ul, .canvas").on("drop", function (event) {
        event.preventDefault();

        var actionName = event.originalEvent.dataTransfer.getData("action");
        var actionId = event.originalEvent.dataTransfer.getData("id");
        var formHtml = event.originalEvent.dataTransfer.getData("form"); // Retrieve form HTML
        let listLength = $("ul.reorder li").length;
        dropTargetId = dropTargetId || listLength + 1;  // Assign a "last" ID or unique identifier
        $(".drop-placeholder").remove();
            // Trigger the modal with the appropriate action
        triggerModal(formHtml, actionName, actionId, dropTargetId);

    });

    // Function to trigger the modal (same for both buttons and accordion items)
    function triggerModal(formHtml, actionName, actionId, dropTargetId) {
        if (formHtml && formHtml.trim() !== "") {
            var $form = $("<div>").html(formHtml); // Convert HTML string to jQuery object

            // Create a hidden input for the drop target ID
            var $hiddenInput = $("<input>")
                .attr("type", "hidden")
                .attr("name", "drop_target_id")
                .attr("id", "dropTargetInput")
                .val(dropTargetId);

            // Insert before the submit button
            $form.find("button[type='submit']").before($hiddenInput);

            $("#modalFormFields").empty().append($form.children());
            $("#dropModal").modal("show"); // Show modal

            // Store and display drop target ID in the modal
            $("#modalDropTarget").text(dropTargetId || "N/A");

            $("#modalFormFields").data("action-id", actionId);
            $("#modalFormFields").data("action-name", actionName);
            $("#modalFormFields").data("drop-target-id", dropTargetId);
        } else {
            console.error("Form HTML is undefined or empty!");
        }
    }
});
