import discord
import logging
from redbot.core import commands, Config

logger = logging.getLogger('red.warcraftlogs')


class Warcraftlogs(commands.Cog):
    """Carl's Warcraftlogs Cog"""
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(enabled=False, splits={})

    async def initialize(self) -> None:
        logger.info('Initializing Warcraftlogs Cog')

    @commands.Cog.listener()
    async def on_message_without_command(self, message: discord.Message):
        if not message.webhook_id or not message.embeds:
            logger.debug('not webhook or embed')
            return

        embed: discord.Embed = message.embeds[0]
        logger.debug(embed)

        if 'url' not in embed or 'warcraftlogs.com' not in embed.url:
            logger.debug('no url or not wcl')
            return

        config = await self.config.guild(message.guild).all()
        if not config['enabled'] or not config['splits']:
            logger.debug('disabled or no splits')
            return

        em = discord.Embed(colour=int('00FF00', 16))
        em.description = 'Report ID: `{}`'.format(embed.url.split('/')[4])
        em.url = embed.url
        em.title = embed.title
        em.set_author(name=embed.description, url=embed.url)
        em.set_thumbnail(url='https://i.imgur.com/pHJks56.png')
        em.set_footer(text=embed.author.name.split()[0],
                      icon_url=embed.thumbnail.url)

        logger.debug('Matching: "%s"', embed.description.lower())
        for split, channel in config['splits'].items():
            logger.debug(f'"{split}" - #{channel}')
            if split in embed.description.lower():
                logger.debug('MATCHED SPLIT')
                channel = message.guild.get_channel(channel)
                if channel:
                    await channel.send(embed=em)

    @commands.group(name='warcraftlogs', aliases=['wcl'])
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def wcl(self, ctx):
        """Options for manging Warcraftlogs splits."""

    @wcl.command(name='add', aliases=['a'])
    async def wcl_add(self, ctx, channel: discord.TextChannel, *, match):
        """
        Add a channel to Warcraftlogs splits with a matching title term.
        [p]wcl add <channel> <matching title term>
        [p]wcl add #raid-2 Raid 2
        """
        config = await self.config.guild(ctx.guild).splits() or {}
        if match.lower() not in config:
            config[match.lower()] = channel.id
            await self.config.guild(ctx.guild).splits.set(config)
            await ctx.send(f'Added split of WCL to channel {channel.mention} '
                           f'if report title contains: "{match.lower()}"')
        else:
            await ctx.send(f'Split matching "{match.lower()}" already exist.')

    @wcl.command(name='remove', aliases=['r'])
    async def wcl_remove(self, ctx, *, match):
        """Removes a channel from Warcraftlogs splits."""
        config = await self.config.guild(ctx.guild).splits() or {}
        if match.lower() in config:
            del config[match.lower()]
            await self.config.guild(ctx.guild).splits.set(config)
            await ctx.send(f'Split matching "{match.lower()}" deleted.')
        else:
            await ctx.send(f'Split matching "{match.lower()}" does not exist')

    @wcl.command(name='enable', aliases=['e', 'on'])
    async def wcl_enable(self, ctx):
        """Enables Warcraftlogs."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if enabled:
            await ctx.send('Warcraftlogs Splitting already enabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(True)
            await ctx.send('Warcraftlogs Splitting have been enabled.')

    @wcl.command(name='disable', aliases=['d', 'off'])
    async def wcl_disable(self, ctx):
        """Disable Warcraftlogs."""
        enabled = await self.config.guild(ctx.guild).enabled()
        if not enabled:
            await ctx.send('Warcraftlogs Splitting already disabled.')
        else:
            await self.config.guild(ctx.guild).enabled.set(False)
            await ctx.send('Warcraftlogs Splitting have been disabled.')

    @wcl.command(name='status', aliases=['s', 'settings'])
    async def wcl_status(self, ctx):
        """Get Warcraftlogs status."""
        logger.debug(ctx.guild)
        config = await self.config.guild(ctx.guild).all()
        logger.debug(config)
        out = f'Warcraftlogs Settings:\n' \
              f'Status: **{config["enabled"]}**\n' \
              f'Splits: {config["splits"]}'
        await ctx.send(out)
