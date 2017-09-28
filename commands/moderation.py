from modules.command_sys import command
import json

class Moderation:
    def __init__(self, xyzzy):
        self.xyzzy = xyzzy

    @command(aliases=["plugh"], usage="[ @User Mention#1234 ]")
    async def block(self, ctx):
        """
        For each user mentioned, disables their ability to send commands to the bot in the server this command was invoked.
        Blocked users will be sent a Direct Message stating that they are blocked when they try to send a command.
        This command has an alias in >>plugh
        [A user may only use this command if they have permission to kick other users.]
        """
        if not ctx.has_permission("kick_members", "author") and str(ctx.msg.author.id) not in self.xyzzy.owner_ids:
            return await ctx.send("```diff\n!Only users with the permission to kick other users can use this command.\n```")

        if not ctx.msg.mentions:
            return await ctx.send("```diff\n-Please mention some people to block.\n```")

        if str(ctx.msg.guild.id) not in self.xyzzy.blocked_users:
            self.xyzzy.blocked_users[str(ctx.msg.guild.id)] = []

        for men in ctx.msg.mentions:
            self.xyzzy.blocked_users[str(ctx.msg.guild.id)].append(str(men.id))
            await ctx.send('```diff\n+ "{}" has been restricted from entering commands in this server.\n```'.format(men.display_name))

        with open("./bot-data/blocked_users.json", "w") as blck:
            json.dump(self.xyzzy.blocked_users, blck)

    @command(usage="[ @User Mention#1234s ]")
    async def unblock(self, ctx):
        """
        For each user mentioned, re-enables their ability to send commands to the bot in the server this command was invoked.
        If the user was never blocked, this command fails silently.
        [A user may only use this command if they have permission to kick other users.]
        """
        if not ctx.has_permission("kick_members", "author") and str(ctx.msg.author.id) not in self.xyzzy.owner_ids:
            return await ctx.send("```diff\n!Only users with the permission to kick other users can use this command.\n```")

        if not ctx.msg.mentions:
            return await ctx.send("```diff\n-Please mention some people to unblock.\n```")

        if str(ctx.msg.guild.id) not in self.xyzzy.blocked_users:
            self.xyzzy.blocked_users[str(ctx.msg.guild.id)] = []
            return

        for men in ctx.msg.mentions:
            if str(men.id) in self.xyzzy.blocked_users[str(ctx.msg.guild.id)]:
                self.xyzzy.blocked_users[str(ctx.msg.guild.id)].remove(str(men.id))
                await ctx.send('```diff\n+ "{}" is now allowed to submit commands.\n```'.format(men.display_name))

        with open("./bot-data/blocked_users.json", "w") as blck:
            json.dump(self.xyzzy.blocked_users, blck)

    @command(usage="[ Game name ] or list")
    async def blockgame(self, ctx):
        """
        Stops the game specified in [game name] being played on the server.
        If "list" is specified as the game name, then a list of all the currently blocked games will be shown.
        [A user may only use this command if they can manage the server.]
        """
        if not ctx.has_permission("manage_guild", "author") and str(ctx.msg.author.id) not in self.xyzzy.owner_ids:
            return await ctx.send("```diff\n!Only users who can manage the server can use this command.\n```")

        if not ctx.args:
            return await ctx.send("```diff\n-Please specify a game to block for the server.\n```")

        if ctx.args[0].lower() == "list":
            if str(ctx.msg.guild.id) not in self.xyzzy.server_settings or not self.xyzzy.server_settings[str(ctx.msg.guild.id)]["blocked_games"]:
                return await ctx.send("```diff\n+No blocked games.\n```")
            else:
                games = self.xyzzy.server_settings[str(ctx.msg.guild.id)]["blocked_games"]

                return await ctx.send("```asciidoc\n.Blocked Games.\n{}\n```".format("\n".join("* '{}'".format(x) for x in sorted(games))))

        stories = {x: y for x, y in self.xyzzy.games.items() if ctx.raw.lower() in x.lower() or [z for z in y.aliases if ctx.raw.lower() in z.lower()]}
        perfect_match = None

        if stories:
            perfect_match = {x: y for x, y in stories.items() if ctx.raw.lower() == x.lower() or [z for z in y.aliases if ctx.raw.lower() == z.lower()]}

        if not stories:
            return await ctx.send('```diff\n-I couldn\'t find any games matching "{}"\n```'.format(ctx.raw))
        elif len(stories) > 1 and not perfect_match:
            return await ctx.send("```accesslog\n"
                                  'I couldn\'t find any games with that name, but I found "{}" in {} other games. Did you mean one of these?\n'
                                  '"{}"\n'
                                  "```".format(ctx.raw, len(stories), '"\n"'.join(sorted(stories))))

        if perfect_match:
            game = list(perfect_match.items())[0][0]
        else:
            game = list(stories[0].items())[0][0]

        if str(ctx.msg.guild.id) not in self.xyzzy.server_settings:
            self.xyzzy.server_settings[str(ctx.msg.guild.id)] = {"blocked_games": [game]}
        else:
            if game not in self.xyzzy.server_settings[str(ctx.msg.guild.id)]["blocked_games"]:
                self.xyzzy.server_settings[str(ctx.msg.guild.id)]["blocked_games"].append(game)
            else:
                return await ctx.send('```diff\n- "{}" has already been blocked on this server.\n```'.format(game))

        await ctx.send('```diff\n+ "{}" has been blocked and will no longer be able to be played on this server.\n```'.format(game))

        with open("./bot-data/server_settings.json", "w") as srv:
            json.dump(self.xyzzy.server_settings, srv)

    @command(usage="[ Game name ]")
    async def unblockgame(self, ctx):
        """
        Re-allows a previously blocked game to be played again.
        [A user may only use this command if can manage the server.]
        """
        if not ctx.has_permission("manage_guild", "author") and str(ctx.msg.author.id) not in self.xyzzy.owner_ids:
            return await ctx.send("```diff\n!Only users who can manage the server can use this command.\n```")

        if not ctx.args:
            return await ctx.send("```diff\n-Please specify a game to unblock.\n```")

        stories = {x: y for x, y in self.xyzzy.games.items() if ctx.raw.lower() in x.lower() or [z for z in y.aliases if ctx.raw.lower() in z.lower()]}
        perfect_match = None

        if stories:
            perfect_match = {x: y for x, y in stories.items() if ctx.raw.lower() == x.lower() or [z for z in y.aliases if ctx.raw.lower() == z.lower()]}

        if not stories:
            return await ctx.send('```diff\n-I couldn\'t find any games matching "{}"\n```'.format(ctx.raw))
        elif len(stories) > 1 and not perfect_match:
            return await ctx.send("```accesslog\n"
                                  'I couldn\'t find any games with that name, but I found "{}" in {} other games. Did you mean one of these?\n'
                                  '"{}"\n'
                                  "```".format(ctx.raw, len(stories), "\n".join(sorted(stories))))

        if perfect_match:
            game = list(perfect_match.items())[0][0]
        else:
            game = list(stories[0].items())[0][0]

        if str(ctx.msg.guild.id) not in self.xyzzy.server_settings:
            self.xyzzy.server_settings[str(ctx.msg.guild.id)] = {"blocked_games": [game]}
            return await ctx.send('```diff\n-No games have been blocked on this server.\n```')

        if game in self.xyzzy.server_settings[str(ctx.msg.guild.id)]["blocked_games"]:
            self.xyzzy.server_settings[str(ctx.msg.guild.id)]["blocked_games"].remove(game)
        else:
            return await ctx.send('```diff\n- "{}" has not been blocked on this server.\n```'.format(game))

        await ctx.send('```diff\n+ "{}" has been unblocked and can be played again on this server.\n```'.format(game))

        with open("./bot-data/server_settings.json", "w") as srv:
            json.dump(self.xyzzy.server_settings, srv)

def setup(xyzzy):
    return Moderation(xyzzy)