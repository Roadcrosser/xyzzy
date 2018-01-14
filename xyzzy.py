import sys # Checking if host platform is Windows

if sys.platform == "win32":
    raise Exception("Xyzzy cannot run on Windows as it requires asyncios's subproccess.")

import shutil # Check if dfrotz is in PATH

if not shutil.which("dfrotz"):
    raise Exception('dfrotz not detected to be in PATH. If you do not have frotz in dumb mode, refer to "https://github.com/DavidGriffith/frotz/blob/master/INSTALL#L78", and then move the dfrotz executable to somewhere that is in PATH, for example /usr/bin.')

from modules.command_sys import Context, Holder
from modules.game import Game
from datetime import datetime
from glob import glob
from random import randint
from configparser import ConfigParser

import os
import json
import re
import asyncio
import traceback
import aiohttp
import discord
import modules.posts as posts

OPTIONAL_CONFIG_OPTIONS = ("home_channel_id", "owner_ids", "carbon_key", "dbots_key", "gist_key", "gist_id")
REQUIRED_CONFIG_OPTIONS = {
    "invoker": '"invoker" option required in configuration.\nMake sure there is a line that is something like "invoker = >".',
    "token": '"token" option required in configuration.\nThis is needed to connect to Discord and actually run.\nMake sure there is a line that is something like "token = hTtPSwWwyOutUBECOMW_AtcH-vdQW4W9WgXc_q".'
}

CAH_REGEX = re.compile(r"(?:can|does|is) this bot (?:play |do )?(?:cah|cards against humanity|pretend you'?re xyzzy)\??")

class ConsoleColours:
    HEADER = "\033[95m"
    OK_BLUE = "\033[94m"
    OK_GREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"

class Xyzzy(discord.Client):
    def __init__(self):
        print(ConsoleColours.HEADER + "Welcome to Xyzzy, v2.0." + ConsoleColours.END)

        if not os.path.exists("./saves/"):
            print('Creating saves directory at "./saves/"')
            os.makedirs("./saves/")

        self.config = {}
        self.timestamp = 0

        print('Reading "options.cfg".')

        parser = ConfigParser()

        with open("./options.cfg") as cfg_data:
            parser.read_string(cfg_data.read())
            self.config = dict(parser._sections["Config"])

        for opt, msg in REQUIRED_CONFIG_OPTIONS.items():
            if opt not in self.config:
                raise Exception(msg)
            else:
                self.__setattr__(opt, self.config[opt])

        for opt in OPTIONAL_CONFIG_OPTIONS:
            if opt in self.config:
                self.__setattr__(opt, self.config[opt])
            else:
                self.__setattr__(opt, None)

        if self.home_channel_id:
            self.home_channel_id = int(self.home_channel_id)

        self.owner_ids = [] if not self.owner_ids else [x.strip() for x in self.owner_ids.split(",")]
        self.home_channel = None
        self.gist_data_cache = None
        self.gist_game_cache = None

        print("Reading game database...")

        with open("./games.json") as games:
            games = json.load(games)
            self.games = {}

            for name, data in games.items():
                if not os.path.exists(data["path"]):
                    print(f"Path for {name} is invalid. Delisting.")
                else:
                    self.games[name] = Game(name, data)

        if not os.path.exists("./bot-data/"):
            print('Creating bot data directory at "./bot-data/"')
            os.makedirs("./bot-data/")

        if not os.path.exists("./save-cache/"):
            print('Creating save cache directory at "./save-cache/"')
            os.makedirs("./save-cache/")

        try:
            print("Loading user preferences...")

            with open("./bot-data/userprefs.json") as pref:
                self.user_preferences = json.load(pref)

            if "unprefixed" not in self.user_preferences:
                with open("./bot-data/userprefs.json", "w") as pref:
                    print(ConsoleColours.OK_BLUE + 'Adding "unprefixed" array to user preferences file...' + ConsoleColours.END)
                    json.dump({**self.user_preferences, "unprefixed": []}, pref)

                    self.user_preferences["unprefixed"] = []
        except FileNotFoundError:
            print(ConsoleColours.WARNING + "User preferences not found. Creating new user preferences file..." + ConsoleColours.END)

            with open("./bot-data/userprefs.json", "w") as pref:
                pref.write('{"version": 1, "backticks": [], "unprefixed": []}')
                self.user_preferences = {
                    "version": 1,
                    "backticks": [],
                    "unprefixed": []
                }

        try:
            print("Loading blocked user list...")

            with open("./bot-data/blocked_users.json") as blk:
                self.blocked_users = json.load(blk)
        except FileNotFoundError:
            print(ConsoleColours.WARNING + "Blocked user list not found. Creating new blocked user list..." + ConsoleColours.END)

            with open("./bot-data/blocked_users.json", "w") as blk:
                blk.write("{}")
                self.blocked_users = {}

        try:
            print("Loading server settings...")

            with open("./bot-data/server_settings.json") as srv:
                self.server_settings = json.load(srv)
        except FileNotFoundError:
            print(ConsoleColours.WARNING + "Server settings not found. Creating new server settings file.." + ConsoleColours.END)

            with open("./bot-data/server_settings.json", "w") as srv:
                srv.write("{}")
                self.server_settings = {}

        self.process = None
        self.thread = None
        self.queue = None
        self.channels = {}

        self.content_regex = re.compile(rf"`{self.invoker}.+`")
        self.session = aiohttp.ClientSession()
        self.commands = Holder(self)

        if os.listdir("./saves"):
            print("Cleaning out saves directory after reboot.")

            for s in os.listdir("./saves"):
                shutil.rmtree("./saves/" + s)

        print(ConsoleColours.OK_GREEN + "Initialisation complete! Connecting to Discord..." + ConsoleColours.END)

        super().__init__()

    def game_count(self):
        return sum(1 for i in self.channels.values() if i.game and not i.game.debug)

    async def update_game(self):
        game = "nothing yet!"

        if self.game_count():
            game = f"{self.game_count()} game{'s' if len(self.channels) > 1 else ''}."

        await self.change_presence(game=discord.Game(name=game))

    async def handle_error(self, ctx, exc):
        trace = "".join(traceback.format_tb(exc.__traceback__))
        err = f"Traceback (most recent call last):\n{trace}{type(exc).__name__}: {exc}"

        print("\n" + ConsoleColours.FAIL + "An error has occured!")
        print(err + ConsoleColours.END)

        if ctx.is_dm():
            print(f'This was caused by a DM with "{ctx.msg.author.name}".\n')
        else:
            print(f'This was caused by a message.\nServer: "{ctx.msg.guild.name}"\nChannel: #{ctx.msg.channel.name}')

        if self.home_channel:
            await self.home_channel.send(f"User: `{ctx.msg.author.name}`\nInput: `{ctx.clean}`\n```py\n{err}\n```")

        await ctx.send(f'```py\nERROR at memory location {hex(randint(2 ** 4, 2 ** 32))}\n  {type(exc).__name__}: {exc}\n\nInput: "{ctx.clean}"\n```')

    async def on_ready(self):
        print("======================\n"
              f"{self.user.name} is online.\n"
              f"Connected with ID {self.user.id}\n"
              f"Accepting commands with the syntax `{self.invoker}command`")

        self.home_channel = self.get_channel(self.home_channel_id)

        for mod in glob("commands/*.py"):
            mod = mod.replace("/", ".").replace("\\", ".")[:-3]

            try:
                self.commands.load_module(mod)
            except Exception as e:
                print(ConsoleColours.FAIL + f'Error loading module "{mod}"\n{e}' + ConsoleColours.END)

        await self.update_game()
        
        if not self.timestamp:
            self.timestamp = datetime.utcnow().timestamp()

            if self.gist_key and self.gist_id:
                url = "https://api.github.com/gists/" + self.gist_id
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "Authorization": "token " + self.gist_key
                }

                print("\nFetching cached GitHub data...")

                async with self.session.get(url, headers=headers) as r:
                    res = await r.json()

                print(f"[{r.status}]")

                self.gist_data_cache = json.loads(res["files"]["xyzzy_data.json"]["content"])
                self.gist_game_cache = json.loads(res["files"]["xyzzy_games.json"]["content"])
                gist_game = sorted([[k, v.url] for k, v in self.games.items()], key=lambda x: x[0])

                if self.gist_game_cache != gist_game:
                    gist_game = json.dumps({
                        "files": {
                            "xyzzy_games.json": {
                                "content": json.dumps(gist_game)
                            }
                        }
                    })

                    async with self.session.patch(url, data=gist_game, headers=headers) as r:
                        print(f"[{r.status}]")

            self.post_loop = await posts.task_loop(self)

    async def on_guild_join(self, guild):
        print(f'I have been added to "{guild.name}".')

        if self.home_channel:
            await self.home_channel.send(f'I have been added to "{guild.name}" (ID: {guild.id}).')

    async def on_guild_remove(self, guild):
        print(f'I have been removed from "{guild.name}".')

        if self.home_channel:
            await self.home_channel.send(f'I have been removed from "{guild.name}" (ID: {guild.id}).')

    async def on_message(self, msg):
        if msg.author.bot or msg.author.id == self.user.id or (msg.guild and not msg.channel.permissions_for(msg.guild.me).send_messages):
            return

        # Hopefully a not so fucky version of the old conditional here.
        # Makes sure that the content actually matches something we like.
        if (not self.content_regex.match(msg.content) and str(msg.author.id) in self.user_preferences["backticks"]) or \
         (not (self.content_regex.match(msg.content) or (msg.content.startswith(self.invoker) and not msg.content.endswith("`"))) and
         str(msg.author.id) not in self.user_preferences["backticks"]) and msg.channel.id not in self.channels:
            # Explanation of how the above works
            # - First line: If the user does have backticks needed, and the content does not have backticks and the prefix, return.
            # - Second line: Else, if the user doesn't have backticks needed, and the content doesn't start with the prefix, or only has one backtick which is at the end, return.
            return

        if not isinstance(msg.channel, discord.DMChannel) and ((str(msg.guild.id) in self.blocked_users and
         str(msg.author.id) in self.blocked_users[str(msg.guild.id)]) or ("global" in self.blocked_users and
         str(msg.author.id) in self.blocked_users["global"])):
            return await msg.author.send("```diff\n"
                                         f'!An administrator has disabled your ability to submit commands in "{msg.guild.name}"\n'
                                         "```")

        clean = msg.content[1:-1] if re.match(r"^`.*`$", msg.content) else msg.content

        # Allows people who have opted in to run commands without a prefix.
        if not clean.startswith(self.invoker) and msg.channel.id in self.channels and self.channels[msg.channel.id].playing and\
         str(msg.author.id) in self.user_preferences["unprefixed"]:
            if msg.content.startswith(("#", "//")):
                return

            channel = self.channels[msg.channel.id]
            channel.last = msg.created_at

            return await channel.handle_input(msg, clean)
        elif not clean.startswith(self.invoker):
            return

        # Without this, an error is thrown below due to only one character.
        if len(clean) == 1:
            return

        # Send game input if a game is running.
        if clean[0] == self.invoker and clean[1] != self.invoker and msg.channel.id in self.channels and self.channels[msg.channel.id].playing:
            channel = self.channels[msg.channel.id]
            channel.last = msg.created_at

            return await channel.handle_input(msg, clean[1:])
        elif not clean.startswith(self.invoker * 2):
            return

        if clean == self.invoker * 2 + "get ye flask":
            return await msg.channel.send("You can't get ye flask!")

        if clean.startswith(self.invoker * 2) and CAH_REGEX.match(clean[2:]):
            return await msg.channel.send("no")

        if not self.commands.get_command(clean[2:].split(" ")[0]):
            return

        try:
            ctx = Context(msg, self)
        except ValueError:
            return await msg.channel.send("Shlex error.")

        try:
            await self.commands.run(ctx)
        except Exception as e:
            await self.handle_error(ctx, e)

if __name__ == "__main__":
    # Only start the bot if it is being run directly
    bot = Xyzzy()
    bot.run(bot.token)