#! /usr/bin/env python

import asyncio
import json
import secrets
import websockets

from asyncio.base_events import Server
from enum import Enum, auto

class Pokemon(dict):
    def __init__(self, paste):
        species_line = paste.split('\n')[0]
        if '(' in species_line:
            species = species_line[species_line.find("(")+1:species_line.find(")")].strip()
        else:
            species = species_line.split('@')[0].strip()
        dict.__init__(self, species=species, paste=paste)

    def species_only(self):
        return { "species": self['species'] }

class TeamName():
    TEAM1 = "TEAM1"
    TEAM2 = "TEAM2"

def other_team(team):
    match team:
        case TeamName.TEAM1:
            return TeamName.TEAM2
        case TeamName.TEAM2:
            return TeamName.TEAM1

class Box(object):
    def __init__(self, box_paste):
        self.box = []
        for paste in box_paste.strip().split('\n\n'):
            self.box.append(Pokemon(paste))
        self.game_score = 0
        self.banned = set()
        self.selected = set()

    def full_box(self):
        return self.box

    def species_only_box(self):
        return [pokemon.species_only() for pokemon in self.box]

    def game_score(self):
        return self.game_score

    def team_paste(self, picks):
        return '\n\n\n'.join([self.box[pick].paste for pick in picks])

    def on_game_win(self):
        self.game_score += 1

    def on_select(self, selection):
        self.selected.add(selection)

    def on_ban(self, ban):
        self.banned.add(ban)

class GameState(Enum):
    FIRST_PICK = auto()
    FIRST_BAN = auto()
    SECOND_PICK = auto()
    SECOND_BAN = auto()
    THIRD_PICK = auto()
    FOURTH_PICK = auto()
    LOCKED_IN = auto()

class Game(object):
    def __init__(self, team1, team2):
        self.state = GameState.FIRST_PICK
        self.team1 = team1
        self.team2 = team2
        self.team1_picks = []
        self.team2_picks = []
        self.team1_bans = []
        self.team2_bans = []
        self.team1_choices = []
        self.team2_choices = []

    def transition(self):
        def add_selections():
            for selection in self.team1_choices:
                self.team1.on_select(selection)
            for selection in self.team2_choices:
                self.team2.on_select(selection)
        def add_bans():
            for ban in self.team1_choices:
                self.team2.on_ban(ban)
            for ban in self.team2_choices:
                self.team1.on_ban(ban)
            match self.state:
                case GameState.FIRST_PICK:
                    add_selections()
                    self.state = GameState.FIRST_BAN
                case GameState.FIRST_BAN:
                    add_bans()
                    self.state = GameState.SECOND_PICK
                case GameState.SECOND_PICK:
                    add_selections()
                    self.state = GameState.SECOND_BAN
                case GameState.SECOND_BAN:
                    add_bans()
                    self.state = GameState.THIRD_PICK
                case GameState.THIRD_PICK:
                    add_selections()
                    self.state = GameState.FOURTH_PICK
                case GameState.FOURTH_PICK:
                    add_selections()
                    self.state = GameState.LOCKED_IN
                case GameState.LOCKED_IN:
                    raise
            self.team1_choices = []
            self.team2_choices = []

    def ready_for_transition(self):
        # CR efan: this isn't right for "lock" choices on THIRD_PICK / FOURTH_PICK
        return len(self.team1_choices) > 0 and len(self.team2_choices) > 0

    def team_paste(self, team):
        match team:
            case TeamName.TEAM1:
                return self.team1.team_paste(self.team1_picks)
            case TeamName.TEAM2:
                return self.team2.team_paste(self.team2_picks)

    def on_choice(self, team, choices):
        match team:
            case TeamName.TEAM1:
                self.team1_choices = choices
            case TeamName.TEAM2:
                self.team2_choices = choices

class ClientMesssageType():
    NEW_MATCH = "new_match"
    JOIN_MATCH = "join_match"
    JOIN_TEAM = "join_team"
    UPDATE_BOX = "update_box"

class ServerMessageType():
    JOINED_MATCH = "joined_match"
    JOINED_TEAM = "joined_team"
    TEAM_PLAYER_UPDATE = "team_player_update"
    TEAM_BOX_UPDATE = "team_box_update"

class Match(object):
    def __init__(self, id):
        self.id = id
        self.team1_connected = set()
        self.team2_connected = set()
        self.connected = set()
        self.team1_players = []
        self.team2_players = []
        self.box1 = None
        self.box2 = None
        self.current_game = None

    def on_box_paste(self, team, box_paste):
        box = Box(box_paste)
        full_box_event = {
            "type": ServerMessageType.TEAM_BOX_UPDATE,
            "team": team,
            "box": box.full_box()
        }
        species_only_box_event = {
            "type": ServerMessageType.TEAM_BOX_UPDATE,
            "team": team,
            "box": box.species_only_box()
        }
        match team:
            case TeamName.TEAM1:
                self.team1 = box
                websockets.broadcast(self.team1_connected, json.dumps(full_box_event))
                websockets.broadcast(self.team2_connected, json.dumps(species_only_box_event))
            case TeamName.TEAM2:
                self.team2 = box
                websockets.broadcast(self.team2_connected, json.dumps(full_box_event))
                websockets.broadcast(self.team1_connected, json.dumps(species_only_box_event))
        
    def start_game(self):
        self.current_game = Game(self.team1, self.team2)

    def ready_to_start_game(self):
        if self.current_game is None:
            return self.box1 is not None and self.box2 is not None
        else:
            return self.current_game.state == GameState.LOCKED_IN

    def add_to_team(self, team, name, websocket):
        match team:
            case TeamName.TEAM1:
                self.team1_players.append(name)
                self.team1_connected.add(websocket)
                players = self.team1_players
            case TeamName.TEAM2:
                self.team2_players.append(name)
                self.team2_connected.add(websocket)
                players = self.team2_players
        self.connected.add(websocket) 
        team_player_event = {
            "type": ServerMessageType.TEAM_PLAYER_UPDATE,
            "team": team,
            "players": players
        }
        websockets.broadcast(self.connected, json.dumps(team_player_event))

MATCHES = {}

async def play(match, team, websocket):
    async for message in websocket:
        event = json.loads(message)
        match event["type"]:
            case ClientMesssageType.UPDATE_BOX:
                match.on_box_paste(team, event["box_paste"])

async def join_match(id, websocket):
    match = MATCHES[id]

    try:
        joined_match_event = {
            "type": ServerMessageType.JOINED_MATCH,
            "id": id,
            "team1_players": match.team1_players,
            "team2_players": match.team2_players
        }
        await websocket.send(json.dumps(joined_match_event))

        join_team_message = await websocket.recv()
        join_team_event = json.loads(join_team_message)
        assert join_team_event["type"] == ClientMesssageType.JOIN_TEAM
        team = join_team_event["team"]
        name = join_team_event["name"]
        match.add_to_team(team, name, websocket)
        joined_team_event = {
            "type": ServerMessageType.JOINED_TEAM,
            "team": team
        }
        await websocket.send(json.dumps(joined_team_event))

        await play(match, team, websocket)

    finally:
        pass

async def new_match(websocket):
    id = secrets.token_urlsafe(8)
    match = Match(id)
    MATCHES[id] = match

    try:
        await join_match(id, websocket)
    finally:
        pass

async def handler(websocket):
    message = await websocket.recv()
    event = json.loads(message)
    match event["type"]:
        case ClientMesssageType.NEW_MATCH:
            await new_match(websocket)
        case ClientMesssageType.JOIN_MATCH:
            id = event["id"]
            await join_match(id, websocket)
        case unexpected:
            print(event)

async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())