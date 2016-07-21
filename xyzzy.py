import sys # subprocesses aren't available on win32's asyncio implementation.

if sys.platform == 'win32':
    raise Exception('Xyzzy requires Asyncio\'s subprocess capabilities, which currently are not available on Windows platforms. Sorry.')

import os.path # for checking if files exist.
import asyncio # for asyncio's subprocess capabilities

import json # for reading and writing to cfgs

from subprocess import PIPE
# Because asyncio.subprocess uses regular subprocess's constants too.

import discord
# https://github.com/Rapptz/discord.py/tree/async

class XYZZYbot(discord.Client):
    def __init__(self):
        os.chdir(os.path.dirname(os.path.realpath(__file__)))

        self.config = {}

        # read config file
        print('Reading "options.cfg", the configuration file...')

        with open('options.cfg') as configdata:
            for line in configdata:
                if not line.startswith('#'):
                    # Like Python, our comments start with #.
                    if '=' not in line:
                        if line.strip() != '':
                            raise Exception('I found a line that didn\'t have an equals sign in it. You should start comments with a number sign (#) so I know not to read them like configuration commands.')
                    else:
                        # Split the line where the first = occurs and save it as
                        # key/string pairs in the dictionary.
                        x = line.split('=', 1)

                        self.config[x[0].strip()] = x[1].strip()

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

        if os.path.exists('./bot-data/'):
            print('Loading user preferences...')
            with open('./bot-data/userprefs.json') as x:
                self.user_preferences = json.load(x)
        else:
            print('I couldn\'t find a folder to store runtime data in, so I\'m going to make one really quick. The file will be "./bot-data/". I\'ll use it to store stuff like user preferences and server settings.')
            print('Writing user preferences...')
            os.makedirs('./bot-data/')
            with open('./bot-data/userprefs.json', 'w') as x:
                x.write('{ "version" : 1, "backticks" : [] }')
                self.user_preferences = { 'version' : 1, 'backticks' : [] }

        self.game = None

        self.process = None
        self.thread = None
        self.queue = None

        self.channels = {}

        # run any initialization discord.py needs to do for this class.
        super().__init__()

    @asyncio.coroutine
    def on_ready(self):
        print(
            '======================\n{} is online.\nConnected with ID {}\nAccepting commands with the syntax `{}command`'.format(
                self.user.name,
                self.user.id,
                self.invoker
                )
            )
        self.home_channel = discord.utils.get(self.servers, id=self.home_channel_id)

    @asyncio.coroutine
    def on_server_join(self, server):
        print('I have been invited to tell stories in "{}".'.format(server.name))
        if self.home_channel:
            self.send_message(self.home_channel, 'I have been invited to tell stories in "{}".'.format(server.name))

    @asyncio.coroutine
    def on_server_remove(self, server):
        print('I have been removed from "{}".'.format(server.name))
        if self.home_channel:
            self.send_message(self.home_channel, 'I have been removed from "{}".'.format(server.name))


    @asyncio.coroutine
    def on_message(self, message):

        # Don't even start if the message doesn't fit our invokation syntax.
        # This is the most disgusting conditional I have ever written.
        if not (message.content.startswith('`{}'.format(self.invoker)) and message.content.endswith('`')) and \
         not (message.content.startswith('{}'.format(self.invoker)) and message.author.id in self.user_preferences['backticks']):
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

        # Disallow bot accounts from submitting commands.
        if message.author.bot:
            return

        if message.content.startswith(
            '`{}'.format(self.invoker * 2)
            ) or (message.content.startswith(
                '{}'.format(self.invoker * 2)
                ) and message.author.id in self.user_preferences['backticks']
            ):
            # define bot commands here

            if not message.content.startswith('`'):
                cmd = message.content.lower()[len(self.invoker * 2):]
            else:
                cmd = message.content.lower()[len(self.invoker * 2) + 1: -1]

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
                self.channels[message.channel.id]['owner'] = message.author
                # "owner", for lack of a better word, and that's my best excuse.

                self.channels[message.channel.id]['channelname'] = message.channel.name
                self.channels[message.channel.id]['servername'] = message.server.name

                yield from self.send_message(message.channel, '```py\nLoaded "{}".```'.format(
                    self.channels[message.channel.id]['game']
                    ))

                # create subprocesses
                self.channels[message.channel.id]['process'] = yield from asyncio.create_subprocess_shell(self.interpreter + ' ' + self.channels[message.channel.id]['file'], stdout=PIPE, stdin=PIPE)

                # The rest of the on_message event will iterate forever, reading
                # output from the program and posting any info produced
                obuffer = b''
                while self.channels[message.channel.id]['process'].returncode is None:
                    try:
                        output = yield from asyncio.wait_for(self.channels[message.channel.id]['process'].stdout.read(1), 0.5)
                        obuffer += output
                    except asyncio.TimeoutError:
                        if obuffer != b'':
                            out = obuffer.decode('utf-8')
                            msg = ''
                            for line in out.splitlines():
                                if len(msg + line[self.channels[message.channel.id]['indent']:] + '\n') < 2000:
                                    msg += line[self.channels[message.channel.id]['indent']:] + '\n'
                                else:
                                    yield from self.send_message(message.channel, msg)
                                    msg = line[self.channels[message.channel.id]['indent']:]

                            msg = msg.strip()

                            if self.channels[message.channel.id]['output']:
                                print(msg)

                            yield from self.send_message(message.channel, msg)

                            obuffer = b''

                yield from self.send_message(message.channel, '```diff\n-The game has ended.```')
                self.channels.pop(message.channel.id)

                return

            if cmd.startswith('debug '):
                if message.author.id not in self.owner_ids:
                    yield from self.send_message(message.channel, '```diff\n!You are not in Owner ID list, therefore you cannot use this command.')
                    return
                if cmd.startswith('debug await '.format(self.invoker * 2)):
                    response = yield from eval(cmd.split(None, 2)[2])
                    yield from self.send_message(message.channel, response)
                    return

                yield from self.send_message(message.channel, eval(cmd.split(None, 1)[1]))
                return

            if cmd.startswith('indent '):
                if message.channel.id in self.channels:
                    try:
                        self.channels[message.channel.id]['indent'] = int(cmd.split(None, 1)[1])
                        yield from self.send_message(message.channel, '```xl\nIndent Level is now "{}".```'.format(self.channels[message.channel.id]['indent']))
                    except ValueError:
                        yield from self.send_message(message.channel, '```diff\n!ERROR: {} is not a number.```'.format(message.content.split(None, 1)[1][:-1]))

            if cmd.startswith('output'):
                if message.channel.id in self.channels:
                    if self.channels[message.channel.id]['output']:
                        self.channels[message.channel.id]['output'] = False
                        yield from self.send_message(message.channel, '```xl\nTerminal Output is now OFF.```'.format(self.channels[message.channel.id]['indent']))
                    else:
                        self.channels[message.channel.id]['output'] = True
                        yield from self.send_message(message.channel, '```xl\nTerminal Output is now ON.```'.format(self.channels[message.channel.id]['indent']))
                return

            if cmd.startswith('forcequit') or cmd.startswith('mortim'):
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
                        self.channels[message.channel.id]['process'].terminate()

            if cmd.startswith('backticks '):
                if cmd.endswith('on') or cmd.endswith('off'):
                    if cmd.endswith('on'):
                        if message.author.id in self.user_preferences['backticks']:
                            self.user_preferences['backticks'].remove(message.author.id)
                            yield from self.send_message(message.channel, '```diff\n+Commands from you now require backticks. (They should look `{}like this`)```'.format(self.invoker))
                        else:
                            yield from self.send_message(message.channel, '```diff\n!Your preferences are already set to require backticks for commands.')
                            return
                    else:
                        if message.author.id not in self.user_preferences['backticks']:
                            self.user_preferences['backticks'].append(message.author.id)
                            yield from self.send_message(message.channel, '```diff\n+Commands from you no longer require backticks. (They should look {}like this)\n+XYZZY will still accept backticked commands in case you forget you set this option.```'.format(self.invoker, self.invoker*2))
                        else:
                            yield from self.send_message(message.channel, '```diff\n!Your preferences are already set such that backticks are not required for commands.')
                            return
                    with open('./bot-data/userprefs.json', 'w') as x:
                        json.dump(self.user_preferences, x)
                else:
                    yield from self.send_messages(message.channel, '```diff\n!You must provide whether you want to turn your backtick preferences ON or OFF.')
            if cmd.startswith('nowplaying'):
                msg = '```md\n## Currently playing games: ##\n'
                for x in self.channels:
                    msg += '[{}]({}) {}\n'.format(self.channels[x]['servername'],self.channels[x]['channelname'],self.channels[x]['game'])
                msg += '```'
                yield from self.send_message(message.author, msg)

            return

        if message.channel.id in self.channels:
            if message.author.id in self.user_preferences['backticks']:
                cmd = message.content[len(self.invoker):] + '\n'
            else:
                cmd = message.content[len(self.invoker) + 1:-1] + '\n'
            self.channels[message.channel.id]['process'].stdin.write(cmd.encode('utf-8'))

if __name__ == '__main__':
    # Only start the bot if it is being run directly
    bot = XYZZYbot()
    bot.run(bot.oauthtoken)
