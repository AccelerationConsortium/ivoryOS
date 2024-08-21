$(function() {
    $("#sortable-grid").sortable({
        items: ".card",
        cursor: "move",
        opacity: 0.7,
        revert: true,
        placeholder: "ui-state-highlight",
        start: function(event, ui) {
            ui.placeholder.height(ui.item.height());
        },
        update: function() {
            const newOrder = $("#sortable-grid").sortable("toArray");
            $.ajax({
                url: saveOrderUrl,  // saveOrderUrl should be set dynamically in your HTML template
                method: 'POST',
                contentType: 'application/json',
                data: JSON.stringify({ order: newOrder }),
                success: function() {
                    console.log('Order saved');
                }
            });
        }
    }).disableSelection();
});
