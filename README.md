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

Cog | Description
------------ | -------------
**[autochannels](autochannels/autochannels.py)** | Creates duplicate channels on the fly and cleans up when done.
**[autodisconnect](autodisconnect/autodisconnect.py)** | Automatically disconnects users from the AFK channel.
**[autoroles](autoroles/autoroles.py)** | Adds roles to new members on join.
**[botutils](botutils/botutils.py)** | Custom stateless bot utilities for Carl Bot but useful for anyone.
**[dictionary](dictionary/dictionary.py)** | Dictionary and Urban Dictionary lookups.
**[liverole](liverole/liverole.py)** | Give a role to users when they go live in Discord.
**[stickyroles](stickyroles/stickyroles.py)** | Remembers users roles and adds them on rejoin.
**[userchannels](userchannels/userchannels.py)** | Creates custom user rooms on the fly and cleans up when done.
**[warcraftlogs](warcraftlogs/warcraftlogs.py)** | Split Warcraft Logs into multiple channels with filters.
**[welcome](welcome/welcome.py)** | Welcomes new users to your servers on join.

### Internal/Hidden Cogs

Cog | Description
------------ | -------------
**[activerole](activerole/activerole.py)** | **WIP: Requires Redis**. Adds a role to active chatters.
**[carlcog](carlcog/carlcog.py)**  | **Custom** Cog for Carl, has useful functions but may not stay here.
**[openai](openai/openai.py)**  | **WIP** Query OpenAI/ChatGPT and query off others previous questions.
**[createthings](createthings/createthings.py)** | **WIP**: Create pre-defined role and emoji sets.
**[heartbeat](heartbeat/heartbeat.py)** | Sends a ping to a heartbeat service; **has hard coding**.
**[lmgtfy](lmgtfy/lmgtfy.py)** | **WIP** Replies to the last query in chat with a real google link.
**[pubsub](pubsub/pubsub.py)** | **Custom** Redis Pub/Sub for Carl Bot and Carl's website.
**[reactroles](reactroles/reactroles.py)** | **WIP**: React Roles Cog; Working but not yet finished.
