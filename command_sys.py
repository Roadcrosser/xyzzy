"""
Totally not "stolen" from Amethyst and stripped down.
"""

from typing import Callable, List, Union, Tuple
from random import randint
import discord
import inspect
import re
import sys
import importlib
import shlex

PERMS = [x for x in dir(discord.Permissions) if not x.startswith(("_", "is")) and x not in ("value", "all", "all_channel", "none", "general", "text", "voice", "update")]

class Context:
    """
    Custom object that get's passed to commands.
    Not intended to be created manually.
    """
    def __init__(self, msg: discord.Message, xyzzy: discord.Client):
        self.msg = msg
        self.client = xyzzy
        self.clean = (msg.content[1:-1] if xyzzy.content_regex.match(msg.content) else msg.content)[2:]
        self.cmd = self.clean.split(" ")[0]
        self.args = shlex.split(self.clean.replace(r'\"', "\u009E").replace("'", "\u009F")) # Shlex doesn't obey escaped quotes, so lets do it ourselves.
        self.args = [x.replace("\u009E", '"').replace("\u009F", "'") for x in self.args][1:]
        self.raw = self.clean.split(" ", 1)[1]

    async def _send(self, content, dest, *, embed=None, file=None, files=None):
        """Internal send function, not actually ment to be used by anyone."""
        if dest == "channel":
            return await self.msg.channel.send(content, embed=embed, file=file, files=files)
        elif dest == "author":
            return await self.msg.author.send(content, embed=embed, file=file, files=files)
        else:
            raise ValueError("Destination is not `channel` or `author`.")

    async def send(self, content: str=None, *, dest: str="channel", embed: discord.Embed=None, file: discord.File=None, files: List[discord.File]=None):
        """Sends a message to the context origin, can either be the channel or author."""
        if content is None and not embed and not file and not files:
            content = "```ERROR at memory location {}\n  No content.\n```".format(hex(randint(2 ** 4, 2 ** 32)))
        elif content:
            # Escape bad mentions
            content = str(content).replace("@everyone", "@\u200Beveryone").replace("@here", "@\u200Bhere")

        msg = await self._send(content, dest, embed=embed, file=file, files=files)

        return msg

    def is_dm(self):
        """Check if the channel for the context is a DM or not."""
        return isinstance(self.msg.channel, discord.DMChannel)

    def has_permission(self, permission, who="self"):
        """Check if someone in context has a permission."""
        if who not in ["self", "author"]:
            raise ValueError("Invalid value for `who` (must be `self` or `author`).")

        if permission not in PERMS:
            return False

        if who == "self":
            return getattr(self.msg.channel.permissions_for(self.msg.guild.me), permission)
        elif who == "author":
            return getattr(self.msg.channel.permissions_for(self.msg.author), permission)

    def typing(self):
        """d.py `async with` shortcut for sending typing to a channel."""
        return self.msg.channel.typing()


class Command:
    """Represents a command."""
    def __init__(self, func: Callable[..., None], *, name: str=None, description: str="", aliases: list=[], usage: str="", owner: bool=False, has_site_help: bool=True):
        self.func = func
        self.name = name or func.__name__
        self.description = description or inspect.cleandoc(func.__doc__ or "")
        self.aliases = aliases or []
        self.cls = None
        self.usage = usage
        self.owner = owner
        self.has_site_help = has_site_help

    def __repr__(self) -> str:
        return self.name

    async def run(self, ctx: Context) -> None:
        if self.owner and str(ctx.msg.author.id) not in ctx.client.owner_ids:
            await ctx.send("```ERROR at memory location {}\n  Access denied.```".format(hex(randint(2 ** 4, 2 ** 32))))
        else:
            await self.func(self.cls, ctx)


class Holder:
    """Object that holds commands and aliases, as well as managing the loading and unloading of modules."""
    def __init__(self, xyzzy):
        self.commands = {}
        self.aliases = {}
        self.modules = {}
        self.xyzzy = xyzzy

    def __len__(self):
        return len(self.commands)

    def __contains__(self, x: str) -> bool:
        return x in self.commands

    def load_module(self, module_name: str) -> None:
        """Loads a module by name, and registers all its commands."""
        if module_name in self.modules:
            raise Exception(f"Module `{module_name}` is already loaded.")

        module = importlib.import_module(module_name)

        # Check if module has needed function
        try:
            module.setup
        except AttributeError:
            del sys.modules[module_name]
            raise Exception("Module does not have a `setup` function.")

        # Get class returned from setup.
        module = module.setup(self.xyzzy)
        # Filter all class methods to only commands and those that do not have a parent (subcommands).
        cmds = [x for x in dir(module) if not re.match("__?.*(?:__)?", x) and isinstance(getattr(module, x), Command)]
        loaded_cmds = []
        loaded_aliases = []

        if not cmds:
            del sys.modules[module_name]
            raise ValueError("Module is empty.")

        for cmd in cmds:
            # Get command from name
            cmd = getattr(module, cmd)

            # Ingore any non-commands if they got through, and subcommands
            if not isinstance(cmd, Command):
                continue

            # Give the command its parent class because it got ripped out.
            cmd.cls = module
            self.commands[cmd.name] = cmd

            # Load aliases for the command
            for alias in cmd.aliases:
                self.aliases[alias] = self.commands[cmd.name]
                loaded_aliases.append(alias)

            loaded_cmds.append(cmd.name)

        self.modules[module_name] = loaded_cmds + loaded_aliases

    def reload_module(self, module_name: str) -> None:
        """Reloads a module by name, and all its commands."""
        if module_name not in self.modules:
            self.load_module(module_name)
            return

        self.unload_module(module_name)
        self.load_module(module_name)

    def unload_module(self, module_name: str) -> None:
        """Unloads a module by name, and unregisters all its commands."""
        if module_name not in self.modules:
            raise Exception(f"Module `{module_name}` is not loaded.")

        # Walk through the commands and remove them from the command and aliases dicts
        for cmd in self.modules[module_name]:
            if cmd in self.aliases:
                del self.aliases[cmd]
            elif cmd in self.commands:
                del self.commands[cmd]

        # Remove from self module array, and delete cache.
        del self.modules[module_name]
        del sys.modules[module_name]

    def get_command(self, cmd_name: str) -> Union[Command, None]:
        """Easily get a command via its name or alias"""
        return self.aliases[cmd_name] if cmd_name in self.aliases else self.commands[cmd_name] if cmd_name in self.commands else None

    async def run(self, ctx: Context) -> None:
        cmd = self.get_command(ctx.cmd)

        if not cmd:
            return

        await cmd.run(ctx)

    @property
    def all_commands(self) -> List[str]:
        return sorted(self.commands.keys())

    @property
    def all_aliases(self) -> List[str]:
        return sorted(self.aliases.keys())

    @property
    def all_modules(self) -> List[str]:
        return sorted(self.modules.keys())


# Command conversion decorator
def command(**attrs):
    """Decorator which converts a function into a command."""
    def decorator(func):
        if isinstance(func, Command):
            raise TypeError("Function is already a command.")

        if not inspect.iscoroutinefunction(func):
            raise TypeError("Command function isn't a coroutine.")

        return Command(func, **attrs)

    return decorator