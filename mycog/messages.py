import discord


class Message(object):
    embed = discord.Embed
    red = discord.Colour(int('ff0000', base=16))
    green = discord.Colour(int('00ff00', base=16))
    yellow = discord.Colour(int('ffff00', base=16))

    @classmethod
    def success(cls, message):
        embed = cls.embed()
        embed.colour = cls.green
        embed.description = message
        return embed

    @classmethod
    def error(cls, message):
        embed = cls.embed()
        embed.colour = cls.red
        embed.description = message
        return embed

    @classmethod
    def warning(cls, message):
        embed = cls.embed()
        embed.colour = cls.yellow
        embed.description = message
        return

    @classmethod
    def ok(cls, message):
        return cls.success(message)

    @classmethod
    def bad(cls, message):
        return cls.success(message)

    @classmethod
    def warn(cls, message):
        return cls.success(message)
