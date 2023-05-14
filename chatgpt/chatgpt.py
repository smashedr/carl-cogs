import discord
import httpx
import logging

from redbot.core import commands

log = logging.getLogger('red.chatgpt')


class Chatgpt(commands.Cog):
    """Carl's ChatGPT Cog"""
    __version__ = '1.0'

    key = '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'
    url = 'https://api.openai.com/v1/chat/completions'
    http_options = {
        'follow_redirects': True,
        'timeout': 30,
    }
    headers = {
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }

    def __init__(self, bot):
        self.bot = bot

    def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load')

    def cog_unload(self):
        log.info(f'{self.__cog_name__}: Cog Unload')

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message) -> None:
        """Listens for chatgpt."""
        channel = message.channel

        trigger = 'chatgpt'
        if message.author.bot or message.content.lower() != trigger:
            return

        await message.delete()
        msg = None
        async for m in message.channel.history(limit=5):
            if m.author.bot:
                continue
            if m.id == message.id:
                continue
            if m.author.id == message.author.id:
                continue
            msg = m
            break

        if not msg:
            await channel.send('No recent questions found...', delete_after=5)
            return

        query = await channel.send('Querying ChatGPT Now...',
                                   delete_after=self.http_options['timeout'])
        try:
            log.info(msg.content)
            data = await self.chat_gpt_response(msg.content)
            log.info(data)
            chat_response = data['choices'][0]['message']['content']
            log.info(chat_response)
            await msg.reply(chat_response)

        except Exception as error:
            log.exception(error)
            await channel.send(f'Error performing lookup: `{error}`')

        finally:
            await query.delete()

    @commands.command(name='chatgpt', aliases=['chat'])
    async def chat_gpt(self, ctx, *, question: str):
        """Ask ChatGPT a <question>."""
        query = await ctx.send('Querying ChatGPT Now...',
                                   delete_after=self.http_options['timeout'])
        try:
            data = await self.chat_gpt_response(question)
            log.debug(data)
            chat_response = data['choices'][0]['message']['content']
            log.debug(chat_response)
            await ctx.send(chat_response)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')

        finally:
            await query.delete()

    async def chat_gpt_response(self, query):
        data = {
            'model': 'gpt-3.5-turbo',
            'messages': [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': query}
            ]
        }
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=self.url, headers=self.headers, json=data)
        if not r.is_success:
            r.raise_for_status()
        return r.json()
