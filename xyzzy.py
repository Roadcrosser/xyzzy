import sys # Checking if host platform is Windows

if sys.platform == "win32":
    raise Exception("Xyzzy cannot run on Windows as it requires asyncios's subproccess.")

import shutil # Check if dfrotz is in PATH

if not shutil.which("dfrotz"):
    raise Exception('dfrotz not detected to be in PATH. If you do not have frotz in dumb mode, refer to "https://github.com/DavidGriffith/frotz/blob/master/INSTALL#L78", and then move the dfrotz executable to somewhere that is in PATH, for example /usr/bin.')

from command_sys import Context, Holder
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

OPTIONAL_CONFIG_OPTIONS = ("home_channel_id", "owner_ids", "carbon_key", "dbots_key", "gist_key", "gist_id")
REQUIRED_CONFIG_OPTIONS = {
    "invoker": '"invoker" option required in configuration.\nMake sure there is a line that is something like "invoker = >".',
    "token": '"token" option required in configuration.\nThis is needed to connect to Discord and actually run.\nMake sure there is a line that is something like "token = hTtPSwWwyOutUBECOMW_AtcH-vdQW4W9WgXc_q".'
}

CAH_REGEX = re.compile(r"(?:can|does|is) this bot (?:play |do )?(?:cah|cards against humanity|pretend you'?re xyzzy)\??")

class ConsoleColours:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKGREEN = "\033[92m"
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

        self.owner_ids = [] if not self.owner_ids else [x.strip() for x in self.owner_ids.split(",")]
        self.home_channel = None
        self.gist_data_cache = None
        self.gist_story_cache = None

        print("Reading story database...")

        with open("./stories.json") as stories:
            self.stories = json.load(stories)

        if not os.path.exists("./bot-data/"):
            print('Creating bot data directory at "./bot-data/"')
            os.makedirs("./bot-data/")

        try:
            print("Loading user preferences...")

            with open("./bot-data/userprefs.json") as pref:
                self.user_preferences = json.load(pref)
        except FileNotFoundError:
            print(ConsoleColours.WARNING + "User preferences not found. Creating new user preferences file..." + ConsoleColours.END)

            with open("./bot-data/userprefs.json", "w") as pref:
                pref.write('{"version": 1, "backticks": []}')
                self.user_preferences = {
                    "version": 1,
                    "backticks": []
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

        self.game = None
        self.process = None
        self.thread = None
        self.queue = None
        self.channels = {}

        self.content_regex = re.compile(r"`{}.+`".format(self.invoker))
        self.session = aiohttp.ClientSession()
        self.commands = Holder(self)

        print(ConsoleColours.OKGREEN + "Initialisation complete! Connecting to Discord..." + ConsoleColours.END)

        super().__init__()

    async def update_game(self):
        game = "nothing yet!"

        if self.channels:
            game = "{} game{}.".format(len(self.channels), "s" if len(self.channels) > 1 else "")

        await self.change_presence(game=discord.Game(name=game))

    async def handle_error(self, ctx, exc):
        trace = "".join(traceback.format_tb(exc.__traceback__))
        err = "Traceback (most recent call last):\n{}{}: {}".format(trace, type(exc).__name__, exc)

        print("\n" + ConsoleColours.FAIL + "An error has occured!")
        print(err + ConsoleColours.END)

        if ctx.is_dm():
            print('This was caused by a DM with "{}".\n'.format(ctx.msg.author.name))
        else:
            print('This was caused by a message.\nServer: "{}"\nChannel: #{}'.format(ctx.msg.guild.name, ctx.msg.channel.name))

        if self.home_channel:
            await self.home_channel.send("User: `{}`\nInput: `{}`\n```py\n{}\n```".format(ctx.msg.author.name, ctx.clean, err))

        await ctx.send('```py\nERROR at memory location {}\n  {}: {}\n\nInput: "{}"\n```'.format(hex(randint(2 ** 4, 2 ** 32)), type(exc).__name__, exc, ctx.clean))

    async def on_ready(self):
        print("======================\n"
              "{0.user.name} is online.\n"
              "Connected with ID {0.user.id}\n"
              "Accepting commands with the syntax `{0.invoker}command`".format(self))

        self.home_channel = self.get_channel(self.home_channel_id)

        for mod in glob("commands/*.py"):
            mod = mod.replace("/", ".").replace("\\", ".")[:-3]

            try:
                self.commands.load_module(mod)
            except Exception as e:
                print(ConsoleColours.FAIL + 'Error loading module "{}"\n{}'.format(mod, e) + ConsoleColours.END)

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

                print("[{}]".format(r.status))

                self.gist_data_cache = json.loads(res["files"]["xyzzy_data.json"]["content"])
                self.gist_story_cache = json.loads(res["files"]["xyzzy_stories.json"]["content"])
                gist_story = sorted([i for i in self.stories])

                if self.gist_story_cache != gist_story:
                    gist_story = json.dumps({
                        "files": {
                            "xyzzy_stories.json": {
                                "content": json.dumps(gist_story)
                            }
                        }
                    })

                    async with self.session.patch(url, data=gist_story, headers=headers) as r:
                        print("[{}]".format(r.status))

            while True:
                guilds = len(self.guilds)
                sessions = len(self.channels)

                if self.carbon_key:
                    url = "https://www.carbonitex.net/discord/data/botdata.php" # PHP SUCKS
                    data = {
                        "key": self.carbon_key,
                        "servercount": guilds
                    }

                    print("\nPosting to Carbonitex...")

                    async with self.session.post(url, data=data) as r:
                        text = await r.text()

                    print("[{}] {}".format(r.status, text))

                if self.dbots_key:
                    url = "https://bots.discord.pw/api/bots/{}/stats".format(self.user.id)
                    data = json.dumps({"server_count": guilds})
                    headers = {
                        "Authorization": self.dbots_key,
                        "content-type": "application/json"
                    }

                    print("\nPosting to Discord Bots...")

                    async with self.session.post(url, data=data, headers=headers) as r:
                        text = await r.text()

                    print("[{}] {}".format(r.status, text))

                if self.gist_key and self.gist_id:
                    url = "https://api.github.com/gists/" + self.gist_id
                    data = {
                        "server_count": guilds,
                        "session_count": sessions,
                        "token": "MTcxMjg4MjM4NjU5NjAwMzg0.Bqwo2M.YJGwHHKzHqRcqCI2oGRl-tlRpn"
                    }

                    if self.gist_data_cache != data:
                        self.gist_data_cache = data
                        data = json.dumps({
                            "files": {
                                "xyzzy_data.json": {
                                    "content": json.dumps(data)
                                }
                            }
                        })
                        headers = {
                            "Accept": "application/vnd.github.v3+json",
                            "Authorization": "token " + self.gist_key
                        }

                        print("\nPosting to GitHub...")

                        async with self.session.patch(url, data=data, headers=headers) as r:
                            print("[{}]".format(r.status))
                    else:
                        print("\nGitHub posting skipped.")

                await asyncio.sleep(3600) # Post stuff every hour

    async def on_guild_join(self, guild):
        print('I have been invited to tell stories in "{}".'.format(guild.name))

        if self.home_channel:
            await self.home_channel.send('I have been invited to tell stories in "{0.name}" (ID: {0.id}).'.format(guild))

    async def on_guild_remove(self, guild):
        print('I have been removed from "{}".'.format(guild.name))

        if self.home_channel:
            await self.home_channel.send('I have been removed from "{0.name}" (ID: {0.id}).'.format(guild))

    async def on_message(self, msg):
        if msg.author.bot or msg.author.id == self.user.id or not msg.channel.permissions_for(msg.guild.me).send_messages:
            return

        # Hopefully a not so fucky version of the old conditional here.
        # Makes sure that the content actually matches something we like.
        if (not self.content_regex.match(msg.content) and str(msg.author.id) in self.user_preferences["backticks"]) or \
         (not (self.content_regex.match(msg.content) or (msg.content.startswith(self.invoker) and not msg.content.endswith("`"))) and str(msg.author.id) not in self.user_preferences["backticks"]):
            # Explanation of how the above works
            # - First line: If the user does have backticks needed, and the content does not have backticks and the prefix, return.
            # - Second line: Else, if the user doesn't have backticks needed, and the content doesn't start with the prefix, or only has one backtick which is at the end, return.
            return

        if not isinstance(msg.channel, discord.DMChannel) and \
                ((str(msg.guild.id) in self.blocked_users and str(msg.author.id) in self.blocked_users[str(msg.guild.id)]) or
                ("global" in self.blocked_users and str(msg.author.id) in self.blocked_users["global"])):
            return await msg.author.send("```diff\n"
                                         '!An administrator has disabled your ability to submit commands in "{}"\n'
                                         "```".format(msg.guild.name))

        clean = msg.content[1:-1] if self.content_regex.match(msg.content) else msg.content

        # Without this, an error is thrown below due to only one character.
        if len(clean) == 1:
            return

        # Send game input if a game is running.
        if clean[0] == self.invoker and clean[1] != self.invoker and msg.channel.id in self.channels and self.channels[msg.channel.id].playing:
            self.channels[msg.channel.id].last = msg.created_at
            return self.channels[msg.channel.id].send_input(clean[1:])

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