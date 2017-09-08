from command_sys import command
import inspect
import asyncio
import re

class Owner:
    def __init__(self, xyzzy):
        self.xyzzy = xyzzy

    @command(aliases=["eval"], usage="[ python ]", owner=True)
    async def debug(self, ctx):
        """
        Executes arbitrary Python code.
        [This command may only be used by trusted individuals.]
        """
        env = {
            "xyzzy": self.xyzzy,
            "ctx": ctx,
            "message": ctx.msg
        }

        out = eval(ctx.clean.split(' ', 1)[1], env)

        if inspect.isawaitable(out):
            out = await out

        await ctx.send("```py\n{}\n```".format(out))

    @command(owner=True)
    async def shutdown(self, ctx):
        """
        After confirmation, shuts down the bot and all running games.
        [This command may only be used by trusted individuals.]
        """
        if self.xyzzy.channels:
            await ctx.send("```diff\n"
                           "!There are currently {} games running on my system.\n"
                           "-If you shut me down now, all unsaved data regarding these games could be lost!\n"
                           "(Use `{}nowplaying` for a list of currently running games.)".format(len(self.xyzzy.channels), self.xyzzy.invoker * 2))

        await ctx.send("```md\n## Are you sure you want to shut down the bot? ##\n[y/n]:\n```")

        while True:
            try:
                check = lambda x: x.channel == ctx.msg.channel and x.author == ctx.msg.author
                msg = await self.xyzzy.wait_for("message", check=check, timeout=30)

                if re.match(r"^`?({})?y(es)?`?$".format(self.xyzzy.invoker * 2), msg.content.lower()):
                    await ctx.send("```asciidoc\n.Xyzzy.\n// Now shutting down...\n```")
                    await self.xyzzy.logout()
                elif re.match(r"^`?({})?no?`?$".format(self.xyzzy.invoker * 2), msg.content.lower()):
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

        for _, chan in self.xyzzy.channels:
            try:
                await chan.channel.send("```{}```".format(ctx.clean))
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

        self.xyzzy.commands.reload_module('commands.' + ctx.args[0].lower())
        await ctx.send('```diff\n+Reloaded module "{}".\n```'.format(ctx.args[0].lower()))

def setup(xyzzy):
    return Owner(xyzzy)