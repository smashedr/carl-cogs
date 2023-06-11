[![Discord](https://img.shields.io/discord/899171661457293343?color=7289da&label=discord&logo=discord&logoColor=white&style=plastic)](https://discord.gg/wXy6m2X8wY)
[![Codacy grade](https://img.shields.io/codacy/grade/439cde1e5a5b4c649beca9b27ec108aa?logo=codacy&style=plastic)](https://app.codacy.com/gh/smashedr/carl-cogs/dashboard)
[![](https://repository-images.githubusercontent.com/422749366/a8e0e86a-fcdf-42f4-a5f8-63946c0cd272)](https://carl.sapps.me/)
# Carl-Cogs

Cogs for Carl Bot and Red Discord Bot.

[https://carl.sapps.me/](https://carl.sapps.me/)

### Installing

To add Carl Bot to your server visit: [https://carl.sapps.me/](https://carl.sapps.me/)

If you run a bot compatible with Red Cogs:

```text
[p]repo add carl-cogs https://github.com/smashedr/carl-cogs
[p]cog list carl-cogs
[p]cog install carl-cogs name
[p]load name
```

### Public Cogs

| Cog                                                    | Description                                                                     |
|--------------------------------------------------------|---------------------------------------------------------------------------------|
| **[activerole](activerole/activerole.py)**             | **Redis** - Adds a role to active chatters.                                     |
| **[asn](asn/asn.py)**                                  | **Redis** - Aviation Safety Network entries post to a channel or view manually. |
| **[autochannels](autochannels/autochannels.py)**       | Creates duplicate channels on the fly and cleans up when done.                  |
| **[autodisconnect](autodisconnect/autodisconnect.py)** | Automatically disconnects users from the AFK channel.                           |
| **[autoroles](autoroles/autoroles.py)**                | Adds roles to new members on join.                                              |
| **[avherald](avherald/avherald.py)**                   | **Redis** - Get and post AVHearld data to Discord.                              |
| **[botutils](botutils/botutils.py)**                   | Custom stateless bot utilities for Carl Bot but useful for anyone.              |
| **[chatgraph](chatgraph/chatgraph.py)**                | **API** - Generage Pie Graph of Messages in Current Channel.                    |
| **[colorme](colorme/colorme.py)**                      | Allow users to manage the color of their own name.                              |
| **[dayinhistory](dayinhistory/dayinhistory.py)**       | **Redis** - Gets and Posts Today in History.                                    |
| **[dictionary](dictionary/dictionary.py)**             | Dictionary and Urban Dictionary lookups.                                        |
| **[flightaware](flightaware/flightaware.py)**          | **Redis** - FlightAware Flights, Operators, Registration.                       |
| **[heartbeat](heartbeat/heartbeat.py)**                | Pings a Heartbeat service every X seconds.                                      |
| **[liverole](liverole/liverole.py)**                   | Give a role to users when they go live in Discord.                              |
| **[lmgtfy](lmgtfy/lmgtfy.py)**                         | LMGTFY chat replies.                                                            |
| **[openai](openai/openai.py)**                         | **Redis** - OpenAI and ChatGPT Commands.                                        |
| **[reactpost](reactpost/reactpost.py)**                | Set channels to auto add Emoji->Channels mappings to post to channel on react.  |
| **[stickyroles](stickyroles/stickyroles.py)**          | Remembers users roles and adds them on rejoin.                                  |
| **[userchannels](userchannels/userchannels.py)**       | Creates custom user rooms on the fly and cleans up when done.                   |
| **[voicetext](voicetext/voicetext.py)**                | **WIP** - Creates Text Channels for Active Voice Channels and Cleans Up.        |
| **[warcraftlogs](warcraftlogs/warcraftlogs.py)**       | Split Warcraft Logs into multiple channels with filters.                        |
| **[welcome](welcome/welcome.py)**                      | Welcomes new users to your servers on join.                                     |

### Internal/Hidden Cogs

| Cog                                              | Description                                                                |
|--------------------------------------------------|----------------------------------------------------------------------------|
| **[captcha](captcha/captcha.py)**                | **API** - Protect server with CAPTCHA.                                     |
| **[carlcog](carlcog/carlcog.py)**                | Custom commands for Carl Bot that could end up in their own module.        |
| **[createthings](createthings/createthings.py)** | **WIP** - Create pre-defined or user-defined role/emoji sets.              |
| **[miscog](miscog/miscog.py)**                   | Miscellaneous commands for Carl Bot that could end up in their own module. |
| **[pubsub](pubsub/pubsub.py)**                   | **API, Redis** - Custom Redis pubsub module for Red and Carl Bot.          |
| **[youtube](youtube/youtube.py)**                | **WIP** - Auto post YouTube videos to specified channels.                  |

# Additional Setup Information

## Redis

Many Cogs use Redis for data caching and setting expiry keys.  
Redis has a small footprint and is very fast.  
Running the docker Redis container will work with these cogs out of the box.  
To configure specific Redis settings, use the `set api` command.  

### Running Redis

```text
docker run --name redis -p 6379:6379 -d redis:alpine
```

### Configure Redis

```text
[p]set api
```

Name: `redis`  
Data:
```text
host    redis
port    6379
db      0
pass    onlyifrequired
```

Above information are the defaults. Password defaults to `None`.
DO NOT enter a password in the config unless you require one.

## API

**Coming Soon.** New API will be posted soon.
