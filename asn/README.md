# AviationSafetyNetwork

Aviation Safety Network data in discord.

**Requires Redis:** See Below for More Details...

## Install

```
[p]cog list carl-cogs
[p]cog install carl-cogs asn
[p]load asn
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
```
docker run --name redis -p 6379:6379 -d redis:alpine
```
