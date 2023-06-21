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

| Cog                                  | Description                                                               |
|--------------------------------------|---------------------------------------------------------------------------|
| **[activerole](activerole)**         | **Redis** - Adds a role to active chatters.                               |
| **[asn](asn)**                       | **Redis** - Aviation Safety Network data in discord.                      |
| **[autoarchive](autoarchive)**       | **WIP** - Automatically clones and archives channels before 10k.          |
| **[autochannels](autochannels)**     | Creates duplicate channels on the fly and cleans up when done.            |
| **[autodisconnect](autodisconnect)** | Automatically disconnects users from the AFK channel.                     |
| **[autoroles](autoroles)**           | Adds roles to new members on join.                                        |
| **[avherald](avherald)**             | **Redis** - Get and post Aviation Herald data to Discord.                 |
| **[botutils](botutils)**             | Custom stateless bot utilities for Carl Bot but useful for anyone.        |
| **[chatgraph](chatgraph)**           | **API** - Generate Pie Graph of Messages in Current or Specified Channel. |
| **[colorme](colorme)**               | Allow users to manage the color of their own name.                        |
| **[consolecmds](consolecmds)**       | **WIP** - Random console commands converted to Python and Discord.        |
| **[coolbirbs](coolbirbs)**           | Generate a Random Cool Birb from coolbirbs.com.                           |
| **[dayinhistory](dayinhistory)**     | **Redis** - Gets and Posts Today in History.                              |
| **[dictionary](dictionary)**         | Dictionary and Urban Dictionary lookups.                                  |
| **[flightaware](flightaware)**       | **Redis** - FlightAware Flights, Operators, Registration.                 |
| **[heartbeat](heartbeat)**           | Pings a Heartbeat service every X seconds.                                |
| **[imdbsearch](imdbsearch)**         | IMDB Search and lookups.                                                  |
| **[liverole](liverole)**             | Give a role to users when they go live in Discord.                        |
| **[lmgtfy](lmgtfy)**                 | LMGTFY chat replies.                                                      |
| **[ocrimage](ocrimage)**             | **WIP** - Converts images to text via Flowery OCR API.                    |
| **[openai](openai)**                 | **Redis** - OpenAI and ChatGPT Commands.                                  |
| **[qr](qr)**                         | **WIP** - Create QR Codes in Discord.                                     |
| **[qrscanner](qrscanner)**           | **WIP** - Scans messages for attachments to parse and post QR Data.       |
| **[reactpost](reactpost)**           | Set channels to add Emoji->Channel mappings to post to channel.           |
| **[saveforlater](saveforlater)**     | **WIP** - Save any message to later by having the bot send it to you.     |
| **[stickyroles](stickyroles)**       | Remembers users roles and adds them on rejoin.                            |
| **[sunsetrise](sunsetrise)**         | Get Sun Set and Sun Rise for Location.                                    |
| **[timer](timer)**                   | **WIP** - Start and Stop Timers in Discord.                               |
| **[tiorun](tiorun)**                 | **WIP** - Runs code on tio.run and returns the results.                   |
| **[userchannels](userchannels)**     | Creates custom user rooms on the fly and cleans up when done.             |
| **[warcraftlogs](warcraftlogs)**     | **WIP** - Split Warcraft Logs into multiple channels with filters.        |
| **[welcome](welcome)**               | Welcomes new users to your servers on join.                               |

### Internal/Hidden Cogs

| Cog                              | Description                                                                       |
|----------------------------------|-----------------------------------------------------------------------------------|
| **[captcha](captcha)**           | **API** - Protect server with CAPTCHA.                                            |
| **[carlcog](carlcog)**           | Custom commands for Carl Bot that could end up in their own module.               |
| **[createthings](createthings)** | **WIP** - Create pre-defined or user-defined role/emoji sets.                     |
| **[github](github)**             | **WIP** - Github Functions in Discord.                                            |
| **[grafana](grafana)**           | **WIP** - Grafana Graphs in Discord.                                              |
| **[miscog](miscog)**             | Miscellaneous commands for Carl Bot that could end up in their own module.        |
| **[planedb](planedb)**           | **WIP** - Add Name->NNumber Mappings to easily search.                            |
| **[pubsub](pubsub)**             | **Redis, API** - Custom Redis pubsub module for Red and Carl Bot.                 |
| **[reactroles](reactroles)**     | **Deprecated** - Create Reaction Role sets to let users get roles from reactions. |
| **[voicetext](voicetext)**       | **WIP** - Creates Text Channels for Active Voice Channels and Cleans Up.          |
| **[youtube](youtube)**           | **WIP** - Auto post YouTube videos to specified channels.                         |

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

Name `redis` with data:
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
