from subprocess import PIPE

import re
import shutil
import os
import asyncio
import discord

SCRIPT_OR_RECORD = re.compile(r"(?i).*(?:\.rec|\.scr)$")

class GameChannel:
    """Represents a channel that is prepped for playing a game through Xyzzy."""
    def __init__(self, msg, game):
        self.indent = 0
        self.output = False
        self.last = msg.created_at
        self.owner = msg.author
        self.channel = msg.channel
        self.game = game["name"]
        self.file = game["path"]
        self.url = game.get("url", None)
        self.process = None
        self.playing = False
        self.save_path = "./saves/" + str(self.channel.id)
        self.last_save = None

    async def init_process(self):
        """Sets up the channel's game process."""
        if self.process:
            raise Exception("Game already has a process.")

        # Make directory for saving
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)
        else:
            # Clear out existing directory if it exists.
            # This could happen due to a reboot or something.
            shutil.rmtree(self.save_path)
            os.makedirs(self.save_path)

        self.process = await asyncio.create_subprocess_shell("dfrotz -h 80 -w 5000 -R {} {}".format(self.save_path, self.file), stdout=PIPE, stdin=PIPE)

    async def send_story(self, msg, save=None):
        """Sends the story to the game's channel, handling permissions."""
        if self.output:
            print(msg)

        if self.channel.permissions_for(self.channel.guild.me).embed_links:
            await self.channel.send(embed=discord.Embed(description=msg, colour=self.channel.guild.me.top_role.colour), file=save)
        else:
            await self.channel.send("```{}```".format(msg), file=save)

    def send_input(self, input):
        """"""
        if not self.process:
            raise Exception("Channel does not have an attached process.")

        self.process.stdin.write((input + "\n").encode("utf-8", "replace"))

    async def force_quit(self):
        """Forces the channel's game process to end."""
        self.process.terminate()
        self.playing = False

    def check_saves(self):
        """Checks if the user saved the game."""
        files = [x for x in os.listdir(self.save_path) if not SCRIPT_OR_RECORD.match(x)]
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
        shutil.rmtree(self.save_path)

    async def game_loop(self):
        """Enters into the channel's game process loop."""
        if not self.process:
            await self.init_process()

        buffer = b""
        self.playing = True

        while self.process.returncode is None:
            try:
                output = await asyncio.wait_for(self.process.stdout.read(1), 0.5)
                buffer += output
            except asyncio.TimeoutError:
                if buffer != b"":
                    out = buffer.decode("utf-8", "replace")
                    msg = ""

                    for i, line in enumerate(out.splitlines()):
                        line = line.replace("*", "\*").replace("__", "\_\_").replace("~~", "\~\~")

                        if len(msg + line[self.indent:] + "\n") < 2000:
                            msg += line[self.indent:] + "\n"
                        else:
                            await self.send_story(msg)

                            msg = line[self.indent:]

                    msg = msg.strip()
                    saves = self.check_saves()

                    await self.send_story(msg, saves)

                    files = os.listdir(self.save_path)
                    latest = 0

                    for file in os.listdir(self.save_path):
                        mod_time = os.stat("{}/{}".format(self.save_path, file)).st_mtime_ns

                        if mod_time < latest or SCRIPT_OR_RECORD.match(file):
                            os.unlink("{}/{}".format(self.save_path, file))
                        elif mod_time > latest and not SCRIPT_OR_RECORD.match(file):
                            latest = mod_time

                    buffer = b""

        self.playing = False
        last_save = self.check_saves()

        if last_save:
            await self.channel.send("```diff\n-The game has ended.\n+Here is your most recent save from the game.\n```", file=last_save)
        else:
            await self.channel.send("```diff\n-The game has ended.\n```")

        self.cleanup()