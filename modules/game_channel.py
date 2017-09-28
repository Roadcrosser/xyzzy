from subprocess import PIPE
from enum import Enum

import re
import shutil
import os
import asyncio
import discord

SCRIPT_OR_RECORD = re.compile(r"(?i).*(?:\.rec|\.scr)$")

def parse_action(action):
    """Parses an action string to easily clump similar actions"""
    if action.lower() in ("n", "north", "go n", "go north", "walk north", "run north"):
        return "n"
    elif action.lower() in ("s", "south", "go s", "go south", "walk south", "run south"):
        return "s"
    elif action.lower() in ("e", "east", "go e", "go east", "walk east", "run east"):
        return "e"
    elif action.lower() in ("w", "west", "go w", "go west", "walk west", "run west"):
        return "w"
    elif action.lower() in ("[enter]", "(enter)", "{enter}", "<enter>") or action == "ENTER":
        return "ENTER"
    elif action.lower() in ("space", "[space]", "(space)", "{space}", "<space>"):
        return "SPACE"
    elif re.match(r"^(?:x|examine) +(?:.+)", action.lower()):
        return "examine " + action.lower().split(" ", 1)[1].strip()
    elif action.lower() in ("z", "wait"):
        return "wait"
    elif action.lower() in ("i", "inventory", "inv"):
        return "inventory"
    if re.match(r"l(?:ook)(?: .*)?", action.lower()):
        return "look " + action.lower().split(" ", 1)[1].strip() if len(action.lower().split(" ")) > 1 else "look"
    else:
        return action.lower()

class InputMode(Enum):
    ANARCHY = 1
    DEMOCRACY = 2
    DRIVER = 3

class GameChannel:
    """Represents a channel that is prepped for playing a game through Xyzzy."""
    def __init__(self, msg, game):
        self.loop = asyncio.get_event_loop()
        self.indent = 0
        self.output = False
        self.last = msg.created_at
        self.owner = msg.author
        self.channel = msg.channel
        self.game = game
        self.process = None
        self.playing = False
        self.save_path = "./saves/" + str(self.channel.id)
        self.last_save = None
        self.save = None
        self.mode = InputMode.ANARCHY
        self.votes = {}
        self.timer = None
        self.voting = True

    async def _democracy_loop(self):
        try:
            await asyncio.sleep(10)
            await self.channel.send("```py\n@ 5 seconds of voting remaining. @\n```")
            await asyncio.sleep(5)

            self.voting = False
            vote_sort = sorted(self.votes.items(), key=lambda x: len(x[1]), reverse=True)
            highest = sorted(x for x in vote_sort if len(x[1]) == len(vote_sort[0][1]))

            # Discard draws
            if len(highest) > 1:
                highest = [x[0] for x in highest]
                draw_join = '"{}" and "{}"'.format(", ".join(highest[:-1]), highest[-1])

                await self.channel.send("```py\n@ VOTING DRAW @\nDraw between {}\nDitching all current votes and starting fresh.```".format(draw_join))
            else:
                cmd = highest[0][0]
                amt = len(highest[0][1])

                await self.channel.send('```py\n@ VOTING RESULTS @\nRunning command "{}" with {} vote(s).\n```'.format(cmd, amt))
                self._send_input(cmd)

            self.votes = {}
            self.voting = True
            self.timer = None
        except Exception as e:
            print(e)
            raise e

    def _send_input(self, input):
        """Send's text input to the game process."""
        if not self.process:
            raise Exception("Channel does not have an attached process.")

        if input == "ENTER":
            input = ""
        elif input == "SPACE":
            input = " "

        self.process.stdin.write((input + "\n").encode("latin-1", "replace"))

    async def game_loop(self):
        """Enters into the channel's game process loop."""
        if not self.process:
            await self.init_process()

        buffer = b""
        first_time = True
        self.playing = True

        while self.process.returncode is None:
            try:
                output = await asyncio.wait_for(self.process.stdout.read(1), 0.5)
                buffer += output
            except asyncio.TimeoutError:
                if buffer != b"":
                    out = buffer.decode("latin-1", "replace")
                    msg = ""

                    for i, line in enumerate(out.splitlines()):
                        if line.strip() == ".":
                            line = ""

                        line = line.replace("*", "\*").replace("_", "\_").replace("~", "\~")

                        if len(msg + line[self.indent:] + "\n") < 2000:
                            msg += line[self.indent:] + "\n"
                        else:
                            await self.send_story(msg)

                            msg = line[self.indent:]

                    msg = msg.strip()
                    saves = self.check_saves()

                    if first_time:
                        saves = None
                        first_time = False

                    await self.send_story(msg, saves)

                    files = os.listdir(self.save_path)
                    latest = 0

                    for file in os.listdir(self.save_path):
                        mod_time = os.stat("{}/{}".format(self.save_path, file)).st_mtime_ns

                        if mod_time < latest or SCRIPT_OR_RECORD.match(file) or file == "__UPLOADED__.qzl":
                            os.unlink("{}/{}".format(self.save_path, file))
                        elif mod_time > latest and not SCRIPT_OR_RECORD.match(file):
                            latest = mod_time

                    buffer = b""

        self.playing = False

        if self.last_save:
            file = discord.File("{}/{}".format(self.save_path, self.last_save), self.last_save)
            await self.channel.send("```diff\n-The game has ended.\n+Here is your most recent save from the game.\n```", file=file)
        else:
            await self.channel.send("```diff\n-The game has ended.\n```")

        self.cleanup()

    async def force_quit(self):
        """Forces the channel's game process to end."""
        self.process.terminate()
        self.playing = False

        if self.timer:
            self.timer.cancel_task()

    async def handle_input(self, msg, input):
        """Easily handles the various input types for the game."""

        if self.mode == InputMode.ANARCHY:
            # Default mode, anyone can send any command at any time.
            self._send_input(input)
        elif self.mode == InputMode.DEMOCRACY:
            # Players vote on commands. After 15 seconds of input, the top command is picked.
            # On ties, all commands are scrapped and we start again.
            if not self.voting:
                return

            voters = []
            [voters.extend(x) for x in self.votes.values()]

            if msg.author.id in voters:
                return

            action = parse_action(input)

            if action in self.votes:
                self.votes[action] += [msg.author.id]
            else:
                self.votes[action] = [msg.author.id]

            await self.channel.send("{} has voted for `{}`".format(msg.author.mention, action))

            if not self.timer:
                self.timer = self.loop.create_task(self._democracy_loop())

        elif self.mode == InputMode.DRIVER:
            # Only the "driver" can send input. They can pass the "wheel" to other people.
            if msg.author.id == self.owner.id:
                self._send_input(input)
        else:
            raise ValueError("Currently in unknown input state: {}".format(self.mode))

    async def init_process(self):
        """Sets up the channel's game process."""
        if self.process:
            raise Exception("Game already has a process.")

        # Make directory for saving
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)

        if self.save:
            self.process = await asyncio.create_subprocess_shell("dfrotz -h 80 -w 5000 -m -R {} -L {} {}".format(self.save_path, self.save, self.game.path), stdout=PIPE, stdin=PIPE)
        else:
            self.process = await asyncio.create_subprocess_shell("dfrotz -h 80 -w 5000 -m -R {} {}".format(self.save_path, self.game.path), stdout=PIPE, stdin=PIPE)

    async def send_story(self, msg, save=None):
        """Sends the story to the game's channel, handling permissions."""
        if self.output:
            print(msg)

        if self.channel.permissions_for(self.channel.guild.me).embed_links:
            await self.channel.send(embed=discord.Embed(description=msg, colour=self.channel.guild.me.top_role.colour), file=save)
        else:
            await self.channel.send("```{}```".format(msg), file=save)



    def check_saves(self):
        """Checks if the user saved the game."""
        files = [x for x in os.listdir(self.save_path) if not SCRIPT_OR_RECORD.match(x) and x != "__UPLOADED__.qzl"]
        latest = [0, None]

        for file in files:
            mod_time = os.stat("{}/{}".format(self.save_path, file)).st_mtime_ns

            if mod_time > latest[0]:
                latest = [mod_time, file]

        if latest[1] and latest[1] != self.last_save:
            self.last_save = latest[1]
            return discord.File("{}/{}".format(self.save_path, latest[1]), latest[1])
        else:
            return None

    def cleanup(self):
        """Cleans up after the game."""

        # Check if cleanup has already been done.
        if os.path.isdir(self.save_path):
            shutil.rmtree(self.save_path)

