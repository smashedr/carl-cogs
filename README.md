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
**[createroles](createroles/createroles.py)** | Create pre-defined or user-defined role sets.
**[liverole](liverole/liverole.py)** | Give members a role when they go live in Discord.
**[stickyroles](stickyroles/stickyroles.py)** | Remembers users roles and adds them back on rejoin.
**[userchannels](userchannels/userchannels.py)** | Creates custom user rooms on the fly and cleans up when done.
**[welcome](welcome/welcome.py)** | Welcomes new users to your servers on join.

### Internal/Hidden Cogs

Cog | Description
------------ | -------------
**mycog** | For testing purposes only!
**pubsub** | Custom Redis Pub/Sub for Carl's website.
**reactroles** | WIP: React Roles cog; working but not finished.
