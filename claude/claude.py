import discord
import httpx
import io
import logging
from typing import Optional, Dict
from collections.abc import Callable

# from anthropic import Anthropic

from redbot.core import commands

log = logging.getLogger("red.claude")


class Claude(commands.Cog):
    """Carl's Claude Cog"""

    model: str = "claude-sonnet-4-6"  # default model is overridden with set api command
    max_tokens = 1024
    http_options = {
        "follow_redirects": True,
        "timeout": 30,
    }

    instructions: str = (
        "You are Carl, a Discord bot. Give short answers unless the question genuinely requires detail."
        # "No padding, no filler, no restating the question."
    )

    def __init__(self, bot):
        self.bot = bot
        # self.redis: Optional[redis.Redis] = None
        self.key: Optional[str] = None
        self.headers: Optional[Dict[str, str]] = None
        self.msg_claude = discord.app_commands.ContextMenu(
            name="Query Claude",
            callback=self.msg_claude_callback,
            type=discord.AppCommandType.message,
        )
        # self.client: Optional[Anthropic] = None

    async def cog_load(self):
        log.info("%s: Cog Load Start", self.__cog_name__)
        # redis_data: dict = await self.bot.get_shared_api_tokens('redis')
        # self.redis = redis.Redis(
        #     host=redis_data.get('host', 'redis'),
        #     port=int(redis_data.get('port', 6379)),
        #     db=int(redis_data.get('db', 0)),
        #     password=redis_data.get('pass', None),
        # )
        # await self.redis.ping()
        data: Dict[str, str] = await self.bot.get_shared_api_tokens("claude")
        log.debug("%s: data: %s", self.__cog_name__, data)
        self.key = data.get("api") or data.get("key") or data.get("token") or data["api_key"]
        log.debug("%s: api_key: %s", self.__cog_name__, self.key)
        self.model = data.get("model", self.model)
        log.debug("%s: model: %s", self.__cog_name__, self.model)
        self.headers = {"X-Api-Key": self.key}

        # self.client = Anthropic(api_key=self.key)

        self.bot.tree.add_command(self.msg_claude)
        log.info("%s: Cog Load Finish", self.__cog_name__)

    async def cog_unload(self):
        log.info("%s: Cog Unload", self.__cog_name__)
        self.bot.tree.remove_command("Query Claude", type=discord.AppCommandType.message)

    async def msg_claude_callback(self, interaction, message: discord.Message):
        log.debug("msg_claude_callback: %s", message)
        await interaction.response.defer()
        text = await self.claude_response(message.content)
        await self.send_text(interaction.followup.send, text)

    @commands.Cog.listener(name="on_message_without_command")
    async def on_message_without_command(self, message: discord.Message) -> None:
        """Listener."""
        if message.author.bot:
            return
        # log.debug(message)
        if message.content.startswith("claude"):
            content = message.content.removeprefix("claude").lstrip(", ")
            log.debug("claude - content: %s", content)
            if message.reference:
                replied_to = message.reference.resolved
                log.debug(f"replied_to: {replied_to}")
                if replied_to is None:
                    replied_to = await message.channel.fetch_message(message.reference.message_id)
                log.debug(f"replied_to.content: {replied_to.content}")
                content += f"\n\nMessage User Replied Too:\n\n{replied_to.content}"
            log.debug(f"content: {content}")
            async with message.channel.typing():
                text = await self.claude_response(content)
                await self.send_text(message.channel.send, text)

    @commands.hybrid_command(name="claude", aliases=["claud", "clade"], description="Claude Command")
    async def claude_cmd(self, ctx: commands.Context, *, question: str):
        """Ask Claude a <question>"""
        log.debug("claude_cmd - question: %s", question)
        # await ctx.typing()
        async with ctx.typing():
            text = await self.claude_response(question)
            await self.send_text(ctx.send, text)

    # async def claude_response(self, message):
    #     log.debug("claude_response - message: %s", message)
    #     response = self.client.messages.create(
    #         model=self.model, max_tokens=1024, messages=[{"role": "user", "content": message}]
    #     )
    #     log.debug("response: %s", response)
    #     return response.content[0].text

    async def claude_response(self, message):
        log.debug("claude_response - message: %s", message)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        data = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": self.instructions,
            # "system": [{"type": "text", "text": self.instructions, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": message}],
        }
        log.debug("data: %s", data)

        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=headers, json=data)
            log.debug("r.status_code: %s", r.status_code)
            r.raise_for_status()

        response = r.json()
        log.debug("response: %s", response)

        text = response["content"][0]["text"]
        log.debug("text: %s", text)
        usage = response.get("usage", {})
        log.info("usage: %s", usage)
        in_t = usage.get("input_tokens", 0)
        out_t = usage.get("output_tokens", 0)

        in_cost = in_t * (1.00 / 1_000_000)
        out_cost = out_t * (5.00 / 1_000_000)
        # in_cost = in_t * (3.00 / 1_000_000)
        # out_cost = out_t * (15.00 / 1_000_000)
        # in_cost = in_t * (5.00 / 1_000_000)
        # out_cost = out_t * (25.00 / 1_000_000)
        tot_cost = in_cost + out_cost

        log.info("in: %s, out: %s, total: %s", in_t, out_t, in_t + out_t)
        if in_t or out_t:
            text = f"{text}\n\n_In: {in_t} / Out: {out_t} / Total: {in_t + out_t} / Cost: ${tot_cost:.4f}_"
        return text

    @staticmethod
    async def send_text(send: Callable, message: str):
        if len(message) < 2000:
            return await send(message)
        else:
            buffer = io.BytesIO(message.encode("utf-8"))
            file = discord.File(buffer, filename="response.txt")
            await send(file=file)
