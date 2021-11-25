#! /usr/bin/env python

import asyncio
import secrets
import websockets

from enum import Enum, auto

class Pokemon(object):
    def __init__(self, paste):
        species_line = paste.split('\n')[0]
        if '(' in species_line:
            self.species = species_line[species_line.find("(")+1:species_line.find(")")]
        else:
            self.species = species_line.split('@')[0]
        self.paste = paste

class TeamName(Enum):
    TEAM1 = auto()
    TEAM2 = auto()

class Team(object):
    def __init__(self, box_paste):
        self.box = []
        for paste in box_paste.split('\n\n\n'):
            self.box.append(Pokemon(paste))
        self.game_score = 0
        self.banned = set()
        self.selected = set()

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

class Match(object):
    def __init__(self, id):
        self.id = id
        self.team1 = None
        self.team2 = None
        self.current_game = None

    def on_box_paste(self, team, box_paste):
        match team:
            case TeamName.TEAM1:
                self.team1 = Team(box_paste)
            case TeamName.TEAM2:
                self.team2 = Team(box_paste)
        
    def start_game(self):
        self.current_game = Game(self.team1, self.team2)

    def ready_to_start_game(self):
        if self.current_game is None:
            return self.team1 is not None and self.team2 is not None
        else:
            return self.current_game.state == GameState.LOCKED_IN

async def handler(websocket):
    async for message in websocket:
        print(message)

async def main():
    async with websockets.serve(handler, "", 8001):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())