import discord
import httpx
import logging
import zlib
from thefuzz import process
from typing import Optional, Tuple, Dict, List, Any

from redbot.core import app_commands, commands, Config
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger('red.tiorun')


class Tiorun(commands.Cog):
    """Carl's Tiorun Cog"""

    tio_url = 'https://tio.run/cgi-bin/static/b666d85ff48692ae95f24a66f7612256-run/93d25ed21c8d2bb5917e6217ac439d61'
    http_options = {
        'follow_redirects': True,
        'timeout': 6,
    }

    guild_default = {
        'channels': [],
    }

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)

    async def cog_load(self):
        log.info('%s: Cog Load Start', self.__cog_name__)
        log.info('%s: Cog Load Finish', self.__cog_name__)

    async def cog_unload(self):
        log.info('%s: Cog Unload', self.__cog_name__)

    @commands.hybrid_command(name='run', aliases=['tio', 'tiorun'])
    @commands.guild_only()
    @commands.max_concurrency(1, commands.BucketType.user)
    @app_commands.describe(language='Programming Language', code='Code to Execute')
    async def run_command(self, ctx: commands.Context, language: str, *, code: str):
        """Executes arbitrary code and returns the output."""
        await ctx.typing()
        languages = await self.get_languages()
        if not languages:
            return await ctx.send('The author of this cog is, to be nice, the king of retards!')
        language = language.lower()
        lang_list = ['languages', 'language', 'list', 'lang']
        if language in lang_list:
            return await ctx.send('')
        matches = {
            'python': 'python3-cython',
            'py': 'python3-cython',
            'c': 'c-clang',
            'cpp': 'cpp-clang',
            'c++': 'cpp-clang',
            'cs': 'cs-core',
            'c#': 'cs-core',
        }
        if language in matches:
            match = matches[language]
        else:
            match, _ = process.extractOne(language, languages.keys())
        log.debug('match: %s', match)
        lang = languages[match]
        log.debug('lang: %s', lang)
        if not lang:
            return await ctx.send('The author of this cog is, to be nice, the king of retards!')
        code = code.strip('` ')
        log.debug('-'*40)
        log.debug('code: %s', code)
        log.debug('-'*40)
        if not code:
            return await ctx.send('The author of this cog is, to be nice, the king of retards!')
        output_list, debug_list = await self.run_code(match, code)
        log.debug('output_list: %s', output_list)
        log.debug('debug_list: %s', debug_list)
        if not output_list:
            return await ctx.send('The author of this cog is, to be nice, the king of retards!')
        output = '\n'.join(output_list).strip()
        debug = '\n'.join(debug_list).strip()
        limit = 4000 - (len(debug) + 20)
        description = cf.box(output[:limit]) + '\n' + cf.italics(debug)
        log.debug('description: %s', description)
        embed = discord.Embed(
            color=await ctx.embed_color(),
            title=f"{lang['name']}",
            url=lang['link'],
            description=description,
        )
        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    # @commands.group(name='tiorun', aliases=['tio', 'run'])
    # @commands.guild_only()
    # @checks.admin_or_permissions(manage_guild=True)
    # async def _rp(self, ctx):
    #     """Manage the ReactPost Options"""

    # @code.command(name="languages")
    # async def code_languages(self, ctx: commands.Context) -> None:
    #     """
    #     List all supported languages
    #     """
    #     languages = await self.get_languages()
    #     if not languages:
    #         return await ctx.send('Something went wrong with the API.')
    #
    #     text = ", ".join([f"[{l['name']}]({l['link']})" for l in languages])
    #     pages = [p for p in pagify(text=text, delims=",", page_length=4000)]
    #     embeds = []
    #     for i, page in enumerate(pages):
    #         embed = discord.Embed(
    #             color=await ctx.embed_color(),
    #             title="Supported Languages",
    #             description=page,
    #         )
    #         embed.set_footer(text=f"Page {i + 1}/{len(pages)}")
    #         embeds.append(embed)
    #
    #     await menu(ctx, embeds, DEFAULT_CONTROLS)

    async def get_languages(self) -> Optional[Dict[str, Any]]:
        url = 'https://tio.run/languages.json'
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.get(url=url)
        log.debug('r.status_code: %s', r.status_code)
        r.raise_for_status()
        return r.json()

    async def run_code(self, language: str, code: str) -> Tuple[List[str], List[str]]:
        payload = [
            {"command": "V", "payload": {"lang": [language.lower()]}},
            {"command": "F", "payload": {".code.tio": code}},
            {"command": "F", "payload": {".input.tio": ""}},
            {"command": "RC"},
        ]
        req = b""
        for instr in payload:
            req += instr["command"].encode()
            if "payload" in instr:
                [(name, value)] = instr["payload"].items()
                req += b"%s\0" % name.encode()
                if isinstance(value, str):
                    value = value.encode()
                req += b"%u\0" % len(value)
                if not isinstance(value, bytes):
                    value = "\0".join(value).encode() + b"\0"
                req += value

        content = zlib.compress(req, 9)[2:-4]
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=self.tio_url, content=content)
        r.raise_for_status()
        res = zlib.decompress(r.content, 31)
        weird_thing = res[:16]
        ret = res[16:].split(weird_thing)
        count = len(ret) >> 1
        output, debug = ret[:count], ret[count:]
        output = [x.decode("utf-8", "ignore") for x in output]
        debug = [x.decode("utf-8", "ignore") for x in debug]
        return output, debug

    # @staticmethod
    # def file_from_responses(output: str, debug: str) -> discord.File:
    #     result = f"""Output:\n{output}\n--------------------------------------------------\nDebug Info:\n{debug}"""
    #     f = io.BytesIO(result.encode("utf-8"))
    #     return discord.File(f, "output.txt")
