[![Discord](https://img.shields.io/discord/899171661457293343?style=plastic&label=Discord&logo=discord&logoColor=white&color=7289da)](https://discord.gg/wXy6m2X8wY)
[![Codacy](https://img.shields.io/codacy/grade/439cde1e5a5b4c649beca9b27ec108aa?style=plastic&label=Codacy&logo=codacy)](https://app.codacy.com/gh/smashedr/carl-cogs/dashboard)
[![Issues](https://img.shields.io/github/issues-raw/smashedr/carl-cogs?style=plastic&label=Issues&logo=github&logoColor=white)](https://github.com/smashedr/carl-cogs/issues)
[![Status](https://uptime-nj.hosted-domains.com/api/badge/26/status?upColor=4fc523&style=plastic)](https://uptime-nj.hosted-domains.com/status/carl)
[![](https://repository-images.githubusercontent.com/422749366/a8e0e86a-fcdf-42f4-a5f8-63946c0cd272)](https://discord.com/oauth2/authorize?client_id=204384021352808450&scope=bot+applications.commands&permissions=8)
# Carl-Cogs

Cogs for Carl Bot and Red Discord Bot.

**[Click Here](https://discord.com/oauth2/authorize?client_id=204384021352808450&scope=bot+applications.commands&permissions=8)**
to add Carl Bot to your Discord Server.

## Table of Contents

*   [Installing](#installing)
*   [Public Cogs](#public-cogs)
*   [Internal Cogs](#internal-cogs)
*   [Tags](#tags)
*   [Redis](#redis)
*   [Web API](#web-api)

## Installing

If you run a bot compatible with Red Cogs:

```text
[p]repo add carl-cogs https://github.com/smashedr/carl-cogs
[p]cog list carl-cogs

[p]cog install carl-cogs name
[p]load name
```

## Public Cogs

These Cogs should be suitable for public use with little to no extra setup.

**34**/50

| Cog | Description |
| --- | --- |
| **[activerole](activerole)** | **Redis** - Adds a role to active chatters. |
| **[asn](asn)** | **Redis** - Aviation Safety Network data in discord. |
| **[autoarchive](autoarchive)** | **WIP** - Automatically clones and archives channels before 10k. |
| **[autochannels](autochannels)** |  Creates duplicate channels on the fly and cleans up when done. |
| **[autodisconnect](autodisconnect)** |  Automatically disconnects users from the AFK channel. |
| **[autoroles](autoroles)** |  Adds roles to new members on join. |
| **[avatar](avatar)** | **WIP** - Server Avatar Auto Updates. |
| **[avherald](avherald)** | **Redis** - Get and post Aviation Herald data to Discord. |
| **[botutils](botutils)** |  Custom stateless bot utilities for Carl Bot but useful for anyone. |
| **[chatgraph](chatgraph)** | **API** - Generate Pie Graph of Messages in Current or Specified Channel. |
| **[colorme](colorme)** |  Allow users to manage the color of their own name. |
| **[console](console)** | **WIP** - Random console commands converted to Python and Discord. |
| **[coolbirbs](coolbirbs)** |  Generate a Random Cool Birb from coolbirbs.com. |
| **[dayinhistory](dayinhistory)** | **Redis** - Gets and Posts Today in History. |
| **[flightaware](flightaware)** | **Redis** - FlightAware Flights, Operators, Registration. |
| **[grafana](grafana)** | **WIP** - Grafana Graphs in Discord. |
| **[heartbeat](heartbeat)** |  Pings a Heartbeat service every X seconds. |
| **[imdbsearch](imdbsearch)** |  IMDB Search and lookups. |
| **[liverole](liverole)** |  Give a role to users when they go live in Discord. |
| **[lmgtfy](lmgtfy)** | **WIP** - LMGTFY chat replies. |
| **[ocrimage](ocrimage)** | **WIP** - Converts images to text via Flowery OCR API. |
| **[openai](openai)** | **WIP** - OpenAI and ChatGPT Commands. |
| **[planedb](planedb)** |  Add Name->NNumber Mappings to easily search. |
| **[reactpost](reactpost)** |  Set channels to add Emoji->Channel mappings to post to channel. |
| **[saveforlater](saveforlater)** |  Save any message to later by having the bot send it to you. |
| **[sunsetrise](sunsetrise)** |  Get Sun Set and Sun Rise for Location. |
| **[timer](timer)** |  Start and Stop Timers in Discord. |
| **[tiorun](tiorun)** |  Runs code on tio.run and returns the results. |
| **[userchannels](userchannels)** |  Creates custom user rooms on the fly and cleans up when done. |
| **[webtools](webtools)** |  Web Tools for Carl Bot that could end up in their own module. |
| **[welcome](welcome)** |  Welcomes new users to your servers on join. |
| **[wolfram](wolfram)** | **WIP** - Query Wolfram Alpha for Results. |
| **[youtube](youtube)** | **WIP** - Auto post YouTube videos to specified channels. |
| **[ziplinecog](ziplinecog)** | **WIP** - Zipline Stats in Discord. |

## Internal Cogs

These Cogs are either not designed for other bots or not ready for the Public yet.
You will most likely need to look under the hood to set up these Cogs.

**16**/50

| Cog | Description |
| --- | --- |
| **[captcha](captcha)** | **WIP** - Protect server with CAPTCHA. |
| **[carlcog](carlcog)** |  Custom commands for Carl Bot that could end up in their own module. |
| **[createthings](createthings)** | **Deprecated** - Create pre-defined or user-defined role/emoji sets. |
| **[dictionary](dictionary)** | **WIP** - Dictionary and Urban Dictionary lookups. |
| **[dockercog](dockercog)** | **WIP** - Docker Daemon API. |
| **[github](github)** | **WIP** - Github Functions in Discord. |
| **[miscog](miscog)** |  Miscellaneous commands for Carl Bot that could end up in their own module. |
| **[pubsub](pubsub)** | **Redis, API** - Custom Redis pubsub module for Red and Carl Bot. |
| **[qr](qr)** | **WIP** - Create QR Codes in Discord. |
| **[qrscanner](qrscanner)** | **WIP** - Scans messages for attachments to parse and post QR Data. |
| **[reactroles](reactroles)** | **Deprecated** - Create Reaction Role sets to let users get roles from reactions. |
| **[stickyroles](stickyroles)** | **Deprecated** - Remembers users roles and adds them on rejoin. |
| **[uptimekuma](uptimekuma)** | **WIP** - Uptimekuma in Discord. |
| **[voicetext](voicetext)** | **WIP** - Creates Text Channels for Active Voice Channels and Cleans Up. |
| **[warcraftlogs](warcraftlogs)** | **Deprecated** - Split Warcraft Logs into multiple channels with filters. |
| **[weather](weather)** | **WIP** - Get Weather for Location. |

## Tags

| Tag | Count | Description |
|---|---|---|
| deprecated | **4** | Cog is **DEPRECATED** and may not function as expected or receive updates. |
| wip | **21** | Cog is an active **Work in Progress** and my be frequently updated with breaking changes. |
| redis | **8** | Cog requires **Redis**. [Read More Here...](#redis) |
| api | **4** | Cog **may** require Web API. [Read More Here...](#web-api) |

## Redis

Many Cogs use Redis for data caching and setting expiry keys.
Redis has a small footprint and is very fast.
Running the docker Redis container will work with these cogs out of the box.
To configure specific Redis settings, use the `set api` command.

### Running Redis

```text
docker run --name redis -p 6379:6379 -d redis:alpine
```

### Setup Redis

```text
[p]set api
```

Name `redis` with data:
```text
host    redis
port    6379
db      0
pass    onlyifrequired
```

Above information are the defaults. Password defaults to `None`.
**DO NOT** enter a password in the config unless you require one.

## Web API

It is a Django app in a Docker container:

*   https://github.com/smashedr/red-api
