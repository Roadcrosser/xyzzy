from command_sys import command
import inspect

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
            'message": ctx.msg
        }

        out = eval(ctx.clean.split(' ', 1)[1], env)

        if inspect.isawaitable(out):
            out = await out

        await ctx.send("```py\n{}\n```".format(out))

def setup(xyzzy):
    return Owner(xyzzy)