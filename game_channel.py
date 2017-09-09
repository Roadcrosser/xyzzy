from typing import Union
from subprocess import PIPE

import asyncio
import discord

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

    async def init_process(self):
        """Sets up the channel's game process."""
        if self.process:
            raise Exception("Game already has a process.")

        self.process = await asyncio.create_subprocess_shell("dfrotz -h 80 -w 5000 " + self.file, stdout=PIPE, stdin=PIPE)

    async def send_story(self, msg):
        """Sends the story to the game's channel, handling permissions."""
        if self.output:
            print(msg)

        if self.channel.permissions_for(self.channel.guild.me).embed_links:
            await self.channel.send(embed=discord.Embed(description=msg, colour=self.channel.guild.me.top_role.colour))
        else:
            await self.channel.send(msg)

    def send_input(self, input):
        self.process.stdin.write((input + '\n').encode('utf-8', 'replace'))

    async def force_quit(self):
        """Forces the channel's game process to end."""
        self.process.terminate()
        self.process = None
        self.playing = False

    async def game_loop(self):
        """Enters into the channel's game process' loop."""
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

                    await self.send_story(msg)

                    buffer = b""

        self.playing = False
        await self.channel.send("```diff\n-The game has ended.\n```")