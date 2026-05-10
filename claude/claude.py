import json
import re
from datetime import timedelta

import discord
import httpx
import io
import logging
from typing import Optional, Dict
from collections.abc import Callable
import redis.asyncio as redis

# from anthropic import Anthropic

from redbot.core import commands

log = logging.getLogger("red.claude")


class Claude(commands.Cog):
    """Carl's Claude Cog"""

    model: str = "claude-haiku-4-5"  # default model is overridden with set api command
    max_tokens = 1024

    chat_expire_min = 30
    chat_max_messages = 16

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
        self.redis: Optional[redis.Redis] = None
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
        redis_data: dict = await self.bot.get_shared_api_tokens("redis")
        self.redis = redis.Redis(
            host=redis_data.get("host", "redis"),
            port=int(redis_data.get("port", 6379)),
            db=int(redis_data.get("db", 0)),
            password=redis_data.get("pass", None),
        )
        await self.redis.ping()
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
        # if not message.content.startswith("claude"):
        #     return
        pattern = re.compile(r"^((hey|yo)[,\s]+)?(claude|carl)\b", re.IGNORECASE)
        if not pattern.match(message.content):
            return

        # log.debug(message)
        # await message.channel.send("PASS")
        # return

        await message.channel.typing()

        content = pattern.sub("", message.content, count=1).lstrip(" ,")
        log.debug("CLAUDE - content: %s", content)
        if not content:
            await message.channel.send("I hear you, but I don't see your question...")
            return

        # await message.channel.send("FAIL")
        # return

        if content == "clear":
            stored = await self.redis.get(f"claude:{message.author.id}")
            log.debug("stored: %s", stored)
            if stored:
                messages = json.loads(stored)
                await self.redis.delete(f"claude:{message.author.id}")
                await message.channel.send(f"💬 Cleared {len(messages)} Messages")
            else:
                await message.channel.send("✅ No Claude History")
            return

        if content == "history":
            stored = await self.redis.get(f"claude:{message.author.id}")
            log.debug("stored: %s", stored)
            if stored:
                messages = json.loads(stored)
                await message.channel.send(f"💬 Found {len(messages)} Messages")
            else:
                await message.channel.send("✅ No Claude History")
            return

        # await message.channel.send("DEBUG")
        # return

        if not message.reference:
            data = await self.history_message(message.author.id, content)
            text = data["content"][0]["text"]
            text = self.append_usage(data, text)
            await self.send_text(message.channel.send, text)
            return

        # TODO: Add history to replies...
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
            data = await self.history_message(ctx.author.id, question)
            text = data["content"][0]["text"]
            await self.send_text(ctx.send, text)

    async def history_message(self, author_id: int, content: str):
        log.debug("history_message - content: %s", content)
        stored = await self.redis.get(f"claude:{author_id}")
        messages = json.loads(stored) if stored else []
        messages.append({"role": "user", "content": content})
        log.debug("messages: %s", messages)

        data = await self.claude_messages(messages)
        log.debug("data: %s", data)

        text = data["content"][0]["text"]
        log.debug("text: %s", text)

        messages.append({"role": "assistant", "content": text})
        log.debug("messages: %s", messages)
        await self.redis.setex(
            f"claude:{author_id}",
            timedelta(minutes=self.chat_expire_min),
            json.dumps(messages[-self.chat_max_messages :]),
        )
        return data

    def append_usage(self, response: dict, content):
        usage = self.parse_usage(response)
        if usage:
            content += f"\n\n_{usage}_"
        return content

    def parse_usage(self, response: dict):
        usage = response.get("usage", {})
        log.info("parse_usage: %s", usage)
        in_t = usage.get("input_tokens", 0)
        out_t = usage.get("output_tokens", 0)
        in_cost, out_cost = 0, 0
        if "haiku" in self.model:
            in_cost = in_t * (1.00 / 1_000_000)
            out_cost = out_t * (5.00 / 1_000_000)
        elif "sonnet" in self.model:
            in_cost = in_t * (3.00 / 1_000_000)
            out_cost = out_t * (15.00 / 1_000_000)
        elif "opus" in self.model:
            in_cost = in_t * (5.00 / 1_000_000)
            out_cost = out_t * (25.00 / 1_000_000)
        else:
            log.warning("Unknown Model: %s", self.model)
        tot_cost = in_cost + out_cost
        log.info("in: %s, out: %s, total: %s cost: %s", in_t, out_t, in_t + out_t, tot_cost)
        result = ""
        if in_t or out_t:
            result += f"In: {in_t} / Out: {out_t} / Total: {in_t + out_t} / Cost: ${tot_cost:.4f}"
        return result

    async def claude_messages(self, messages):
        log.debug("claude_messages - messages: %s", messages)
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
            "messages": messages,
        }
        log.debug("data: %s", data)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=headers, json=data)
            log.debug("r.status_code: %s", r.status_code)
            r.raise_for_status()
        response = r.json()
        log.debug("response: %s", response)
        return response

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
