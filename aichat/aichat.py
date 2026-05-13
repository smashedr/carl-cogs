import json
import discord
import httpx
import io
import logging
import re
from collections import deque
from pprint import pformat
from typing import Optional, Dict, Callable

from redbot.core import commands, Config
from redbot.core.utils import AsyncIter
from redbot.core.utils import chat_formatting as cf

log = logging.getLogger("red.aichat")


MODEL_PRICING = {
    # # GPT-5.4 series
    # "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-mini": (0.375, 2.25),  # flex
    # "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-nano": (0.10, 0.625),  # flex
    # # GPT-5.2 series
    # "gpt-5.2": (1.75, 14.00),
    # # GPT-5.1 series
    # "gpt-5.1": (1.25, 10.00),
    # # GPT-5 series
    # "gpt-5": (1.25, 10.00),
    # "gpt-5": (0.625, 5.00),  # flex
    # "gpt-5-mini": (0.25, 2.00),
    "gpt-5-mini": (0.125, 1.00),  # flex
    # "gpt-5-nano": (0.05, 0.40),
    "gpt-5-nano": (0.025, 0.20),  # flex
    # # GPT-4.1 series
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    # # GPT-4o series
    "gpt-4o-mini": (0.15, 0.60),
}


class AIChat(commands.Cog):
    """Carl's AIChat Cog"""

    # TODO: Add instructions to guild_default
    instructions: str = "You are Carl, a Discord bot. Give short answers unless the question genuinely requires detail."
    guild_default = {
        "model": "gpt-4.1-nano",
        "channels": [],
    }
    channel_default = {
        "instructions": None,
        # "chat_messages": 20,  # TODO: Implement Channel Messages
    }
    channel_histories = {}

    max_tokens = 1024
    chat_messages = 20
    http_options = {
        "follow_redirects": True,
        "timeout": 60,
    }

    # noinspection PyMissingConstructor
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 1337, True)
        self.config.register_guild(**self.guild_default)
        self.config.register_channel(**self.channel_default)

        self.key: Optional[str] = None
        self.headers: Optional[Dict[str, str]] = None

    async def cog_load(self):
        log.info("%s: Cog Load Start", self.__cog_name__)
        data: Dict[str, str] = await self.bot.get_shared_api_tokens("openai")
        log.debug("%s: data: %s", self.__cog_name__, data)
        self.key = data.get("api") or data.get("key") or data.get("token") or data["api_key"]
        self.headers = {"Authorization": f"Bearer {self.key}"}

        log.debug("httpx.__version__: %s", httpx.__version__)

        await self.bot.wait_until_ready()
        await self.process_history()
        log.info("%s: Cog Load Finish", self.__cog_name__)

    async def cog_unload(self):
        log.info("%s: Cog Unload", self.__cog_name__)

    async def process_history(self):
        log.debug("%s: process_history", self.__cog_name__)
        all_guilds: dict = await self.config.all_guilds()
        log.debug("all_guilds: %s", all_guilds)
        for guild_id, data in all_guilds.items():
            log.debug("guild_id: %s - data: %s", guild_id, data)
            guild: discord.Guild = self.bot.get_guild(guild_id)
            log.debug("guild: %s", guild)
            for channel in await AsyncIter(data.get("channels", []), delay=1, steps=3):
                log.debug("channel: %s", channel)
                await self.gen_history(guild, channel)

    async def gen_history(self, guild: discord.Guild, channel_id):
        log.debug("gen_history: %s", channel_id)
        channel: discord.TextChannel = guild.get_channel(channel_id)
        log.debug("channel: %s", channel)

        # channel_config: dict = await self.config.channel(channel_id).all()
        # log.debug("channel_config: %s", channel_config)

        # if channel_id not in self.channel_histories:
        self.channel_histories[channel_id] = deque(maxlen=self.chat_messages)

        messages = [msg async for msg in channel.history(limit=self.chat_messages)]
        for message in reversed(messages):
            log.debug("message: %s", message.content)
            if not message.content:
                continue
            self.push_message(self.channel_histories[channel_id], message, guild.me.id)

        log.debug("history: %s", self.channel_histories[channel_id])

    @staticmethod
    def push_message(results: list, message: discord.Message, user_id: int):
        # log.debug("push_message - id: %s - bot: %s", message.author.id, user_id)
        if message.author.id == user_id:
            # results.append({"role": "model", "parts": [{"text": message.content}]})  # Gemini
            results.append({"role": "assistant", "content": message.content})  # OpenAI
        else:
            text = f"[{message.author.display_name}]: {message.content}"
            # results.append({"role": "user", "parts": [{"text": text}]})  # Gemini
            results.append({"role": "user", "content": text})  # OpenAI

    @commands.Cog.listener(name="on_message")
    async def on_message(self, message: discord.Message):
        if not message.content:
            return
        # channels = await self.config.guild(message.guild).channels()
        guild_config: dict = await self.config.guild(message.guild).all()
        log.debug("guild_config: %s", guild_config)
        log.debug("channels: %s", guild_config.get("channels", []))
        if message.channel.id not in guild_config["channels"]:
            return

        # log.debug("message: %s", message)
        if message.channel.id not in self.channel_histories:
            self.channel_histories[message.channel.id] = deque(maxlen=self.chat_messages)
        self.push_message(self.channel_histories[message.channel.id], message, message.guild.me.id)

        if message.author.bot:
            return
        # pattern = re.compile(r"^((hey|yo)[,\s]+)?(carl)\b", re.IGNORECASE)
        pattern = re.compile(r"^(\w+[,\s]+){0,2}(carl)\b", re.IGNORECASE)
        if not pattern.match(message.content):
            return
        # log.debug("message: %s", message)

        async with message.channel.typing():
            messages = list(self.channel_histories.get(message.channel.id, deque()))
            # log.debug("messages: %s", messages)
            log.debug("len(messages): %s", len(messages))

            # model = await self.config.guild(message.guild).model()
            model = guild_config.get("model")
            log.debug("model: %s", model)

            channel_config: dict = await self.config.channel(message.channel).all()
            log.debug("channel_config: %s", channel_config)
            instructions = channel_config.get("instructions")
            log.debug("instructions: %s", instructions)

            data = await self.openai_responses(messages, model, instructions)
            log.debug("response - data: %s", data)
            # text = data["output"][0]["content"][0]["text"]
            text = self.get_text(data)
            # text = await self.append_usage(model, data, text)
            log.debug("text: %s", text)
            await self.send_text(message.channel.send, text)

    # @commands.hybrid_command(name="chat", aliases=["c"], description="Continue or Start ChatGPT Session")
    # async def ai_chat_cmd(self, ctx: commands.Context, *, question: str):
    #     """Continue or Start ChatGPT Session with <question>"""
    #     await self.ai_chat(ctx, question=question)

    @commands.group(name="ai", description="AI Chat Bot Commands")
    async def ai(self, ctx: commands.Context):
        """AI Chat Bot Commands"""

    # @ai.command(name="chat", aliases=["c"], description="Continue or Start ChatGPT Session")
    # @app_commands.describe(question="Question or Query to send to ChatGPT")
    # async def ai_chat(self, ctx: commands.Context, *, question: str):
    #     """Continue or Start ChatGPT Session with <question>"""
    #     log.debug("ai_chat - question: %s", question)
    #     await ctx.typing()

    # @ai.command(name="newchat", aliases=["chatgpt", "new"], description="Start New ChatGPT Session")
    # @app_commands.describe(question="Question or Query to send to ChatGPT")
    # async def ai_chat_new(self, ctx: commands.Context, *, question: str):
    #     """Start a new ChatGPT with <question>."""
    #     log.debug("ai_chat_new - question: %s", question)
    #     await ctx.typing()

    ## CHANNEL MANAGEMENT ##

    @ai.command(name="context", aliases=["c", "ctx"], description="Dump AI Chat Context")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.channel)
    @commands.guild_only()
    async def _ai_context(self, ctx: commands.Context):
        """Dump AI Chat Context"""
        log.debug("_ai_context")
        await ctx.typing()
        channels = await self.config.guild(ctx.guild).channels()
        if ctx.channel.id not in channels:
            await ctx.send("❕ AI Disabled. Enable it first.")
            return

        history = list(self.channel_histories.get(ctx.channel.id))
        log.debug("history: %s", history)
        data = json.dumps(history, indent=2)
        log.debug("data: %s", data)
        bytes_io = io.BytesIO(bytes(data, "utf-8"))
        file = discord.File(bytes_io, f"{ctx.channel.name}.json")
        await ctx.send(f"Chat Context for {ctx.channel.mention}", file=file)

    @ai.command(name="reset", aliases=["r", "clear"], description="Reset or Cut AI Chat Context")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.cooldown(rate=1, per=5, type=commands.BucketType.channel)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _ai_reset(self, ctx: commands.Context, number: Optional[int] = 0):
        """Reset or Cut AI Chat Context"""
        log.debug("_ai_reset: %s", number)
        await ctx.typing()
        channels = await self.config.guild(ctx.guild).channels()
        if ctx.channel.id not in channels:
            await ctx.send("❕ AI Disabled. Enable it first.")
            return

        if number and number > 0:
            history = self.channel_histories.get(ctx.channel.id)
            if history:
                self.channel_histories[ctx.channel.id] = deque(list(history)[-number:])
            await ctx.send(f"✂️ AI Chat History Truncated to {number} Messages")
        else:
            self.channel_histories[ctx.channel.id].clear()
            await ctx.send("🧹 AI Chat History Cleared")

    @ai.command(name="instructions", aliases=["i", "role", "system"], description="AI Channel Instructions")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _ai_instructions(self, ctx: commands.Context, *, instructions: Optional[str] = None):
        """AI Channel Instructions"""
        log.debug("_ai_instructions: %s", instructions)
        await ctx.typing()
        channels = await self.config.guild(ctx.guild).channels()
        if ctx.channel.id not in channels:
            await ctx.send("❕ AI Disabled. Enable it first.")
            return

        await self.config.channel(ctx.channel).instructions.set(instructions)
        await ctx.send(f"✅ Channel Instructions Updated:\n```\n{instructions}\n```")

    @ai.command(name="enable", aliases=["e", "on"], description="Enable AI Chat Bot")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.cooldown(rate=1, per=3, type=commands.BucketType.channel)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _ai_enable(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Enable AI Chat Bot"""
        await ctx.typing()
        channel: discord.TextChannel = channel or ctx.channel
        log.debug("channel: %s", channel)
        channels = await self.config.guild(ctx.guild).channels()
        if channel.id not in channels:
            channels.append(channel.id)
            await self.config.guild(ctx.guild).channels.set(channels)
            await self.gen_history(ctx.guild, channel.id)
            await ctx.send(f"✅ AI Chat enabled in {channel.mention}")
        else:
            await ctx.send(f"❕ AI Chat is already enabled in {channel.mention}")

    @ai.command(name="disable", aliases=["d", "off"], description="Disable AI Chat Bot")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.admin_or_can_manage_channel()
    async def _ai_disable(self, ctx: commands.Context, channel: Optional[discord.TextChannel]):
        """Disable AI Chat Bot"""
        await ctx.typing()
        channel: discord.TextChannel = channel or ctx.channel
        log.debug("channel: %s", channel)
        channels = await self.config.guild(ctx.guild).channels()
        if channel.id in channels:
            channels.remove(channel.id)
            await self.config.guild(ctx.guild).channels.set(channels)
            await ctx.send(f"⛔ AI Chat disabled in {channel.mention}")
        else:
            await ctx.send(f"❕ AI Chat is not enabled in {channel.mention}")

    @ai.command(name="status", aliases=["s", "info"], description="AI Chat Bot Status")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    # @commands.admin_or_can_manage_channel()
    async def _ai_status(self, ctx: commands.Context):
        """AI Chat Bot Status"""
        await ctx.typing()
        guild_config: dict = await self.config.guild(ctx.guild).all()
        log.debug("guild_config: %s", guild_config)
        channels = guild_config.get("channels", [])
        log.debug("channels: %s", channels)
        enabled = "✅ Enabled" if ctx.channel.id in channels else "⛔ Disabled"
        model = guild_config.get("model")
        log.debug("model: %s", model)
        channel_config: dict = await self.config.channel(ctx.channel).all()
        log.debug("channel_config: %s", channel_config)
        instructions = channel_config.get("instructions", "No Channel Specific Instructions.")
        log.debug("instructions: %s", instructions)
        history = len(self.channel_histories.get(ctx.channel.id) or [])
        message = (
            f"AI Chat Status for Channel {ctx.channel.mention}\nStatus: {enabled}\n"
            f"Model: {model}\nMessage Count: {history}\nInstructions:\n```\n{instructions}\n```"
        )
        await ctx.send(message)

    ## GUILD MANAGEMENT ##

    @ai.command(name="model", aliases=["m", "models"], description="Get or Set AI Models")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.mod()
    async def _ai_model(self, ctx: commands.Context, model: Optional[str] = None):
        """Get or Set AI Models"""
        log.debug("_ai_model: %s", model)
        await ctx.typing()
        if model:
            model = model.lower()
            models = list(MODEL_PRICING.keys())
            if model in models:
                await self.config.guild(ctx.guild).model.set(model)
                await ctx.send(f"✅ Model Updated: `{model}`")
            else:
                await ctx.send(f"❕ Model must be one of:\n```json\n{pformat(MODEL_PRICING)}\n```")
        else:
            model = await self.config.guild(ctx.guild).model()
            await ctx.send(f"🤖 Current Model: `{model}`\n```json\n{pformat(MODEL_PRICING)}\n```")

    @ai.command(name="channels", aliases=["channel", "enabled", "config"], description="AI Enabled Channels")
    @commands.max_concurrency(1, commands.BucketType.guild)
    @commands.guild_only()
    @commands.mod()
    async def _ai_channels(self, ctx: commands.Context):
        """AI Enabled Channels"""
        await ctx.typing()
        channel_ids = await self.config.guild(ctx.guild).channels()
        log.debug("channel_ids: %s", channel_ids)
        channels = [ctx.guild.get_channel(x) for x in channel_ids]
        log.debug("Channels: %s", channels)
        model = await self.config.guild(ctx.guild).model()
        mentions = cf.humanize_list([c.mention for c in channels]) if channels else "`None`"
        log.debug("mentions: %s", mentions)
        await ctx.send(f"🤖 Enabled in {len(channels)} channels.\nModel: `{model}`\nchannels: {mentions}")

    @staticmethod
    async def send_text(send: Callable, message: str):
        if len(message) < 2000:
            return await send(message)
        else:
            buffer = io.BytesIO(message.encode("utf-8"))
            file = discord.File(buffer, filename="response.txt")
            await send(file=file)

    @staticmethod
    def get_text(data: dict) -> str:
        # output = data.get("output")
        # for out in output:
        #     if out.get("type", "") == "message":
        #         content = out.get("content", [])
        default = "⚠️ I'm Speechless (error)..."
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content.get("text", default)
        return default

    async def openai_responses(self, messages: list, model="gpt-4.1-nano", instructions: Optional[str] = None):
        # log.debug("openai_responses: %s", messages)
        url = "https://api.openai.com/v1/responses"
        data = {
            "model": model,
            # "instructions": f"{self.instructions}\n\n{instructions}".strip(),
            "instructions": "\n\n".join(filter(None, [self.instructions, instructions])),
            "input": messages,
            "max_output_tokens": self.max_tokens,
        }
        if model.startswith("gpt-5"):
            data["service_tier"] = "flex"
        if model.startswith("gpt-5-"):
            data["reasoning"] = {"effort": "minimal"}
        if model.startswith("gpt-5.2-"):
            data["reasoning"] = {"effort": "none"}
        log.debug("request - data: %s", data)
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=self.headers, json=data)
            log.error("r.status_code: %s", r.status_code)
            r.raise_for_status()
        return r.json()

    # async def gemini_response(self, contents: list):
    #     log.debug("gemini_response - contents: %s", len(contents))
    #     headers = {"Content-Type": "application/json", "x-goog-api-key": self.key}
    #     data = {"system_instruction": {"parts": [{"text": self.instructions}]}, "contents": contents}
    #     url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    #     async with httpx.AsyncClient(**self.http_options) as client:
    #         r = await client.post(url=url, headers=headers, json=data)
    #         log.error("r.status_code: %s", r.status_code)
    #         r.raise_for_status()
    #     return r.json()

    # async def append_usage(self, model: str, response: dict, content):
    #     usage = await self.parse_usage(model, response)
    #     if usage:
    #         content += f"\n\n_{usage}_"
    #     return content
    #
    # @staticmethod
    # async def parse_usage(model: str, response: dict):
    #     usage = response.get("usage", {})
    #     log.debug("parse_usage: %s", usage)
    #     if not usage:
    #         return ""
    #     in_t = usage.get("input_tokens", 0)
    #     out_t = usage.get("output_tokens", 0)
    #     if pricing := MODEL_PRICING.get(model):
    #         in_rate, out_rate = pricing
    #         in_cost = in_t * (in_rate / 1_000_000)
    #         out_cost = out_t * (out_rate / 1_000_000)
    #     else:
    #         log.warning("Unknown Model: %s", model)
    #         in_cost = out_cost = 0
    #
    #     tot_cost = in_cost + out_cost
    #     log.debug("in: %s, out: %s, total: %s cost: %s", in_t, out_t, in_t + out_t, tot_cost)
    #     result = ""
    #     if in_t or out_t:
    #         result += f"In: {in_t} / Out: {out_t} / Total: {in_t + out_t} / Cost: ${tot_cost:.5f}"
    #     return result
