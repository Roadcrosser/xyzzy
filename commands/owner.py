from modules.command_sys import command
from subprocess import PIPE

import traceback as tb
import inspect
import asyncio
import discord
import re
import sys
import importlib
import os.path

class Owner:
    def __init__(self, xyzzy):
        self.xyzzy = xyzzy

    @command(aliases=["eval"], usage="[ python ]", owner=True)
    async def evaluate(self, ctx):
        """
        Executes arbitrary Python code.
        [This command may only be used by trusted individuals.]
        """
        env = {
            "bot": self.xyzzy,
            "ctx": ctx,
            "message": ctx.msg
        }

        try:
            out = eval(ctx.raw, env)

            if inspect.isawaitable(out):
                out = await out
        except Exception as e:
            out = str(e)

        await ctx.send(f"```py\n{out}\n```")

    @command(owner=True)
    async def shutdown(self, ctx):
        """
        After confirmation, shuts down the bot and all running games.
        [This command may only be used by trusted individuals.]
        """
        if self.xyzzy.channels:
            await ctx.send("```diff\n"
                           f"!There are currently {len(self.xyzzy.channels)} games running on my system.\n"
                           "-If you shut me down now, all unsaved data regarding these games could be lost!\n"
                           f"(Use `{self.xyzzy.invoker * 2}nowplaying` for a list of currently running games.)\n```")

        await ctx.send("```md\n## Are you sure you want to shut down the bot? ##\n[y/n]:\n```")

        while True:
            try:
                check = lambda x: x.channel == ctx.msg.channel and x.author == ctx.msg.author
                msg = await self.xyzzy.wait_for("message", check=check, timeout=30)

                if re.match(rf"^`?({self.xyzzy.invoker * 2})?y(es)?`?$", msg.content.lower()):
                    await ctx.send("```asciidoc\n.Xyzzy.\n// Now shutting down...\n```")
                    await self.xyzzy.logout()
                elif re.match(rf"^`?({self.xyzzy.invoker * 2})?no?`?$", msg.content.lower()):
                    return await ctx.send("```css\nShutdown aborted.\n```")
                else:
                    await ctx.send("```md\n# Invalid response. #\n```")
            except asyncio.TimeoutError:
                return await ctx.send("```css\nMessage timeout: Shutdown aborted.\n```")

    @command(owner=True, usage="[ announcement ]")
    async def announce(self, ctx):
        """
        For each channel currently playing a game, sends the text in [announcement].
        [This command may only be used by trusted individuals.]
        """
        if not ctx.args:
            return await ctx.send("```diff\n-Nothing to announce.\n```")

        for chan in self.xyzzy.channels.values():
            try:
                await chan.channel.send(f"```{ctx.raw}```")
            except:
                pass

    @command(usage="[ module ]", owner=True, has_site_help=False)
    async def reload(self, ctx):
        """
        Reloads the module specified in [module].
        [This command may only be used by trusted individuals.]
        """

        if not ctx.args:
            return await ctx.send("```diff\n-No module to reload.\n```")

        if os.path.exists(f'commands/{ctx.args[0].lower()}.py'):
            self.xyzzy.commands.reload_module('commands.' + ctx.args[0].lower())
        elif os.path.exists(f'modules/{ctx.args[0].lower()}.py') and f'modules.{ctx.args[0].lower()}' in sys.modules:
            del sys.modules[f'modules.{ctx.args[0].lower()}']
            importlib.import_module(f'modules.{ctx.args[0].lower()}')
        elif os.path.exists(f'modules/{ctx/args[0].lower()}.py'):
            return await ctx.send("```diff\n-Module is not loaded.\n```")
        else:
            return await ctx.send("```diff\n-Unknown thing to reload.\n```")

        await ctx.send(f'```diff\n+Reloaded module "{ctx.args[0].lower()}".\n```')

    @command(owner=True)
    async def nowplaying(self, ctx):
        """
        Sends you a direct message containing all currently running xyzzy instances across Discord.
        [This command may only be used by trusted individuals.]
        """
        if not self.xyzzy.channels:
            return await ctx.send("```md\n## Nothing is currently being played. ##\n```", dest="author")

        msg = "```md\n## Currently playing games: ##\n"
        time = (ctx.msg.created_at - chan.last).total_seconds() // 60

        for chan in self.xyzzy.channels.values():
            msg += f"[{chan.channel.guild.name}]({chan.channel.name}) {chan.game.name} {{{time} minutes ago}}\n"

        msg += '```'

        await ctx.send(msg, dest="author")

    @command(owner=True, has_site_help=False)
    async def repl(self, ctx):
        """Repl in Discord. Because debugging using eval is a PiTA."""
        check = lambda m: m.content.startswith("`") and m.author == ctx.msg.author and m.channel == ctx.msg.channel
        locals = {}
        globals = {
            "discord": discord,
            "xyzzy": self.xyzzy,
            "ctx": ctx,
            "last": None
        }

        await ctx.send("```You sit down at the terminal and press a key.\nA message appears.```"
                       "```\n"
                       "      **** XYZZY PYTHON V3.5 REPL ****\n"
                       " 4GB RAM SYSTEM   A LOT OF PYTHON BYTES FREE\n\n"
                       "READY.\n"
                       "```")

        while True:
            resp = await self.xyzzy.wait_for("message", check=check)
            clean = resp.content.strip("` \n")

            if clean.lower() in ("quit", "exit", "exit()", "quit()"):
                return await ctx.send("```You stand up from the terminal.```")

            runner = exec

            if clean.count("\n") == 0:
                try:
                    res =  compile(clean, "<repl>", "eval")
                    runner = eval
                except SyntaxError:
                    pass

            if runner is exec:
                try:
                    res = compile(clean, "<repl>", "exec")
                except SyntaxError as e:
                    if e.text is None:
                        await ctx.send(f"```py\n{e.__class__.__name__}: {e}\n```")
                    else:
                        await ctx.send(f"```py\n{e.text}{'^':>{e.offset}}\n{e.__class__.__name__}: {e}\n```")

                    continue

            globals["last"] = resp
            fmt = None

            try:
                res = runner(res, globals, locals)

                if inspect.isawaitable(res):
                    res = await res

                if res:
                    msg = f"```py\n{res}\n```"
                else:
                    msg = "```Nothing happens.```"
            except Exception as e:
                msg = f"```py\n{tb.format_exc()}\n```"

            if msg:
                try:
                    await ctx.send(msg)
                except discord.Forbidden:
                    pass
                except discord.HTTPException as e:
                    await ctx.send(f"Unexpected error: `{e}`")

    @command(owner=True, has_site_help=False)
    async def git(self, ctx):
        """Runs some git commands in Discord."""
        if not ctx.args or ctx.args[0] not in ("status", "pull", "gud", "rekt"):
            return await ctx.send("```\n"
                                  "usage: git <command> [<args>]\n\n"
                                  "   pull     Fetches latest updates from a remote repository\n"
                                  "   status   Show the working tree status\n"
                                  "   gud      Gits gud\n"
                                  "   rekt     Gits rekt\n"
                                  "```")

        if ctx.args[0] == "status":
            process = await asyncio.create_subprocess_shell("git status", stdout=PIPE)
            res = await process.stdout.read()

            return await ctx.send(f"```{res.decode('utf8')}```")

        if ctx.args[0] == "pull":
            async with ctx.typing():
                process = await asyncio.create_subprocess_shell("git pull", stdout=PIPE)
                res = await process.stdout.read()

                await ctx.send(f"```{res.decode('utf8')}```")

        if ctx.args[0] == "gud":
            if not ctx.args[1:]:
                return await ctx.send("```You are now so gud!```")
            else:
                return await ctx.send(f"```{ctx.raw.split(' ', 1)[1]} is now so gud!```")

        if ctx.args[0] == "rekt":
            if not ctx.args[1:]:
                return await ctx.send("```You got #rekt!```")
            else:
                return await ctx.send(f"```{ctx.raw.split(' ', 1)[1]} got #rekt!```")


def setup(xyzzy):
    return Owner(xyzzy)