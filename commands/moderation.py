from command_sys import command
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
            await ctx.send('```diff\n- "{}" has been restricted from entering commands in this server.\n```'.format(men.display_name))

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

def setup(xyzzy):
    return Moderation(xyzzy)