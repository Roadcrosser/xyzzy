from modules.command_sys import command
from subprocess import PIPE

import traceback as tb
import inspect
import asyncio
import disnake as discord
import re
import sys
import importlib
import os.path

from xyzzy import Xyzzy


class Owner:
    def __init__(self, xyzzy: Xyzzy):
        self.xyzzy = xyzzy

    @command(aliases=["eval"], usage="[ python ]", owner=True)
    async def evaluate(self, ctx):
        """
        Executes arbitrary Python code.
        [This command may only be used by trusted individuals.]
        """
        env = {"bot": self.xyzzy, "ctx": ctx, "message": ctx.msg}

        try:
            out = eval(ctx.raw, env)

            if inspect.isawaitable(out):
                out = await out
        except Exception as e:
            out = str(e)

        await ctx.send("```py\n{}\n```".format(out))

    @command(owner=True)
    async def shutdown(self, ctx):
        """
        After confirmation, shuts down the bot and all running games.
        [This command may only be used by trusted individuals.]
        """
        if self.xyzzy.channels:
            await ctx.send(
                "```diff\n"
                "!There are currently {} games running on my system.\n"
                "-If you shut me down now, all unsaved data regarding these games could be lost!\n"
                "(Use `{}nowplaying` for a list of currently running games.)\n```".format(
                    len(self.xyzzy.channels), self.xyzzy.user.mention
                )
            )

        await ctx.send(
            "```md\n## Are you sure you want to shut down the bot? ##\n[y/n]:\n```"
        )

        while True:
            try:
                check = (
                    lambda x: x.channel == ctx.msg.channel
                    and x.author == ctx.msg.author
                )
                msg = await self.xyzzy.wait_for("message", check=check, timeout=30)

                if re.match(
                    r"^`?({} ?)?y(es)?`?$".format(self.xyzzy.user.mention),
                    msg.content.lower(),
                ):
                    await ctx.send("```asciidoc\n.Xyzzy.\n// Now shutting down...\n```")
                    await self.xyzzy.logout()
                elif re.match(
                    r"^`?({} ?)?no?`?$".format(self.xyzzy.user.mention),
                    msg.content.lower(),
                ):
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

        count = 0
        with ctx.msg.channel.typing():
            for chan in self.xyzzy.channels.values():
                try:
                    await chan.channel.send("```{}```".format(ctx.raw))
                    count += 1
                except:
                    pass

        return await ctx.send(
            f"```diff\n+ Announcement as been sent to {count} channels. (Failed in {len(self.xyzzy.channels) - count})\n```"
        )

    @command(usage="[ module ]", owner=True, has_site_help=False)
    async def reload(self, ctx):
        """
        Reloads the module specified in [module].
        [This command may only be used by trusted individuals.]
        """

        if not ctx.args:
            return await ctx.send("```diff\n-No module to reload.\n```")

        if os.path.exists("commands/{}.py".format(ctx.args[0].lower())):
            self.xyzzy.commands.reload_module("commands." + ctx.args[0].lower())
        elif (
            os.path.exists("modules/{}.py".format(ctx.args[0].lower()))
            and "modules.{}".format(ctx.args[0].lower()) in sys.modules
        ):
            del sys.modules["modules.{}".format(ctx.args[0].lower())]
            importlib.import_module("modules.{}".format(ctx.args[0].lower()))
        elif os.path.exists("modules/{}.py".format(ctx.args[0].lower())):
            return await ctx.send("```diff\n-Module is not loaded.\n```")
        else:
            return await ctx.send("```diff\n-Unknown thing to reload.\n```")

        await ctx.send(
            '```diff\n+Reloaded module "{}".\n```'.format(ctx.args[0].lower())
        )

    @command(owner=True)
    async def nowplaying(self, ctx):
        """
        Sends you a direct message containing all currently running xyzzy instances across Discord.
        [This command may only be used by trusted individuals.]
        """
        if not self.xyzzy.channels:
            return await ctx.send(
                "```md\n## Nothing is currently being played. ##\n```", dest="author"
            )

        msg = "```md\n## Currently playing games: ##\n"

        for chan in self.xyzzy.channels.values():
            msg += "[{0.channel.guild.name}]({0.channel.name}) {0.game.name} {{{1} minutes ago}}\n".format(
                chan, (ctx.msg.created_at - chan.last).total_seconds() // 60
            )

        msg += "```"

        await ctx.send(msg, dest="author")

    @command(owner=True, has_site_help=False)
    async def repl(self, ctx):
        """Repl in Discord. Because debugging using eval is a PiTA."""
        check = (
            lambda m: m.content.startswith("`")
            and m.author == ctx.msg.author
            and m.channel == ctx.msg.channel
        )
        locals = {}
        globals = {"discord": discord, "xyzzy": self.xyzzy, "ctx": ctx, "last": None}

        await ctx.send(
            "```You sit down at the terminal and press a key.\nA message appears.```"
            "```\n"
            "      **** XYZZY PYTHON V3.5 REPL ****\n"
            " 4GB RAM SYSTEM   A LOT OF PYTHON BYTES FREE\n\n"
            "READY.\n"
            "```"
        )

        while True:
            resp = await self.xyzzy.wait_for("message", check=check)
            clean = resp.content.strip("` \n")

            if clean.lower() in ("quit", "exit", "exit()", "quit()"):
                return await ctx.send("```You stand up from the terminal.```")

            runner = exec

            if clean.count("\n") == 0:
                try:
                    res = compile(clean, "<repl>", "eval")
                    runner = eval
                except SyntaxError:
                    pass

            if runner is exec:
                try:
                    res = compile(clean, "<repl>", "exec")
                except SyntaxError as e:
                    if e.text is None:
                        await ctx.send(
                            "```py\n{0.__class__.__name__}: {0}\n```".format(e)
                        )
                    else:
                        await ctx.send(
                            "```py\n{0.text}{1:>{0.offset}}\n{0.__class__.__name__}: {0}\n```".format(
                                e, "^"
                            )
                        )

                    continue

            globals["last"] = resp
            fmt = None

            try:
                res = runner(res, globals, locals)

                if inspect.isawaitable(res):
                    res = await res

                if res:
                    msg = "```py\n{}\n```".format(res)
                else:
                    msg = "```Nothing happens.```"
            except Exception as e:
                msg = "```py\n{}\n```".format(tb.format_exc())

            if msg:
                try:
                    await ctx.send(msg)
                except discord.Forbidden:
                    pass
                except discord.HTTPException as e:
                    await ctx.send("Unexpected error: `{}`".format(e))

    @command(owner=True, has_site_help=False)
    async def git(self, ctx):
        """Runs some git commands in Discord."""
        if not ctx.args or ctx.args[0] not in ("status", "pull", "gud", "rekt"):
            return await ctx.send(
                "```\n"
                "usage: git <command> [<args>]\n\n"
                "   pull     Fetches latest updates from a remote repository\n"
                "   status   Show the working tree status\n"
                "   gud      Gits gud\n"
                "   rekt     Gits rekt\n"
                "```"
            )

        if ctx.args[0] == "status":
            process = await asyncio.create_subprocess_shell("git status", stdout=PIPE)
            res = await process.stdout.read()

            return await ctx.send("```{}```".format(res.decode("utf8")))

        if ctx.args[0] == "pull":
            async with ctx.typing():
                process = await asyncio.create_subprocess_shell("git pull", stdout=PIPE)
                res = await process.stdout.read()

                await ctx.send("```{}```".format(res.decode("utf8")))

        if ctx.args[0] == "gud":
            if not ctx.args[1:]:
                return await ctx.send("```You are now so gud!```")
            else:
                return await ctx.send(
                    "```{} is now so gud!```".format(ctx.raw.split(" ", 1)[1])
                )

        if ctx.args[0] == "rekt":
            if not ctx.args[1:]:
                return await ctx.send("```You got #rekt!```")
            else:
                return await ctx.send(
                    "```{} got #rekt!```".format(ctx.raw.split(" ", 1)[1])
                )


def setup(xyzzy):
    return Owner(xyzzy)
