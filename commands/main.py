from command_sys import command
import json

class Main:
    def __init__(self, xyzzy):
        self.xyzzy = xyzzy

    @command(usage="[ command ]", has_site_help=False)
    async def help(self, ctx):
        """Show help for commands."""
        if not ctx.args:
            return await ctx.send("```inform\n"
                                  "Detailed help can be found at the link below.\n"
                                  'For quick information on a command, type "{}help (command)"\n'
                                  "```\n"
                                  "http://xyzzy.roadcrosser.xyz/help/".format(self.xyzzy.invoker * 2))
        elif self.xyzzy.commands.get_command(ctx.args[0].lower()):
            cmd = self.xyzzy.commands.get_command(ctx.args[0].lower())
            msg = """```inform7
"{}{}{}
{}"
```""".format(self.xyzzy.invoker * 2, cmd.name, " " + cmd.usage if cmd.usage else "", cmd.description)

            if cmd.has_site_help:
                msg += "\nMore information: http://xyzzy.roadcrosser.xyz/help/#{}".format(cmd.name)

            return await ctx.send(msg)
        else:
            return await ctx.send("```diff\n"
                                  '-No information found on "{}".\n'
                                  "```".format(ctx.args[0].lower()))

    @command(has_site_help=False)
    async def about(self, ctx):
        """Sends information about xyzzy."""
        await ctx.send("Information about xyzzy can be found here: http://roadcrosser.xyz/zy")

    @command(aliases=["join"], has_site_help=False)
    async def invite(self, ctx):
        """Gives the bot"s invite link."""
        await ctx.send("This bot can be invited through the following URL: <http://xyzzy.roadcrosser.xyz/invite>")

    @command(has_site_help=False)
    async def list(self, ctx):
        """Sends you a direct message containing all stories in xyzzy's library."""
        msg = """```md
# Here are all of the games I have available: #
{}
```
Alternatively, an up-to-date list can be found here: http://xyzzy.roadcrosser.xyz/list""".format("\n".join(x["name"] for x in self.xyzzy.stories))

        if ctx.args and ctx.args[0] == "here":
            await ctx.send(msg)
        else:
            try:
                await ctx.send(msg, dest="author")
            except:
                await ctx.send("I cannot PM you, as you seem to have private messages disabled. However, an up-to-date list is available at: http://xyzzy.roadcrosser.xyz/list")

    @command(usage="[ on|off ]")
    async def backticks(self, ctx):
        if not ctx.args or ctx.args[0] not in ("on", "off"):
            return await ctx.send("```diff\nYou must provide whether you want to turn your backtick preferences ON or OFF.\n```")

        if ctx.args[0] == "on":
            if str(ctx.msg.author.id) not in self.xyzzy.user_preferences["backticks"]:
                self.xyzzy.user_preferences["backticks"].append(str(ctx.msg.author.id))
                await ctx.send("```diff\n+Commands from you now require backticks. (They should look `{}like this`)\n```".format(self.xyzzy.invoker))
            else:
                return await ctx.send("```diff\n!Your preferences are already set to require backticks for commands.\n```")
        else:
            if str(ctx.msg.author.id) in self.xyzzy.user_preferences["backticks"]:
                self.xyzzy.user_preferences["backticks"].remove(str(ctx.msg.author.id))
                await ctx.send("```diff\n+Commands from you no longer require backticks. (They should look {}like this)\n+XYZZY will still accept backticked commands.\n```".format(self.xyzzy.invoker))
            else:
                return await ctx.send("```diff\n!Your preferences are already set such that backticks are not required for commands\n```")

        with open('./bot-data/userprefs.json', 'w') as x:
            json.dump(self.xyzzy.user_preferences, x)

def setup(xyzzy):
    return Main(xyzzy)