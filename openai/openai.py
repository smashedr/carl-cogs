import discord
import httpx
import json
import logging
import redis.asyncio as redis
from datetime import timedelta

from redbot.core import commands

log = logging.getLogger('red.openai')

CHAT_EXPIRE_MIN = 15

REDIS_CONFIG = {
    'host': 'redis',
    'port': 6379,
    'db': 0,
    'password': None,
}


class Openai(commands.Cog):
    """Carl's OpenAI Cog"""

    key = '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'
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
        self.redis = redis.Redis

    async def cog_load(self):
        log.info(f'{self.__cog_name__}: Cog Load Start')
        self.redis = redis.Redis(
            host=REDIS_CONFIG['host'],
            port=REDIS_CONFIG['port'],
            db=REDIS_CONFIG['db'],
            password=REDIS_CONFIG['password'],
        )
        log.info(f'{self.__cog_name__}: Cog Load Finish')

    async def cog_unload(self):
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

        bot_msg = await channel.send('Querying ChatGPT Now...',
                                     delete_after=self.http_options['timeout'])
        try:
            log.info(msg.content)
            data = await self.openai_completions(msg.content)
            log.info(data)
            chat_response = data['choices'][0]['message']['content']
            await msg.reply(chat_response)

        except Exception as error:
            log.exception(error)
            await channel.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    @commands.command(name='chatgpt', aliases=['newchat'])
    async def chatgpt_new(self, ctx, *, question: str):
        """Start a new ChatGPT with: <question>"""
        bot_msg = await ctx.send('Querying ChatGPT Now...',
                                 delete_after=self.http_options['timeout'])
        try:
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': question},
            ]
            chat_response = self.query_n_save(ctx, messages)
            await ctx.send(chat_response)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    @commands.command(name='chat', aliases=['c'])
    async def chatgpt_continue(self, ctx, *, question: str):
        """Continue a ChatGPT session with: <question>"""
        messages = await self.redis.get(f'chatgpt-{ctx.author.id}')
        messages = json.loads(messages)
        if not messages:
            await ctx.send(f'No chats in the last {CHAT_EXPIRE_MIN} minutes.')
            return

        bot_msg = await ctx.send('Querying ChatGPT Now...',
                                 delete_after=self.http_options['timeout'])
        try:
            messages.append({'role': 'user', 'content': question})
            chat_response = self.query_n_save(ctx, messages)
            await ctx.send(chat_response)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    async def query_n_save(self, ctx, messages):
        data = await self.openai_completions(messages)
        log.debug(data)
        chat_response = data['choices'][0]['message']['content']
        messages.append({'role': 'assistant', 'content': chat_response})
        await self.redis.setex(
            f'chatgpt-{ctx.author.id}',
            timedelta(minutes=CHAT_EXPIRE_MIN),
            json.dumps(messages),
        )
        return chat_response

    async def openai_completions(self, messages):
        url = 'https://api.openai.com/v1/chat/completions'
        data = {'model': 'gpt-3.5-turbo', 'messages': messages}
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers, json=data)
        if not r.is_success:
            r.raise_for_status()
        return r.json()
