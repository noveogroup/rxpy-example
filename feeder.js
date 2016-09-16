(function (global, $, undefined) {
    function main() {
        var $input = $('#textInput'),
            $results = $('#results');
        var ws = new WebSocket("ws://localhost:8080/ws");

        $input.keyup(function(ev) {
            var msg = { term: ev.target.value };
            ws.send(JSON.stringify(msg));
        });

        ws.onmessage = function(msg) {
            var value = JSON.parse(msg.data);
            if (value === "clear") {$results.empty(); return;}

            // Append the results
            $('<li><a tabindex="-1" href="' + value.link +
                '">' + value.title +'</a> <p>' + value.published +
                '</p><p>' + value.summary + '</p></li>'
            ).appendTo($results);
            $results.show();
        }
    }
    main();
}(window, jQuery));

