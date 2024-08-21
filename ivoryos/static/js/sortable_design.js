$(document).ready(function(){
    function slideout(){
        setTimeout(function(){
            $("#response").slideUp("slow", function () {});
        }, 2000);
    }

    $("#response").hide();

    $(function() {
        $("#list ul").sortable({
            cancel: ".unsortable",
            opacity: 0.8,
            cursor: 'move',
            update: function() {
                var item_order = [];
                $('ul.reorder li').each(function() {
                    item_order.push($(this).attr("id"));
                });
                var order_string = 'order=' + item_order.join(',');

                $.ajax({
                    method: "POST",
                    url: updateListUrl,  // updateListUrl should be set dynamically in your HTML template
                    data: order_string,
                    cache: false,
                    success: function(data){
                        $("#response").html(data);
                        $("#response").slideDown('slow');
                        slideout();
                    }
                });
            }
        });
    });
});
