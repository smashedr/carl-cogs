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
**[autoroles](autoroles/autoroles.py)** | Adds roles to new members on join.
**[liverole](liverole/liverole.py)** | Give members a role when they go live in Discord.
**[stickyroles](stickyroles/stickyroles.py)** | Remembers users roles and adds them back on rejoin.
**[userchannels](userchannels/userchannels.py)** | Creates custom user rooms on the fly and cleans up when done.
**[warcraftlogs](warcraftlogs/warcraftlogs.py)** | Splits Warcraftlogs into multiple channels based on filters.
**[welcome](welcome/welcome.py)** | Welcomes new users to your servers on join.

### Internal/Hidden Cogs

Cog | Description
------------ | -------------
**carlcog** | Custom Cog for Carl, has useful functions but may not stay here.
**[createthings](createthings/createthings.py)** | WIP: Create pre-defined role and emoji sets.
**pubsub** | Custom Redis Pub/Sub for Carl Bot and Carl's website.
**reactroles** | WIP: React Roles Cog; Working but not yet finished.
