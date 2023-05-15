import discord
import httpx
import io
import json
import logging
import re
import validators
import redis.asyncio as redis
from datetime import timedelta
from PIL import Image

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
        # 'Content-Type': 'application/json',
    }

    def __init__(self, bot):
        self.bot = bot
        self.redis = redis.Redis

    async def cog_load(self) -> None:
        log.info(f'{self.__cog_name__}: Cog Load Start')
        self.redis = redis.Redis(
            host=REDIS_CONFIG['host'],
            port=REDIS_CONFIG['port'],
            db=REDIS_CONFIG['db'],
            password=REDIS_CONFIG['password'],
        )
        log.info(f'{self.__cog_name__}: Cog Load Finish')

    async def cog_unload(self) -> None:
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
            log.debug(msg.content)
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': msg.content},
            ]
            data = await self.openai_completions(messages)
            log.debug(data)
            chat_response = data['choices'][0]['message']['content']
            await msg.reply(chat_response)

        except Exception as error:
            log.exception(error)
            await channel.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    @commands.command(name='chatgpt', aliases=['newchat'])
    async def chatgpt_new(self, ctx: commands.Context, *, question: str):
        """Start a new ChatGPT with: <question>"""
        bot_msg = await ctx.send('Starting a new ChatGPT...',
                                 delete_after=self.http_options['timeout'])
        await ctx.typing()
        try:
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': question},
            ]
            chat_response = await self.query_n_save(ctx, messages)
            await ctx.send(chat_response)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    @commands.command(name='chat', aliases=['c'])
    async def chatgpt_continue(self, ctx: commands.Context, *, question: str):
        """Continue a ChatGPT session with: <question>"""
        messages = await self.redis.get(f'chatgpt-{ctx.author.id}')
        if messages:
            messages = json.loads(messages)
            bot_msg = await ctx.send('Continuing ChatGPT chat...',
                                     delete_after=self.http_options['timeout'])
        else:
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
            ]
            bot_msg = await ctx.send(f'No chats in the last {CHAT_EXPIRE_MIN} '
                                     f'minutes. Starting a new chat...',
                                     delete_after=self.http_options['timeout'])
        await ctx.typing()
        try:
            messages.append({'role': 'user', 'content': question})
            chat_response = await self.query_n_save(ctx, messages)
            await ctx.send(chat_response)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    async def query_n_save(self, ctx: commands.Context, messages):
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
        headers = {'Content-Type': 'application/json'}
        headers.update(self.headers)
        log.debug('headers: %s', headers)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=headers, json=data)
        if not r.is_success:
            r.raise_for_status()
        return r.json()

    @commands.command(name='aigeneration', aliases=['aigen', 'aimage'])
    async def openai_image_cmd(self, ctx: commands.Context, *, query: str):
        """Request an Image from OpenAI: <size> <query>"""
        size = '1024x1024'
        sizes = ['256x256', '512x512', '1024x1024']
        m = re.search('[0-9]{3,4}x[0-9]{3,4}', query)
        if m and m.group(0):
            if m.group(0) in sizes:
                size = m.group(0)
                query = query.replace(size, '').strip()
            else:
                await ctx.send(f'Valid sizes: {sizes}')
                return

        bot_msg = await ctx.send(f'Generating Image at size {size} now...',
                                 delete_after=self.http_options['timeout'])
        await ctx.typing()
        try:
            img_response = await self.openai_generations(query, size)
            log.debug(img_response)
            if not img_response['data']:
                await ctx.send('Error: No data returned...')
                return

            url = img_response['data'][0]['url']
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=url)
            if not r.is_success:
                r.raise_for_status()

            data = io.BytesIO()
            data.write(r.content)
            data.seek(0)
            file_name = '-'.join(query.split()[:3]).lower() + '.png'
            file = discord.File(data, filename=file_name)
            chat_response = f'**{query}** `{size}`:'
            await ctx.send(chat_response, file=file)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    async def openai_generations(self, query, size='1024x1024', n=1):
        url = 'https://api.openai.com/v1/images/generations'
        data = {
            'prompt': query,
            'size': size,
            'n': n,
        }
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers, json=data)
        if not r.is_success:
            r.raise_for_status()
        return r.json()

    @commands.command(name='aivariation', aliases=['aivary'])
    async def openai_image(self, ctx: commands.Context, *, query: str = None):
        """Request an Image from OpenAI: <image or image url>"""
        log.debug(query)
        log.debug(ctx.message)
        log.debug(ctx.message.attachments)

        if not query or ctx.message.attachments:
            await ctx.send_help()
            return

        bot_msg = await ctx.send(f'Getting Image Variation Now...',
                                 delete_after=self.http_options['timeout'])
        await ctx.typing()

        if query:
            query = query.strip('< >')
            log.debug('query: %s', query)
            if not validators.url(query):
                await ctx.send(f'Not a valid url: {query}')
                return

            # Step 1: Make a GET request and save the response to a io.BytesIO object
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=query, headers=self.headers)
            if not r.is_success:
                await ctx.send(f'Error fetching URL: {query}')
                await bot_msg.delete()
                # r.raise_for_status()
                return

            image_bytes = io.BytesIO(r.content)

        if ctx.message.attachments:
            await ctx.send(f'Error: Attachments are not supported yet.')
            return

        # Step 2: Determine if the image is a PNG
        image = Image.open(image_bytes)

        # Step 3: Convert to PNG if it's not already a PNG
        if image.format != 'PNG':
            log.debug('Converting Image to PNG...')
            # Create a new io.BytesIO object to store the PNG image
            png_image = io.BytesIO()

            # Convert the image to PNG format and save it to the io.BytesIO object
            image.save(png_image, 'PNG')
            png_image.seek(0)
            image_bytes = png_image

        log.debug('Querying OpenAI for Data...')
        size = self.determine_best_size(image)
        img_response = await self.openai_variations(image_bytes, size)
        log.debug(img_response)
        if not img_response['data']:
            await ctx.send('Error: No data returned...')
            await bot_msg.delete()
            return

        try:
            log.debug('Retrieving Image from URL...')
            url = img_response['data'][0]['url']
            log.debug('url: %s', url)
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=url)
            if not r.is_success:
                r.raise_for_status()

            log.debug('Uploading Image to Discord...')
            data = io.BytesIO()
            data.write(r.content)
            data.seek(0)
            file = discord.File(data, filename='variation.png')
            await ctx.send(file=file)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`')

        finally:
            await bot_msg.delete()

    async def openai_variations(self, file: io.BytesIO = None, size='1024x1024'):
        url = 'https://api.openai.com/v1/images/variations'
        data = {'size': size, 'n': 1}
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers,
                                  data=data, files={'image': file})
        if not r.is_success:
            r.raise_for_status()
        return r.json()

    @staticmethod
    def determine_best_size(image):
        sizes = ['256x256', '512x512', '1024x1024']
        width, height = image.size

        best_size = None
        best_diff = float('inf')

        for size in sizes:
            target_width, target_height = map(int, size.split('x'))
            diff = abs(target_width - width) + abs(target_height - height)

            if diff < best_diff:
                best_size = size
                best_diff = diff

        log.debug('best_size: %s', best_size)
        return best_size
