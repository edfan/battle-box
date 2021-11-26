function joined_match(event, websocket) {
    $("#match-id").text(event.id);
    $("#team1-players").text(event.team1_players);
    $("#team2-players").text(event.team2_players);
}

function joined_team(event, websocket) {
    $("#team").text(event.team);
}

function team_player_update(event, websocket) {
    switch (event.team) {
        case "TEAM1":
            $("#team1-players").text(event.players);
            break;
        case "TEAM2":
            $("#team2-players").text(event.players);
            break;
    }
}

function team_box_update(event, websocket) {
    switch (event.team) {
        case "TEAM1":
            $("#team1-box").text(JSON.stringify(event.box));
            break;
        case "TEAM2":
            $("#team2-box").text(JSON.stringify(event.box));
            break;
    }
}

$(function () {
    const websocket = new WebSocket("ws://localhost:8001/");
    websocket.addEventListener("message", ({ data }) => {
        const event = JSON.parse(data);
        console.log(event);
        switch (event.type) {
            case "joined_match":
                joined_match(event, websocket);
                break;
            case "joined_team":
                joined_team(event, websocket);
                break;
            case "team_player_update":
                team_player_update(event, websocket);
                break;
            case "team_box_update":
                team_box_update(event, websocket);
                break;
        }
    });
    $("#new-match").click(function() {
        const event = {
            type: "new_match"
        };
        websocket.send(JSON.stringify(event));
    });
    $("#join-match").click(function() {
        const event = {
            type: "join_match",
            id: $("#join-match-id").val()
        };
        websocket.send(JSON.stringify(event));
    });
    $("#join-team1").click(function() {
        const event = {
            type: "join_team",
            team: "TEAM1",
            name: $("#player-name").val()
        };
        websocket.send(JSON.stringify(event));
    });
    $("#join-team2").click(function() {
        const event = {
            type: "join_team",
            team: "TEAM2",
            name: $("#player-name").val()
        };
        websocket.send(JSON.stringify(event));
    });
    $("#update-box").click(function() {
        const event = {
            type: "update_box",
            box_paste: $("#box-input").val()
        };
        websocket.send(JSON.stringify(event));
    });
});