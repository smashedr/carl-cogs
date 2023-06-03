[![Discord](https://img.shields.io/discord/899171661457293343?color=7289da&label=discord&logo=discord&logoColor=white&style=plastic)](https://discord.gg/wXy6m2X8wY)
[![Codacy grade](https://img.shields.io/codacy/grade/439cde1e5a5b4c649beca9b27ec108aa?logo=codacy&style=plastic)](https://app.codacy.com/gh/smashedr/carl-cogs/dashboard)
[![](https://repository-images.githubusercontent.com/422749366/a8e0e86a-fcdf-42f4-a5f8-63946c0cd272)](https://carl.sapps.me/)
# Carl-Cogs

Cogs for Carl Bot.

[https://carl.sapps.me/](https://carl.sapps.me/)

### Installing

To add Carl Bot to your server visit: [https://carl.sapps.me/](https://carl.sapps.me/)

If you run a bot compatible with Red Cogs:

```
[p]repo add carl-cogs https://github.com/smashedr/carl-cogs
[p]cog list carl-cogs
[p]cog install carl-cogs <cog-name>
```

### Public Cogs

| Cog                                                    | Description                                                                    |
|--------------------------------------------------------|--------------------------------------------------------------------------------|
| **[asn](asn/asn.py)**                                  | **Redis**. Aviation Safety Network entries post to a channel or view manually. |
| **[autochannels](autochannels/autochannels.py)**       | Creates duplicate channels on the fly and cleans up when done.                 |
| **[autodisconnect](autodisconnect/autodisconnect.py)** | Automatically disconnects users from the AFK channel.                          |
| **[autoroles](autoroles/autoroles.py)**                | Adds roles to new members on join.                                             |
| **[botutils](botutils/botutils.py)**                   | Custom stateless bot utilities for Carl Bot but useful for anyone.             |
| **[dayinhistory](dayinhistory/dayinhistory.py)**       | **Redis**. This Day in History post to a channel or view manually.             |
| **[dictionary](dictionary/dictionary.py)**             | Dictionary and Urban Dictionary lookups.                                       |
| **[liverole](liverole/liverole.py)**                   | Give a role to users when they go live in Discord.                             |
| **[openai](openai/openai.py)**                         | **Redis**. Query OpenAI/ChatGPT and query off others previous questions.       |
| **[stickyroles](stickyroles/stickyroles.py)**          | Remembers users roles and adds them on rejoin.                                 |
| **[userchannels](userchannels/userchannels.py)**       | Creates custom user rooms on the fly and cleans up when done.                  |
| **[voicetext](voicetext/voicetext.py)**                | Automatically creates Text channels for occupied Voice Channels.               |
| **[warcraftlogs](warcraftlogs/warcraftlogs.py)**       | Split Warcraft Logs into multiple channels with filters.                       |
| **[welcome](welcome/welcome.py)**                      | Welcomes new users to your servers on join.                                    |

### Internal/Hidden Cogs

| Cog                                              | Description                                                                                                 |
|--------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| **[activerole](activerole/activerole.py)**       | **Redis**. Adds a role to active chatters.                                                                  |
| **[captcha](captcha/captcha.py)**                | **API**. Protect Server with Human Verification for new members.                                            |
| **[carlcog](carlcog/carlcog.py)**                | **Custom**. Cog for Carl, has useful functions but may not stay here.                                       |
| **[createthings](createthings/createthings.py)** | **WIP**. Create pre-defined role and emoji sets.                                                            |
| **[miscog](miscog/miscog.py)**                   | **Custom**. Miscellaneous Cog with specific and heavy commands.                                             |
| **[heartbeat](heartbeat/heartbeat.py)**          | **WIP**. Sends a ping to a heartbeat service.                                                               |
| **[lmgtfy](lmgtfy/lmgtfy.py)**                   | **WIP**. Replies to the last query in chat with a real google link.                                         |
| **[pubsub](pubsub/pubsub.py)**                   | **Custom**. Redis Pub/Sub for Carl Bot and Carl's website.                                                  |
| **[reactroles](reactroles/reactroles.py)**       | **Deprecated**. Recommended Alternative: [Trusty-cogs/roletools](https://github.com/TrustyJAID/Trusty-cogs) |

# Additional Setup Information

## Redis

Many Cogs use Redis for data caching and setting expiry keys.  
Redis has a small footprint and is very fast.  
Running the docker Redis container will work with these cogs out of the box.  
To configure specific Redis settings, use the `set api` command.  

```agsl
[p]set api
```
Name: `redis`  
Data:
```agsl
host    redis
port    6379
db      0
pass    onlyifrequired
```
Above information are the defaults. Password defaults to `None`.
DO NOT enter a password in the config unless you require one.

## API

**Coming Soon**. New API will be posted soon.
