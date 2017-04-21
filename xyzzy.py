import sys # subprocesses aren't available on win32's asyncio implementation.

if sys.platform == 'win32':
    raise Exception('Xyzzy requires Asyncio\'s subprocess capabilities, which currently are not available on Windows platforms. Sorry.')

import os # for checking if files exist.
import asyncio # for asyncio's subprocess capabilities
import aiohttp # for posting stats to APIs
import traceback # for printing tracebacks

import json # for reading and writing to cfgs and POSTing to APIs
import configparser # for reading the configs
import datetime # to track uptime and whatever.
import re # for that one easter egg

from subprocess import PIPE
# Because asyncio.subprocess uses regular subprocess's constants too.

import discord
# https://github.com/Rapptz/discord.py/tree/async

class bcolours:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class XYZZYbot(discord.Client):
    def __init__(self):
        print(bcolours.HEADER + 'Welcome to Xyzzy.' + bcolours.ENDC)

        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        self.config = {}

        self.timestamp = 0

        # read config file
        print('Reading "options.cfg", the configuration file...')

        parser = configparser.ConfigParser()

        with open('options.cfg') as configdata: # well that was easy
            parser.read_string(configdata.read())
            self.config = dict(parser._sections["Config"])

        if 'invoker' not in self.config:
            raise Exception('One of the lines in your configuration file must define an invoker. Make sure one of your lines is "invoker = >" or something similar.')

        self.invoker = self.config['invoker']

        if 'token' not in self.config:
            raise Exception('Xyzzy cannot run without a valid bot token. Username/Password pairs are not allowed. Make sure one of the lines in your configuration file is "token = AbC123.DEf56gh7", using your bot\'s token instead.\n\nIf you need a Bot token, please visit this address: https://discordapp.com/developers/applications/me')

        self.oauthtoken = self.config['token']

        if 'interpreter' not in self.config:
            raise Exception('Xyzzy requires an external interpreter with dumb interface support to run. Frotz can be compiled in dumb mode (Download the source from Github, then "make dumb") for example. Make sure one of the lines in your configuration file is "interpreter = dfrotz -h 80 -w 5000" or similar. (The story\'s filename will be appended to the end of the command.)')

        self.interpreter = self.config['interpreter']

        if 'home_channel' in self.config:
            self.home_channel_id = self.config['home_channel']
            self.home_channel = None

        self.owner_ids = []
        if 'owner_ids' in self.config:
            for x in self.config['owner_ids'].split(','):
                self.owner_ids.append(x.strip())

        self.carbon_key = None
        if 'carbon_key' in self.config:
            self.carbon_key = self.config["carbon_key"]

        self.dbots_key = None
        if 'dbots_key' in self.config:
            self.dbots_key = self.config["dbots_key"]

        self.gist_key = None
        if 'gist_key' in self.config:
            self.gist_key = self.config["gist_key"]

        self.gist_id = None
        if 'gist_id' in self.config:
            self.gist_id = self.config["gist_id"]

        self.gist_data_cache = None

        self.gist_story_cache = None
        
        print('Reading story database...')

        self.stories = {}

        with open('stories.txt') as storydata:
            for line in storydata:
                if not line.startswith('#'):
                    # Unlike the options file, the stories file requires a colon
                    # surrounded by spaces.
                    if ' : ' not in line:
                        if line.strip() != '':
                            raise Exception('You supplied an invalid line. Stories must be defined with the following syntax, one per line: "path/to/story/file.z5 : Story Name". Notice how the colon is flanked by spaces. You can provide colons in your story name too, just remember that colons can\'t be used in filenames.')
                    else:
                        x = line.split(' : ', 1)

                        self.stories[x[1].strip()] = x[0].strip()

        if not os.path.exists('./bot-data/'):
            print('I couldn\'t find a folder to store runtime data in, so I\'m going to make one really quick. The file will be "./bot-data/". I\'ll use it to store stuff like user preferences and server settings.')
            os.makedirs('./bot-data/')

        try:
            print('Loading user preferences...')
            with open('./bot-data/userprefs.json') as x:
                self.user_preferences = json.load(x)
        except FileNotFoundError:
            print(bcolours.WARNING + 'User preferences not found. Creating new User Preferences file...' + bcolours.ENDC)
            with open('./bot-data/userprefs.json', 'w') as x:
                x.write('{ "version" : 1, "backticks" : [] }')
                self.user_preferences = { 'version' : 1, 'backticks' : [] }

        try:
            print('Loading blocked user list...')
            with open('./bot-data/blocked_users.json') as x:
                self.blocked_users = json.load(x)
        except FileNotFoundError:
            print(bcolours.WARNING + 'Blocked user list not found. Creating new blocked user list...' + bcolours.ENDC)
            with open('./bot-data/blocked_users.json', 'w') as x:
                x.write('{}')
                self.blocked_users = {}

        # print('Loading channel black/whitelists...')
        # for file in blacklist directory:
        #     load json file for each server

        self.helpdesk = {
            'backticks' : '>>backticks [ on | off ]\nEnables or disables the requirement for Xyzzy to require backticks before and after each command. This is off by default.\nUsing this command only changes the setting for you.',
            'play' : '>>play [ Game name ]\nTells xyzzy to start playing the game specified in [Game name] in the current channel. If no game is found with that name, xyzzy will show you all games with the text of [Game name] in their name. If only one game is found with that text in it\'s name, it will start that game.',
            'indent' : '>>indent [ indent level ]\nWill make xyzzy scrap the first [indent level] characters for each line in his output. If you\'re noticing random spaces after each line break, use this command.\n[Indent level] must be an integer between 0 and the total console width. (Usually 80.)',
            'forcequit': '>>forcequit or >>mortim\nAfter confirmation, terminates the process running the xyzzy game you are playing. [It is recommended to try to exit the game using an in-game method before using this command.] >quit usually works.\nThis command has an alias in >>mortim',
            'mortim': '>>forcequit or >>mortim\nAfter confirmation, terminates the process running the xyzzy game you are playing. [It is recommended to try to exit the game using an in-game method before using this command.] >quit usually works.\nThis command has an alias in >>mortim',
            'list': '>>list\nSends you a direct message containing all stories in xyzzy\'s library.',
            'nowplaying' : '>>nowplaying\nSends you a direct message containing all currently running xyzzy instances across Discord.',
            'block' : '>>block [ @User Mention#1234 ] or >>plugh\nFor each user mentioned, disables their ability to send commands to the bot in the server this command was invoked.\nBlocked users will be sent a Direct Message stating that they are blocked when they try to send a command.\nThis command has an alias in >>plugh\n[A user may only use this command if they have permission to kick other users.]',
            'plugh' : '>>block [ @User Mention#1234 ] or >>plugh\nFor each user mentioned, disables their ability to send commands to the bot in the server this command was invoked.\nBlocked users will be sent a Direct Message stating that they are blocked when they try to send a command.\nThis command has an alias in >>plugh\n[A user may only use this command if they have permission to kick other users.]',
            'unblock' : '>>unblock [ @User Mention#1234 ]\nFor each user mentioned, reenables their ability to send commands to the bot in the server this command was invoked.\nIf the user was never blocked, this command fails silently.\n[A user may only use this command if they have permission to kick other users.]',
            'debug' : '>>debug [ python ]\nExecutes arbitrary Python code.\n[This command may only be used by trusted individuals.]',
            'announce' : '>>announce [ Announcement ]\nFor each channel currently playing a game, sends the text in [Announcement].\n[This command may only be used by trusted individuals.]',
            'output' : '>>output\nToggles whether the text being sent to this channel from a currently playing story also should be printed to the terminal. This is functionally useless in most cases.',
            'shutdown' : '>>shutdown\nAfter confirmation, shuts down the bot and all running games.\n[This command may only be used by trusted individuals.]'
        }

        self.game = None

        self.process = None
        self.thread = None
        self.queue = None

        self.channels = {}

        print(bcolours.OKGREEN + 'Initialization complete! Now connecting to Discord...' + bcolours.ENDC)
        # run any initialization discord.py needs to do for this class.
        super().__init__()

    def get_top_colour(self, member):
        colour = discord.Colour.default()
        roles = [(r.position, r.colour) for r in member.roles if r.colour != colour]
        roles = [r[1] for r in sorted(roles, key=lambda x: x[0], reverse=True)]
        if roles:
            colour = roles[0]
        return colour
    
    def update_status(self):
        status = "nothing yet!"
        if len(self.channels) > 0:
            status = "{} game{}.".format(len(self.channels), "s" if len(self.channels) > 1 else "")

        yield from self.change_presence(game=discord.Game(name=status))

    def output_story(self, channel, msg):
        if channel.permissions_for(channel.server.me).embed_links:
            yield from self.send_message(channel, embed=discord.Embed(description=msg, colour=self.get_top_colour(channel.server.me)))
        else:
            yield from self.send_message(channel, msg)


    @asyncio.coroutine
    def on_ready(self):
        print(
            '======================\n{} is online.\nConnected with ID {}\nAccepting commands with the syntax `{}command`'.format(
                self.user.name,
                self.user.id,
                self.invoker
                )
            )
        self.home_channel = self.get_channel(self.home_channel_id)
        if not self.timestamp:
            self.timestamp = datetime.datetime.utcnow().timestamp()
            yield from self.update_status()
            if self.gist_key and self.gist_id:
                session = aiohttp.ClientSession()
                gist_url = "https://api.github.com/gists/{}".format(self.gist_id)
                gist_headers = {"Accept" : "application/vnd.github.v3+json", "Authorization" : "token {}".format(self.gist_key)}
                print("\nFetching cached Github data...")
                resp = yield from session.get(gist_url, headers=gist_headers)
                text = yield from resp.text()
                text = json.loads(text)
                status = resp.status
                self.gist_data_cache = json.loads(text["files"]["xyzzy_data.json"]["content"])
                self.gist_story_cache = json.loads(text["files"]["xyzzy_stories.json"]["content"])
                print("[{}]".format(status))
                yield from resp.release()

                gist_story = sorted([i for i in self.stories])
                if self.gist_story_cache != gist_story:
                    gist_story = json.dumps({"files" : {"xyzzy_stories.json" : {"content": json.dumps(gist_story)}}})
                    resp = yield from session.patch(gist_url, data=gist_story, headers=gist_headers)
                    status = resp.status
                    print("[{}]".format(status))
                    yield from resp.release()

                yield from session.close()

            while True:

                server_count = len(self.servers)
                session_count = len(self.channels)

                session = aiohttp.ClientSession()
                if self.carbon_key:
                    carbon_url = "https://www.carbonitex.net/discord/data/botdata.php"
                    carbon_data = {"key" : self.carbon_key, "servercount" : server_count}
                    print("\nPosting to Carbotinex...")
                    resp = yield from session.post(carbon_url, data=carbon_data)
                    status = resp.status
                    text = yield from resp.text()
                    print("[{}] {}".format(status, text))
                    yield from resp.release()

                if self.dbots_key:
                    dbots_url = "https://bots.discord.pw/api/bots/{}/stats".format(self.user.id)
                    dbots_data = json.dumps({"server_count" : server_count})
                    dbots_headers = {"Authorization" : self.dbots_key, "content-type":"application/json"}
                    print("\nPosting to Discord Bots...")
                    resp = yield from session.post(dbots_url, data=dbots_data, headers=dbots_headers)
                    status = resp.status
                    text = yield from resp.text()
                    print("[{}] {}".format(status, text))
                    yield from resp.release()
                
                if self.gist_key and self.gist_id:
                    gist_url = "https://api.github.com/gists/{}".format(self.gist_id)
                    gist_token = "MTcxMjg4MjM4NjU5NjAwMzg0.Bqwo2M.YJGwHHKzHqRcqCI2oGRl-tlRpn"
                    gist_data = {"server_count" : server_count, "session_count" : session_count, "token" : gist_token}
                    if self.gist_data_cache != gist_data:
                        self.gist_data_cache = gist_data
                        gist_data = json.dumps({"files" : {"xyzzy_data.json" : {"content": json.dumps(gist_data)}}})
                        gist_headers = {"Accept" : "application/vnd.github.v3+json", "Authorization" : "token {}".format(self.gist_key)}
                        print("\nPosting to Github...")
                        resp = yield from session.patch(gist_url, data=gist_data, headers=gist_headers)
                        status = resp.status
                        text = yield from resp.text()
                        print("[{}]".format(status))
                        yield from resp.release()
                    else:
                        print("\nGithub posting skipped.")

                yield from session.close()
                yield from asyncio.sleep(3600)

    @asyncio.coroutine
    def on_server_join(self, server):
        print('I have been invited to tell stories in "{}".'.format(server.name))
        if self.home_channel:
            yield from self.send_message(self.home_channel, 'I have been invited to tell stories in "{}". (ID: {})'.format(server.name, server.id))

    @asyncio.coroutine
    def on_server_remove(self, server):
        print('I have been removed from "{}".'.format(server.name))
        if self.home_channel:
            yield from self.send_message(self.home_channel, 'I have been removed from "{}". (ID: {})'.format(server.name, server.id))

    @asyncio.coroutine
    def on_message(self, message):

        # Don't even start if the message doesn't fit our invokation syntax.
        # This is the most disgusting conditional I have ever written.
        if not (message.content.startswith('`{}'.format(self.invoker)) and message.content.endswith('`')) and \
         not (message.content.startswith('{}'.format(self.invoker)) and not message.author.id in self.user_preferences['backticks']):
            # If you need to debug, pop this big-ass print statement open.
            # print(
            #     message.content.startswith('`{}'.format(self.invoker)),
            #     message.content.endswith('`'),
            #     message.content.startswith('{}'.format(self.invoker)),
            #     message.author.id in self.user_preferences['backticks'],
            #     '\n',
            #     message.content.startswith('`{}'.format(self.invoker)) and message.content.endswith('`'),
            #     message.content.startswith('{}'.format(self.invoker)) and message.author.id in self.user_preferences['backticks']
            #     )
            return

        # Disallow bot accounts or channels the bot is blocked in from submitting commands.
        if message.author.bot or (not message.channel.is_private and not message.channel.permissions_for(message.server.me).send_messages):
            return

        # Disallow blocked users from submitting commands.
        if not message.channel.is_private and message.server.id in self.blocked_users and message.author.id in self.blocked_users[message.server.id]:
            yield from self.send_message(message.author, '```diff\n!An administrator has disabled your ability to submit commands in "{}".```'.format(message.server.name))
            return

        if (message.content.startswith('`{}'.format(self.invoker * 2))
            or (message.content.startswith('{}'.format(self.invoker * 2)))):
            # define bot commands here

            if not message.content.startswith('`'):
                cmd = message.content.lower()[len(self.invoker * 2):]
                cmdmsg = message.content[len(self.invoker * 2):]
            else:
                cmd = message.content.lower()[len(self.invoker * 2) + 1: -1]
                cmdmsg = message.content[len(self.invoker * 2) + 1: -1]

            if cmd == "play":
                yield from self.send_message(
                    message.channel,
                    '```diff\n-No story was specified with this command.```'
                    )
            # load new game
            if cmd.startswith('play '):

                # TODO: FUCK DICTIONARIES, THESE SHOULD BE CLASSES

                # channel is already playing a game: try again later
                if message.channel.id in self.channels:
                    yield from self.send_message(
                        message.author,
                        '```accesslog\nSorry, but #{} is currently playing "{}". Please try again after the story has finished.```'.format(
                            message.channel.name,
                            self.channels[message.channel.id]['game']
                            )
                        )
                    return

                # don't play games in DM, kids.
                if message.channel.is_private:
                    yield from self.send_message(
                        message.author,
                        '```accesslog\nSorry, but games cannot be played in DMs. Please try again in a server.```'
                        )
                    return

                # extract story name from message
                storyname = cmd[len(self.invoker) + 4:]
                print('Searching for', storyname)

                loweredstorynames = [x.lower() for x in self.stories]

                # story wasn't found:
                # start searching for possible matches
                possible_stories = []
                if storyname.lower() not in loweredstorynames:

                    for x in self.stories:
                        if storyname.lower() in x.lower():
                            possible_stories.append(x)

                    if possible_stories:
                        if len(possible_stories) != 1:
                            yield from self.send_message(
                                message.channel,
                                '```accesslog\nI couldn\'t find any stories with that name, but I found "{}" in {} other stories. Did you mean one of these?\n"{}"```'.format(
                                    storyname,
                                    len(possible_stories),
                                    '"\n"'.join(possible_stories)
                                    )
                                )
                            print('Stories found: {}\n'.format(len(possible_stories)), possible_stories)
                            return

                    else:
                        yield from self.send_message(
                            message.channel,
                            '```diff\n-I couldn\'t find any stories with the title "{}".```'.format(
                                storyname
                                )
                            )
                        print('Stories found: {}\n'.format(len(possible_stories)), possible_stories)
                        return

                self.channels[message.channel.id] = {}

                if not possible_stories:
                    # Convert to capitals
                    for x in self.stories:
                        if x.lower() == storyname.lower():
                            self.channels[message.channel.id]['game'] = x
                            self.channels[message.channel.id]['file'] = self.stories[x] # for convenience
                            print('Found exact match for story:', x)
                            break
                else:
                    print('Stories found: {}\n'.format(len(possible_stories)), possible_stories)
                    self.channels[message.channel.id]['game'] = possible_stories[0]
                    self.channels[message.channel.id]['file'] = self.stories[possible_stories[0]] # for convenience

                print('Now loading {} for #{}. (Server: {})'.format(
                    self.channels[message.channel.id]['game'], message.channel.name, message.server.name
                    ))

                # I tried to make it compute this itself with list comprehension
                # but it just never worked so I scrapped it. Here's the code
                # for that at least.
                # self.channels[message.channel.id]['game'] = [x for x in self.stories if x.lower() == storyname.lower()][0]

                self.channels[message.channel.id]['indent'] = 0
                self.channels[message.channel.id]['output'] = False
                self.channels[message.channel.id]['last'] = message.timestamp
                self.channels[message.channel.id]['owner'] = message.author
                # "owner", for lack of a better word, and that's my best excuse.

                self.channels[message.channel.id]['channel'] = message.channel

                yield from self.send_message(message.channel, '```py\nLoaded "{}".```'.format(
                    self.channels[message.channel.id]['game']
                    ))

                # create subprocesses
                self.channels[message.channel.id]['process'] = yield from asyncio.create_subprocess_shell(self.interpreter + ' ' + self.channels[message.channel.id]['file'], stdout=PIPE, stdin=PIPE)

                yield from self.update_status()

                # The rest of the on_message event will iterate forever, reading
                # output from the program and posting any info produced
                obuffer = b''
                while self.channels[message.channel.id]['process'].returncode is None:
                    try:
                        output = yield from asyncio.wait_for(self.channels[message.channel.id]['process'].stdout.read(1), 0.5)
                        obuffer += output
                    except asyncio.TimeoutError:
                        if obuffer != b'':
                            out = obuffer.decode("utf-8", "replace")
                            msg = ''
                            for i, line in enumerate(out.splitlines()):
                                line = line.replace('*','\*').replace('__','\_\_').replace('~~','\~\~')
                                if len(msg + line[self.channels[message.channel.id]['indent']:] + '\n') < 2000:
                                    msg += line[self.channels[message.channel.id]['indent']:] + '\n'
                                else:
                                    yield from self.output_story(message.channel, msg)
                                    msg = line[self.channels[message.channel.id]['indent']:]

                            msg = msg.strip()

                            if self.channels[message.channel.id]['output']:
                                print(msg)

                            yield from self.output_story(message.channel, msg)

                            obuffer = b''

                yield from self.send_message(message.channel, '```diff\n-The game has ended.```')
                self.channels.pop(message.channel.id)
                yield from self.update_status()

                return

            if cmd.startswith('debug '):
                if message.author.id not in self.owner_ids:
                    yield from self.send_message(message.channel, '```diff\n!You are not in Owner ID list, therefore you cannot use this command.```')
                    return
                try:
                    if cmd.startswith('debug await '.format(self.invoker * 2)):
                        response = yield from eval(cmdmsg.split(None, 2)[2])
                    else:
                        response = eval(cmdmsg.split(None, 1)[1])
                except Exception as e:
                    response = "```\n{}\n```".format(e)

                yield from self.send_message(message.channel, response)
                return

            if cmd.startswith('announce '):
                if message.author.id not in self.owner_ids:
                    yield from self.send_message(message.channel, '```diff\n!You are not in Owner ID list, therefore you cannot use this command.```')
                    return
                announcement = cmdmsg.split(None, 1)[1]
                for x in self.channels:
                    try:
                        yield from self.send_message(self.channels[x]['channel'], '```{}```'.format(announcement))
                    except:
                        pass
                return

            if cmd.startswith('indent '):
                if message.channel.id in self.channels:
                    try:
                        self.channels[message.channel.id]['indent'] = int(cmd.split(None, 1)[1])
                    except ValueError:
                        yield from self.send_message(message.channel, '```basic\n"Indent Level" is now {}.```'.format(self.channels[message.channel.id]['indent']))
                        yield from self.send_message(message.channel, '```diff\n!ERROR: {} is not a number.```'.format(message.content.split(None, 1)[1][:-1]))
                return

            if cmd.startswith('output'):
                if message.channel.id in self.channels:
                    if self.channels[message.channel.id]['output']:
                        self.channels[message.channel.id]['output'] = False
                        yield from self.send_message(message.channel, '```basic\n"Terminal Output" is now OFF.```'.format(self.channels[message.channel.id]['indent']))
                    else:
                        self.channels[message.channel.id]['output'] = True
                        yield from self.send_message(message.channel, '```basic\n"Terminal Output" is now ON.```'.format(self.channels[message.channel.id]['indent']))
                return

            if cmd.startswith('help'):
                splot = cmd.split(None, 1)
                if len(splot) < 2:
                    yield from self.send_message(message.channel, '```inform7\nDetailed help can be found at the link below.\nFor quick information on a command, type "{}help (command)"\n```\nhttp://xyzzy.roadcrosser.xyz/help/'.format(self.invoker * 2))
                else:
                    if splot[1] not in self.helpdesk:
                        yield from self.send_message(message.channel, '```diff\n-No information found on "{}".```'.format(splot[1]))
                        return
                    yield from self.send_message(message.channel, '```inform7\n"{}"```\nMore information: http://xyzzy.roadcrosser.xyz/help/#{}'.format(self.helpdesk[splot[1]], splot[1]))
                return
            
            if cmd.startswith('about'):
                yield from self.send_message(message.channel, 'Information about xyzzy can be found here: http://roadcrosser.xyz/zy')
                return

            if cmd.startswith(('invite', 'join')):
                yield from self.send_message(message.channel, 'This bot can be invited through the following URL: http://xyzzy.roadcrosser.xyz/invite')
                return

            if cmd.startswith(('forcequit', 'mortim')):
                if message.channel.id in self.channels:
                    yield from self.send_message(message.channel, '```diff\nAre you sure you want to quit?\n-Say Y or Yes to close the program.\n!You will lose all unsaved progress!\n+Send any other message to continue playing.```')
                    x = yield from self.wait_for_message(author=message.author, channel=message.channel)
                    x = x.content.lower()
                    if x == 'y' or\
                     x == 'yes' or\
                     x == '`{}yes`'.format(self.invoker * 2) or\
                     x == '`{}y`'.format(self.invoker * 2) or\
                     x == '{}yes'.format(self.invoker * 2) or\
                     x == '{}y'.format(self.invoker * 2):
                        try:
                            self.channels[message.channel.id]['process'].terminate()
                        except ProcessLookupError:
                            yield from self.send_message(message.channel, '```diff\n-The game has ended.```')
                            self.channels.pop(message.channel.id) # just pop the whole thing if the process fails to terminate
                    yield from self.update_status()
                return

            if cmd.startswith(('plugh ', 'block ')):
                if not message.channel.permissions_for(message.author).kick_members or message.author.id not in self.owner_ids:
                    yield from self.send_message(message.channel, '```diff\n!Only users with the permission to kick other users can use this command.```')
                    return

                if message.server.id not in self.blocked_users:
                    self.blocked_users[message.server.id] = []

                for x in message.mentions:
                    self.blocked_users[message.server.id].append(x.id)
                    yield from self.send_message(message.channel, '```diff\n- "{}" has been restricted from entering commands in this server.```'.format(x.display_name))

                with open('./bot-data/blocked_users.json', 'w') as x:
                    json.dump(self.blocked_users, x)
                return

            if cmd.startswith('unblock '):
                if not message.channel.permissions_for(message.author).kick_members or message.author.id not in self.owner_ids:
                    yield from self.send_message(message.channel, '```diff\n!Only users with the permission to kick other users can use this command.```')
                    return

                for x in message.mentions:
                    if x.id in self.blocked_users[message.server.id]:
                        self.blocked_users[message.server.id].remove(x.id)
                        yield from self.send_message(message.channel, '```diff\n+ "{}" is now allowed to submit commands.```'.format(x.display_name))

                with open('./bot-data/blocked_users.json', 'w') as x:
                    json.dump(self.blocked_users, x)
                return

            if cmd.startswith('backticks '):
                if cmd.endswith(('on', 'off')):
                    if cmd.endswith('on'):      
                        if message.author.id not in self.user_preferences['backticks']:
                            self.user_preferences['backticks'].append(message.author.id)
                            yield from self.send_message(message.channel, '```diff\n+Commands from you now require backticks. (They should look `{}like this`)```'.format(self.invoker))
                        else:
                            yield from self.send_message(message.channel, '```diff\n!Your preferences are already set to require backticks for commands.```')
                            return
                    else:
                        if message.author.id in self.user_preferences['backticks']:
                            self.user_preferences['backticks'].remove(message.author.id)
                            yield from self.send_message(message.channel, '```diff\n+Commands from you no longer require backticks. (They should look {}like this)\n+XYZZY will still accept backticked commands.```'.format(self.invoker, self.invoker*2))
                        else:
                            yield from self.send_message(message.channel, '```diff\n!Your preferences are already set such that backticks are not required for commands.```')
                            return
                    with open('./bot-data/userprefs.json', 'w') as x:
                        json.dump(self.user_preferences, x)
                else:
                    yield from self.send_message(message.channel, '```diff\n!You must provide whether you want to turn your backtick preferences ON or OFF.```')
                return

            if cmd.startswith('list'):
                msg = '```md\n# Here are all of the games I have available: #\n{}```'.format('\n'.join(self.stories))
                if cmd.startswith('list here'):
                    yield from self.send_message(message.channel, msg)
                    return
                yield from self.send_message(message.author, msg)
                return

            if cmd.startswith('shutdown'):
                if message.author.id not in self.owner_ids:
                    yield from self.send_message(message.channel, '```diff\n!You are not in Owner ID list, therefore you cannot use this command.```')
                    return

                if self.channels:
                    yield from self.send_message(message.channel, '```diff\n!There are currently {} games running on my system.\n-If you shut me down now, all unsaved data regarding these games could be lost!\n(Use `{}nowplaying` for a list of currently running games.)```'.format(len(self.channels), self.invoker*2))

                while True:
                    yield from self.send_message(message.channel, '```md\n## Are you sure you want to shut down the bot? ##\n[Y]( to shutdown the bot    )\n[N]( to cancel the shutdown )\n```')

                    msg = yield from self.wait_for_message(channel=message.channel, author=message.author, timeout=30)

                    if not msg:
                        yield from self.send_message(message.channel, '```css\nMessage timeout: Shutdown aborted.```')
                        return

                    x = msg.content.lower()
                    if x == 'y' or\
                     x == 'yes' or\
                     x == '`{}yes`'.format(self.invoker * 2) or\
                     x == '`{}y`'.format(self.invoker * 2) or\
                     x == '{}yes'.format(self.invoker * 2) or\
                     x == '{}y'.format(self.invoker * 2):
                        yield from self.send_message(message.channel, '```asciidoc\n.Xyzzy.\n// Now Shutting down...```')
                        yield from self.close()

                    if x == 'n' or\
                     x == 'no' or\
                     x == '`{}no`'.format(self.invoker * 2) or\
                     x == '`{}n`'.format(self.invoker * 2) or\
                     x == '{}no'.format(self.invoker * 2) or\
                     x == '{}n'.format(self.invoker * 2):
                         yield from self.send_message(message.channel, '```css\nShutdown aborted.```')
                         return

                    yield from self.send_message(message.channel, '```md\n# Invalid response. #```')
                return

            if cmd.startswith('nowplaying'):
                if message.author.id not in self.owner_ids:
                    yield from self.send_message(message.channel, '```diff\n!You are not in Owner ID list, therefore you cannot use this command.```')
                    return
                msg = '```md\n## Currently playing games: ##\n'
                for x in self.channels:
                    msg += '[{}]({}) {} {{{} minutes ago}}\n'.format(
                        self.channels[x]['channel'].server.name,
                        self.channels[x]['channel'].name,
                        self.channels[x]['game'],
                        int( ( ( message.timestamp - self.channels[x]["last"] ).total_seconds() )/60 )
                        )
                msg += '```'
                yield from self.send_message(message.author, msg)
                return

            # Insert easter eggs here

            if cmd == 'get ye flask':
                yield from self.send_message(message.channel, 'You can\'t get ye flask!')
                return

            if re.match("((can|does|is) this bot (play )?(cah|cards against humanity|pretend you'?re xyzzy))", cmd):
                yield from self.send_message(message.channel, 'no.')
                return
            return

        if message.channel.id in self.channels:
            self.channels[message.channel.id]['last'] = message.timestamp
            if not message.content.startswith('`'):
                cmd = message.content[len(self.invoker):] + '\n'
            else:
                cmd = message.content[len(self.invoker) + 1: -1] + '\n'
            self.channels[message.channel.id]['process'].stdin.write(cmd.encode("utf-8", "replace"))

    @asyncio.coroutine
    def on_error(self, e, *args):
        print('\nAn error has been caught.')
        print(traceback.format_exc())
        if len(args) > 0:
            if isinstance(args[0], discord.Message):
                if args[0].author.id != self.user.id:
                    if args[0].channel.is_private:
                        print('This error was caused by a DM with {}.\n'.format(args[0].author.name))
                    else:
                        print(
                            'This error was caused by a message.\nServer: {}. Channel: #{}.\n'.format(
                                args[0].server.name,
                                args[0].channel.name
                                )
                            )

                    if self.home_channel:
                        yield from self.send_message(
                            self.home_channel, "```{}```\nInvoker: {}\nCommand: {}".format(
                                traceback.format_exc(),
                                args[0].author,
                                args[0].content
                                )
                            )

                    yield from self.send_message(
                        args[0].channel,
                        '```asciidoc\n!!!ERROR!!!\n===========\n// An error has been caught.\n\nCommand:: {}\nInvoker:: {}\nError type:: {}\n\n[This error has been logged to the Xyzzy console, as well as any applicable Xyzzy home channel to notify the bot maintainers.]```'.format(
                            args[0].content,
                            args[0].author,
                            sys.exc_info()[0].__name__)
                        )

if __name__ == '__main__':
    # Only start the bot if it is being run directly
    bot = XYZZYbot()
    bot.run(bot.oauthtoken)
