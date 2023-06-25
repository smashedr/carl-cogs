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
from typing import Optional, List

from redbot.core import commands, app_commands

log = logging.getLogger('red.openai')


class OpenAI(commands.Cog):
    """Carl's OpenAI Cog"""

    chat_expire_min = 30
    chat_max_messages = 10
    http_options = {
        'follow_redirects': True,
        'timeout': 30,
    }

    def __init__(self, bot):
        self.bot = bot
        self.redis: Optional[redis.Redis] = None
        self.msg_chatgpt = discord.app_commands.ContextMenu(
            name="AI ChatGPT",
            callback=self.msg_chatgpt_callback,
            type=discord.AppCommandType.message,
        )
        self.msg_spelling = discord.app_commands.ContextMenu(
            name="AI Spelling",
            callback=self.msg_spelling_callback,
            type=discord.AppCommandType.message,
        )
        data = await self.bot.get_shared_api_tokens('openai')
        self.key = data['api_key']
        self.headers = {
            'Authorization': f'Bearer {self.key}',
        }

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        data = await self.bot.get_shared_api_tokens('redis')
        self.redis = redis.Redis(
            host=data['host'] if 'host' in data else 'redis',
            port=int(data['port']) if 'port' in data else 6379,
            db=int(data['db']) if 'db' in data else 0,
            password=data['pass'] if 'pass' in data else None,
        )
        await self.redis.ping()
        self.bot.tree.add_command(self.msg_chatgpt)
        self.bot.tree.add_command(self.msg_spelling)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)
        self.bot.tree.remove_command("AI ChatGPT", type=discord.AppCommandType.message)
        self.bot.tree.remove_command("AI Spelling", type=discord.AppCommandType.message)

    async def msg_chatgpt_callback(self, interaction, message: discord.Message):
        if not message.content:
            return await interaction.response.send_message('Message has no content.',
                                                           ephemeral=True, delete_after=60)
        # ctx = await self.bot.get_context(interaction)
        # await ctx.defer(ephemeral=True, thinking=False)
        await interaction.response.defer()
        await self.process_chatgpt(message)

    async def msg_spelling_callback(self, interaction, message: discord.Message):
        if not message.content:
            return await interaction.response.send_message('Message has no content.',
                                                           ephemeral=True, delete_after=60)
        # ctx = await self.bot.get_context(interaction)
        # await ctx.defer(ephemeral=True)
        await interaction.response.send_message('\U0000231B', ephemeral=True, delete_after=1)
        await self.process_fuck(message)

    @commands.Cog.listener(name='on_message_without_command')
    async def on_message_without_command(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.content:
            return
        if message.type == discord.MessageType.reply:
            await self.process_chatgpt_reply(message)
        if message.content.lower() == 'chatgpt':
            await self.process_chatgpt(message, True)
        if message.content.lower() == 'fuck':
            await self.process_fuck(message)
        if message.content.lower() in ['aimage', 'aimg']:
            await self.process_aimage(message)

    async def process_fuck(self, message: discord.Message, search=False) -> None:
        """Listens for fuck."""
        channel: discord.TextChannel = message.channel
        if search:
            await message.delete()
            match: discord.Message | None = None
            async for m in message.channel.history(limit=10):
                if message.id == m.id:
                    continue
                if message.author.id == m.author.id:
                    match = m
                    break
                if not m.content:
                    continue
        else:
            match = message

        if not match:
            await channel.send('No messages from you out of the last 10...', delete_after=10)
            return

        data = await self.openai_edits(match.content)
        if data['choices']:
            await match.reply(data['choices'][0]['text'])

    async def process_chatgpt_reply(self, message: discord.Message) -> None:
        """Listens for chatgpt replies."""
        pass

    async def process_chatgpt(self, message: discord.Message, search=False) -> None:
        """Listens for chatgpt."""
        channel: discord.TextChannel = message.channel
        if search:
            await message.delete()
            match: discord.Message | None = None
            async for m in message.channel.history(limit=5):
                if m.author.bot:
                    continue
                if m.id == message.id:
                    continue
                if not m.content:
                    continue
                # if m.author.id == message.author.id:
                #     continue
                match = m
                break
        else:
            match = message

        if not match:
            await channel.send('No recent questions found...', delete_after=5)
            return

        bm: discord.Message = await channel.send(
            '\U0000231B Querying ChatGPT Now...',
            delete_after=self.http_options['timeout']
        )
        try:
            log.debug(match.content)
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': match.content},
            ]
            data = await self.openai_completions(messages)
            log.debug(data)
            chat_response = data['choices'][0]['message']['content']
            await match.reply(chat_response)

        except Exception as error:
            log.exception(error)
            await channel.send(f'Error performing lookup: `{error}`',
                               delete_after=10)

        finally:
            await bm.delete()

    async def process_aimage(self, message: discord.Message) -> None:
        """Listens for aimage."""
        channel: discord.TextChannel = message.channel
        await message.delete()
        match = None
        async for m in message.channel.history(limit=5):
            if m.author.bot:
                continue
            if m.id == message.id:
                continue
            if not m.content:
                continue
            match = m
            break

        if not match:
            await channel.send('No recent messages found???', delete_after=10)
            return

        bm: discord.Message = await channel.send(
            f'\U0000231B Querying OpenAI for: `{match.content}`',
            delete_after=self.http_options['timeout']
        )
        try:
            await channel.typing()
            img_response = await self.openai_generations(match.content)
            log.debug(img_response)
            if not img_response['data']:
                await channel.send('Error: No data returned from OpenAI!',
                                   delete_after=10)
                return

            await bm.edit(content='\U0000231B Downloading Image from OpenAI...')
            await channel.typing()
            url = img_response['data'][0]['url']
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=url)
            if not r.is_success:
                log.error('r.status_code: %s', r.status_code)
                await channel.send('Error: Downloading image from OpenAI!',
                                   delete_after=10)
                r.raise_for_status()

            await bm.edit(content='\U0000231B Uploading Image to Discord...')
            await channel.typing()
            data = io.BytesIO()
            data.write(r.content)
            data.seek(0)
            file_name = '-'.join(match.content.split()[:3]).lower() + '.png'
            file = discord.File(data, filename=file_name)
            await match.reply(file=file)

        except Exception as error:
            log.exception(error)
            await channel.send(f'Error performing lookup: `{error}`',
                               delete_after=10)
        finally:
            await bm.delete()

    # @commands.hybrid_command(name='newchat', aliases=['chatgpt'])
    # async def ai_chat_new_cmd(self, ctx: commands.Context, *, question: str):
    #     """Shorthand for Start a new ChatGPT with: <question>"""
    #     await self.ai_chat_new(ctx, question=question)

    @commands.hybrid_command(name='chat', aliases=['c'], description='Continue or Start ChatGPT Session')
    async def ai_chat_cmd(self, ctx: commands.Context, *, question: str):
        """Continue or Start ChatGPT Session with <question>"""
        await self.ai_chat(ctx, question=question)

    @commands.hybrid_group(name='ai', description='OpenAI and ChatGPT Commands')
    async def ai(self, ctx: commands.Context):
        """OpenAI and ChatGPT Commands"""

    @ai.command(name='chat', aliases=['c'], description='Continue or Start ChatGPT Session')
    @app_commands.describe(question='Question or Query to send to ChatGPT')
    async def ai_chat(self, ctx: commands.Context, *, question: str):
        """Continue or Start ChatGPT Session with <question>"""
        messages = await self.redis.get(f'chatgpt:{ctx.author.id}')
        messages = json.loads(messages) if messages else []
        await ctx.typing()
        if messages:
            bm: discord.Message = await ctx.send(
                '\U0000231B Continuing ChatGPT chat...',
                delete_after=self.http_options['timeout']
            )
        else:
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
            ]
            bm: discord.Message = await ctx.send(
                '\U0000231B Starting a new ChatGPT...',
                delete_after=self.http_options['timeout']
            )
        try:
            messages.append({'role': 'user', 'content': question})
            chat_response = await self.query_n_save(ctx, messages)
            await ctx.send(chat_response)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`',
                           delete_after=10)
        finally:
            await bm.delete()

    @ai.command(name='newchat', aliases=['chatgpt'], description='Start New ChatGPT Session')
    @app_commands.describe(question='Question or Query to send to ChatGPT')
    async def ai_chat_new(self, ctx: commands.Context, *, question: str):
        """Start a new ChatGPT with <question>."""
        await ctx.typing()
        bm: discord.Message = await ctx.send(
            '\U0000231B Starting a new ChatGPT...',
            delete_after=self.http_options['timeout']
        )
        try:
            messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': question},
            ]
            chat_response = await self.query_n_save(ctx, messages)
            await ctx.send(chat_response)
        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`',
                           delete_after=10)
        finally:
            await bm.delete()

    @ai.command(name='spelling', aliases=['spellcheck', 'spell', 's'], description='Fix Spelling Errors for Content')
    @app_commands.describe(content='Content to Fix Spelling Errors')
    async def ai_spell(self, ctx: commands.Context, *, content: str):
        """Fix spelling of <content>."""
        log.debug('content: %s', content)
        bm: discord.Message = await ctx.send(
            f'\U0000231B Querying OpenAI Now...',
            delete_after=self.http_options['timeout'],
            ephemeral=True,
        )
        data = await self.openai_edits(content)
        await bm.delete()
        if data['choices']:
            await ctx.send(data['choices'][0]['text'], ephemeral=True)

    @ai.command(name='generation', aliases=['gen', 'g', 'image'], description='Generate a New Image from a Description')
    @app_commands.describe(description='Description for New Image')
    async def ai_image_gen(self, ctx: commands.Context, *, description: str):
        """Request an Image from OpenAI: <size> <query>"""
        size = '1024x1024'
        sizes = ['256x256', '512x512', '1024x1024']
        query = description
        m = re.search('[0-9]{3,4}x[0-9]{3,4}', query)
        if m and m.group(0):
            if m.group(0) in sizes:
                size = m.group(0)
                query = query.replace(size, '').strip()
            else:
                await ctx.send(f'Valid sizes: {sizes}', delete_after=60)
                return

        await ctx.typing()
        bm: discord.Message = await ctx.send(
            f'\U0000231B Generating Image at size {size} now...',
            delete_after=self.http_options['timeout']
        )
        try:
            img_response = await self.openai_generations(query, size)
            log.debug(img_response)
            if not img_response['data']:
                await ctx.send('Error: No data returned!', delete_after=10)
                return

            url = img_response['data'][0]['url']
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=url)
            if not r.is_success:
                log.error('r.status_code: %s', r.status_code)
                await ctx.send(f'Error downloading URL: {url}',
                               delete_after=10)
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
            await ctx.send(f'Error performing lookup: `{error}`',
                           delete_after=10)
        finally:
            await bm.delete()

    @ai.command(name='variation', description='Request Image Variation')
    @app_commands.describe(link='Link of Image to Vary')
    async def ai_image_vary(self, ctx: commands.Context, *, link: str):
        """Request an Image from OpenAI <image or image url>"""
        query = link
        log.debug(query)
        log.debug(ctx.message)
        log.debug(ctx.message.attachments)

        if not query or ctx.message.attachments:
            await ctx.send_help()
            return

        await ctx.typing()
        bm: discord.Message = await ctx.send(
            f'\U0000231B Processing Image Variation...',
            delete_after=self.http_options['timeout']
        )
        # await ctx.typing()
        if query:
            query = query.strip('< >')
            log.debug('query: %s', query)
            if not validators.url(query):
                await ctx.send(f'Not a valid url: {query}')
                return

            # Step 1: Make a GET request and save response to BytesIO object
            await bm.edit(content='\U0000231B Downloading provided URL...')
            # await ctx.typing()
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=query, headers=self.headers)
            if not r.is_success:
                log.error('r.status_code: %s', r.status_code)
                await bm.delete()
                await ctx.send(f'Error fetching URL: {query}')
                r.raise_for_status()

            image_bytes = io.BytesIO(r.content)

        if ctx.message.attachments:
            await ctx.send(f'Error: Attachments are not supported yet!',
                           delete_after=10)
            return

        # Step 3: Convert to PNG if it's not already a PNG
        image = Image.open(image_bytes)
        if image.format != 'PNG':
            await bm.edit(content='\U0000231B Converting to PNG...')
            # await ctx.typing()
            log.debug('Converting Image to PNG...')
            png_image = io.BytesIO()
            image.save(png_image, 'PNG')
            png_image.seek(0)
            image_bytes = png_image

        log.debug('Querying OpenAI for Data...')
        await bm.edit(content='\U0000231B Querying OpenAI for New Image...')
        # await ctx.typing()
        size = self.determine_best_size(image)
        log.debug('size: %s', size)
        img_response = await self.openai_variations(image_bytes, size=size)
        log.debug(img_response)
        if not img_response['data']:
            await ctx.send('Error: No data returned...', delete_after=10)
            await bm.delete()
            return

        try:
            log.debug('Retrieving Image from URL...')
            await bm.edit(content='\U0000231B Downloading Image from OpenAI...')
            # await ctx.typing()
            url = img_response['data'][0]['url']
            log.debug('url: %s', url)
            async with httpx.AsyncClient(**self.http_options) as client:
                r = await client.get(url=url)
            if not r.is_success:
                log.error('r.status_code: %s', r.status_code)
                await ctx.send(f'Error downloading URL: {url}',
                               delete_after=10)
                r.raise_for_status()

            log.debug('Uploading Image to Discord...')
            await bm.edit(content='\U0000231B Uploading Image to Discord...')
            # await ctx.typing()
            data = io.BytesIO()
            data.write(r.content)
            data.seek(0)
            file = discord.File(data, filename='variation.png')
            await ctx.send(file=file)

        except Exception as error:
            log.exception(error)
            await ctx.send(f'Error performing lookup: `{error}`',
                           delete_after=10)
        finally:
            await bm.delete()

    async def query_n_save(self, ctx: commands.Context, messages: List):
        data = await self.openai_completions(messages)
        chat_response = data['choices'][0]['message']['content']
        messages.append({'role': 'assistant', 'content': chat_response})
        await self.redis.setex(
            f'chatgpt:{ctx.author.id}',
            timedelta(minutes=self.chat_expire_min),
            json.dumps(messages[-self.chat_max_messages:]),
        )
        return chat_response

    async def openai_completions(self, messages: List):
        url = 'https://api.openai.com/v1/chat/completions'
        data = {'model': 'gpt-3.5-turbo', 'messages': messages}
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers, json=data)
            log.error('r.status_code: %s', r.status_code)
            r.raise_for_status()
        return r.json()

    async def openai_edits(self, message: str):
        url = 'https://api.openai.com/v1/edits'
        data = {'model': 'text-davinci-edit-001', 'input': message,
                'instruction': 'Fix the spelling mistakes'}
        # Fix the spelling and grammar errors ??? box -> thinking
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers, json=data)
            log.error('r.status_code: %s', r.status_code)
            r.raise_for_status()
        return r.json()

    async def openai_generations(self, query: str, size='1024x1024', n=1):
        url = 'https://api.openai.com/v1/images/generations'
        data = {'prompt': query, 'size': size, 'n': n}
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers, json=data)
            log.error('r.status_code: %s', r.status_code)
            r.raise_for_status()
        return r.json()

    async def openai_variations(self, file: io.BytesIO = None,
                                size='1024x1024', n=1):
        url = 'https://api.openai.com/v1/images/variations'
        data = {'size': size, 'n': n}
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers, data=data,
                                  files={'image': file})
            log.error('r.status_code: %s', r.status_code)
            r.raise_for_status()
        return r.json()

    @staticmethod
    def determine_best_size(image: Image):
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
