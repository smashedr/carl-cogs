# Pubsub

Custom Redis pubsub module for Red and Carl Bot.

**Web API:** Cog _may_ require the Web API for additional functionality. See below...

**Requires Redis:** Cog requires Redis to function. See below...

## Install

```text
[p]cog list carl-cogs
[p]cog install carl-cogs pubsub
[p]load pubsub
```

## Configure Redis

Use the set api command to configure redis credentials.
This is not necessary if all values are default.
Make sure to **NOT** set a password unless you need one.

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

To start a Redis instance with all defaults run:
```text
docker run --name redis -p 6379:6379 -d redis:alpine
```

## Configure Web API

It is a Django app in a Docker container:

*   https://github.com/smashedr/red-api
