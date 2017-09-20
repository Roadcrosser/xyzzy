from command_sys import command
from game_channel import GameChannel
from io import BytesIO
from math import floor

import os
import re
import json
import asyncio
import quetzal_parser as qzl

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
            msg = '```inform7\n"{}{}{}{}"\n```'.format(self.xyzzy.invoker * 2, cmd.name, " " + cmd.usage + " " if cmd.usage else "", cmd.description)

            if cmd.has_site_help:
                msg += "\nMore information: http://xyzzy.roadcrosser.xyz/help/#{}".format(cmd.name)

            return await ctx.send(msg)
        else:
            return await ctx.send('```diff\n-No information found on "{}".\n```'.format(ctx.args[0].lower()))

    @command(has_site_help=False)
    async def ping(self, ctx):
        msg = await ctx.send("Pong!")

        await msg.edit(content="Pong! `{}ms`".format(floor(msg.created_at.timestamp() * 1000 - ctx.msg.created_at.timestamp() * 1000)))

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
Alternatively, an up-to-date list can be found here: http://xyzzy.roadcrosser.xyz/list""".format("\n".join(sorted(x["name"] for x in self.xyzzy.stories)))

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
                await ctx.send("```diff\n"
                               "+Commands from you no longer require backticks. (They should look {}like this)\n"
                               "+XYZZY will still accept backticked commands."
                               "\n```".format(self.xyzzy.invoker))
            else:
                return await ctx.send("```diff\n!Your preferences are already set such that backticks are not required for commands\n```")

        with open('./bot-data/userprefs.json', 'w') as x:
            json.dump(self.xyzzy.user_preferences, x)

    @command(usage="[ game ]")
    async def play(self, ctx):
        """
        Tells xyzzy to start playing the [game] in the current channel.
        If no game is found with that name, xyzzy will show you all games with the [game] in their name.
        If only one game is found with that text in it's name, it will start that game.
        If you run the command with a save file attached, xyzzy will try to load a game from it.
        """
        # Don't do DMs kids.
        if ctx.is_dm():
            return await ctx.send("```accesslog\nSorry, but games cannot be played in DMs. Please try again in a server.```")

        if ctx.msg.channel.id in self.xyzzy.channels:
            return await ctx.send('```accesslog\nSorry, but #{} is currently playing "{}". Please try again after the story has finished.\n```'.format(ctx.msg.channel.name, self.xyzzy.channels[ctx.msg.channel.id].game))

        if not ctx.msg.attachments:
            if not ctx.args:
                return await ctx.send("```diff\n-Please provide a game to play.\n```")

            print("Searching for " + ctx.raw)

            stories = {x: y for x, y in self.xyzzy.stories.items() if ctx.raw.lower() in x.lower() or [z for z in y["aliases"] if ctx.raw.lower() in z.lower()]}
            perfect_match = None

            if stories:
                perfect_match = {x: y for x, y in stories.items() if ctx.raw.lower() == x.lower() or [z for z in y["aliases"] if ctx.raw.lower() == z.lower()]}

            if not stories:
                return await ctx.send('```diff\n-I couldn\'t find any stories matching "{}"\n```'.format(ctx.raw))
            elif len(stories) > 1 and not perfect_match:
                return await ctx.send("```accesslog\n"
                                    'I couldn\'t find any stories with that name, but I found "{}" in {} other stories. Did you mean one of these?\n'
                                    '"{}"\n'
                                    "```".format(ctx.raw, len(stories), "\n".join(sorted(x for x in stories))))

            if perfect_match:
                game = list(perfect_match.items())[0]
                game = {"name": game[0], **game[1]}
            else:
                game = list(stories.items())[0]
                game = {"name": game[0], **game[1]}
        else:
            # Attempt to load a game from a possible save file.
            attach = ctx.msg.attachments[0]

            if attach.width or attach.height:
                return await ctx.send("```diff\n-Images are not save files.\n```")

            async with ctx.typing():
                async with self.xyzzy.session.get(attach.url) as r:
                    res = await r.read()

                try:
                    qzl_headers = qzl.parse_quetzal(BytesIO(res))
                except Exception as e:
                    if str(e) == "Invalid file format.":
                        return await ctx.send("```diff\n-Invalid file format.\n```")
                    else:
                        return await ctx.send("```diff\n-{}\n```".format(str(e)))

                for name, stuff in self.xyzzy.stories.items():
                    comp_res = qzl.compare_quetzal(qzl_headers, stuff["path"])

                    if comp_res:
                        game = {"name": name, **stuff}
                        break

                if not comp_res:
                    return await ctx.send("```diff\n-No games matching your save file could be found.\n```")

                if not os.path.exists("./saves/{}".format(ctx.msg.channel.id)):
                    os.makedirs("./saves/{}".format(ctx.msg.channel.id))

                with open("./saves/{}/__UPLOADED__.qzl".format(ctx.msg.channel.id), "wb") as save:
                    save.write(res)

        if str(ctx.msg.guild.id) in self.xyzzy.server_settings:
            if game["name"] in self.xyzzy.server_settings[str(ctx.msg.guild.id)]["blocked_games"]:
                return await ctx.send('```diff\n- "{}" has been blocked on this server.\n```'.format(game["name"]))

        print("Now loading {} for #{} (Server: {})".format(game["name"], ctx.msg.channel.name, ctx.msg.guild.name))

        chan = GameChannel(ctx.msg, game)
        self.xyzzy.channels[ctx.msg.channel.id] = chan

        if ctx.msg.attachments:
            chan.save = "./saves/{}/__UPLOADED__.qzl".format(ctx.msg.channel.id)

        await ctx.send('```py\nLoaded "{}"{}\n```\n{}'.format(chan.game, " by " + game["author"] if "author" in game else "", "<" + chan.url + ">" or ""))
        await chan.init_process()
        await self.xyzzy.update_game()
        await chan.game_loop()
        await self.xyzzy.update_game()
        del self.xyzzy.channels[ctx.msg.channel.id]

    @command()
    async def output(self, ctx):
        """
        Toggles whether the text being sent to this channel from a currently playing story also should be printed to the terminal.
        This is functionally useless in most cases.
        """
        if ctx.msg.channel.id not in self.xyzzy.channels:
            return await ctx.send("```diff\n-Nothing is being played in this channel.\n```")

        chan = self.xyzzy.channels[ctx.msg.channel.id]

        if chan.output:
            chan.output = False
            await ctx.send('```basic\n"Terminal Output" is now OFF.\n```'.format(chan.indent))
        else:
            chan.output = True
            await ctx.send('```basic\n"Terminal Output" is now ON\n```'.format(chan.indent))

    @command(usage="[ indent level ]")
    async def indent(self, ctx):
        """
        Will make xyzzy scrap the first nth characters for each line in his output.
        If you're noticing random spaces after each line break, use this command.
        [Indent level] must be an integer between 0 and the total console width. (Usually 80.)
        """
        if ctx.msg.channel.id not in self.xyzzy.channels:
            return await ctx.send("```diff\n-Nothing is being played in this channel.\n```")

        if not ctx.args:
            return await ctx.send("```diff\n-You need to supply a number.\n```")

        chan = self.xyzzy.channels[ctx.msg.channel.id]

        try:
            chan.indent = int(ctx.args[0])
            await ctx.send('```basic\n"Indent Level" is now {}.\n```'.format(chan.indent))
        except ValueError:
            await ctx.send("```diff\n!ERROR: Valid number not supplied.\n```".format(chan.indent))

    @command(aliases=["mortim"])
    async def forcequit(self, ctx):
        """
        After confirmation, terminates the process running the xyzzy game you are playing.
        [It is recommended to try to exit the game using an in-game method before using this command.] >quit usually works.
        This command has an alias in >>mortim
        """
        if ctx.msg.channel.id not in self.xyzzy.channels:
            return await ctx.send("```diff\n-Nothing is being played in this channel.\n```")

        await ctx.send("```diff\n"
                       "Are you sure you want to quit?\n"
                       "-Say Y or Yes to close the program.\n"
                       "!NOTE: You will lose all unsaved progress!\n"
                       "+Send any other message to continue playing.\n"
                       "```")

        try:
            check = lambda x: x.channel == ctx.msg.channel and x.author == ctx.msg.author
            msg = await self.xyzzy.wait_for("message", check=check, timeout=30)

            if re.match(r"^`?({})?y(es)?`?$", msg.content.lower()):
                chan = self.xyzzy.channels[ctx.msg.channel.id]

                await chan.force_quit()
                chan.cleanup()
                del self.xyzzy.channels[ctx.msg.channel.id]
            else:
                await ctx.send("```diff\n+Continuing game.\n```")
        except asyncio.TimeoutError:
            await ctx.send("```diff\n+Message timeout expired. Continuing game.\n```")
        except ProcessLookupError:
            chan = self.xyzzy.channels[ctx.msg.channel.id]
            saves = chan.check_saves()

            if saves:
                await self.channel.send("```diff\n-The game has ended.\n+Here are your saves from the game.\n```", files=saves)
            else:
                await ctx.send("```diff\n-The game has ended.\n```")

            chan.cleanup()
            del self.xyzzy.channels[ctx.msg.channel.id]

    @command(aliases=["upload"], usage="[ Save as Attachment ]")
    async def uploadsave(self, ctx):
        """Uploads a save to be played from during a game."""
        if not ctx.msg.attachments:
            return await ctx.send("Please send a save file as an attachment.")

        attach = ctx.msg.attachments[0]

        if attach.height or attach.width:
            return await ctx.send("```diff\n-Images are not save files.\n```")

        async with ctx.typing():
            async with self.xyzzy.session.get(attach.url) as r:
                res = await r.read()

            try:
                qzl_headers = qzl.parse_quetzal(BytesIO(res))
            except Exception as e:
                if str(e) == "Invalid file format.":
                    return await ctx.send("```diff\n-Invalid file format.\n```")
                else:
                    return await ctx.send("```diff\n-{}\n```".format(str(e)))

            if not os.path.exists("./saves/{}".format(ctx.msg.channel.id)):
                os.makedirs("./saves/{}".format(ctx.msg.channel.id))

            with open("./saves/{}/{}.qzl".format(ctx.msg.channel.id, attach.filename.rsplit(".")[0]), "wb") as save:
                save.write(res)

        await ctx.send("```diff\n"
                       "+Saved file as '{}.qzl'.\n"
                       "+You can load it by playing the relevant game and using the RESTORE command.\n"
                       "-Note that this will get removed during the next game played if it is not loaded, or after the next reboot.\n"
                       "```".format(attach.filename.split(".")[0]))

def setup(xyzzy):
    return Main(xyzzy)