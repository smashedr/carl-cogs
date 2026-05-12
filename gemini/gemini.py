import base64
import discord
import httpx
import io
import logging
from typing import Optional, Dict
from collections.abc import Callable

from redbot.core import commands

log = logging.getLogger("red.gemini")


class Gemini(commands.Cog):
    """Carl's Gemini Cog"""

    # model: str = "gpt-4o-mini"  # default model is overridden with set api command
    # max_tokens = 2000
    http_options = {
        "follow_redirects": True,
        "timeout": 30,
    }

    instructions: str = (
        "You are Carl, a Discord bot. Give short answers unless the question genuinely requires detail."
        # "No padding, no filler, no restating the question."
    )

    prompt = (
        "You are an expert geolocation analyst. "
        "Your task is to determine the precise geographic location shown in an image using a systematic, hierarchical chain-of-thought methodology. "
        "A short 2-3 paragraph summary: what you see, what it tells you, and your conclusion. "
        "Give your best guess at a specific location with reasoning. "
        "Provide a GeoHack URL with these example query strings and format: "
        "<https://geohack.toolforge.org/geohack.php?params=47.6601_N_122.3338_W&pagename=United%20States%2C%20Washington%2C%20Seattle> "
    )

    def __init__(self, bot):
        self.bot = bot
        # self.redis: Optional[redis.Redis] = None
        self.key: Optional[str] = None
        self.headers: Optional[Dict[str, str]] = None
        self.msg_geoimage = discord.app_commands.ContextMenu(
            name="GeoImage",
            callback=self.msg_geoimage_callback,
            type=discord.AppCommandType.message,
        )

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
        data: Dict[str, str] = await self.bot.get_shared_api_tokens("gemini")
        log.debug("%s: data: %s", self.__cog_name__, data)
        self.key = data.get("api") or data.get("key") or data.get("token") or data["api_key"]
        log.debug("%s: api_key: %s", self.__cog_name__, self.key)
        # self.model = data.get("model", self.model)
        # log.debug("%s: model: %s", self.__cog_name__, self.model)
        self.headers = {"x-goog-api-key": self.key}

        self.bot.tree.add_command(self.msg_geoimage)
        log.info("%s: Cog Load Finish", self.__cog_name__)

    async def cog_unload(self):
        log.info("%s: Cog Unload", self.__cog_name__)
        self.bot.tree.remove_command("GeoImage", type=discord.AppCommandType.message)

    async def msg_geoimage_callback(self, interaction, message: discord.Message):
        log.debug("msg_geoimage_callback: %s", message)
        log.debug("attachments: %s", message.attachments)
        if not message.attachments:
            return await interaction.response.send_message(
                "❌ Message has no attachments.", ephemeral=True, delete_after=60
            )

        attachment = message.attachments[0]
        log.debug("attachment.content_type: %s", attachment.content_type)
        if not attachment.content_type or not attachment.content_type.startswith("image/"):
            return await interaction.response.send_message(
                f"❌ Attachment not an image: {attachment.content_type}", ephemeral=True, delete_after=60
            )

        await interaction.response.defer()

        image_bytes = await attachment.read()
        response = await self.gemini_img_response(image_bytes, attachment.content_type)
        log.info("response: %s", response)
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        log.info("text: %s", text)

        usage = response.get("usageMetadata", {})
        log.info("usage: %s", usage)
        in_t = usage.get("promptTokenCount", 0)
        out_t = usage.get("candidatesTokenCount", 0)
        tho_t = usage.get("thoughtsTokenCount", 0)
        tot_t = usage.get("totalTokenCount", 0)
        log.info("in: %s, out: %s, thought: %s, total: %s", in_t, out_t, tho_t, tot_t)
        if in_t or out_t or tot_t:
            text = f"{text}\n\n_In: {in_t} / Out: {out_t} / Thought: {tho_t} / Total: {tot_t}_"
        await self.send_text(interaction.followup.send, text)

        # messages = [
        #     {
        #         "role": "user",
        #         "content": [
        #             {"type": "input_text", "text": self.prompt},
        #             {"type": "input_image", "image_url": attachment.url},
        #         ],
        #     }
        # ]
        # log.debug("messages: %s", messages)
        # result = await self.openai_responses(messages, "gpt-4o-mini")
        # log.debug("result: %s", result)
        # output_text = result["output"][0]["content"][0]["text"]
        # log.debug("output_text: %s", output_text)
        # in_t = result["usage"]["input_tokens"]
        # out_t = result["usage"]["output_tokens"]
        # text = f"{output_text}\n\n_Input: {in_t} / Output: {out_t}_"
        # await interaction.followup.send(text)

    # @commands.Cog.listener(name='on_message_without_command')
    # async def on_message_without_command(self, message: discord.Message):
    #     log.debug('on_message_without_command: %s', message)

    @commands.hybrid_command(name="geoimage", aliases=["geo"], description="GeoImage Command")
    async def geoimage_cmd(self, ctx: commands.Context, image: str):
        """GeoImage an <image>"""
        log.debug("geoimage_cmd: %s", image)
        await ctx.send("INOP")

    @commands.hybrid_command(name="gemini", aliases=["g"], description="Gemini Command")
    async def gemini_cmd(self, ctx: commands.Context, *, question: str):
        """Ask Gemini a <question>"""
        log.debug("gemini_cmd: %s", question)
        async with ctx.typing():
            response = await self.gemini_response(question)
            log.debug("response: %s", response)
            text = response["candidates"][0]["content"]["parts"][0]["text"]
            log.info("text: %s", text)
            await self.send_text(ctx.send, text)

    # async def openai_responses(self, messages: List, model: Optional[str] = None):
    #     # log.debug('openai_responses: %s', messages)
    #     url = "https://api.openai.com/v1/responses"
    #     data = {"model": model or self.model, "input": messages, "max_output_tokens": self.max_tokens}
    #     log.debug("data.model: %s", data["model"])
    #     async with httpx.AsyncClient(**self.http_options) as client:
    #         r = await client.post(url=url, headers=self.headers, json=data)
    #         log.error("r.status_code: %s", r.status_code)
    #         log.error("r.text: %s", r.text)
    #         r.raise_for_status()
    #     return r.json()

    async def gemini_response(self, text: str):
        log.debug("gemini_response - text: %s", text)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.key,
        }
        data = {
            "system_instruction": {"parts": [{"text": self.instructions}]},
            "contents": [{"parts": [{"text": text}]}],
        }
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=headers, json=data)
            log.error("r.status_code: %s", r.status_code)
            # log.error("r.text: %s", r.text)
            r.raise_for_status()
        return r.json()

    async def gemini_img_response(self, image_bytes: bytes, mime_type: str):
        log.debug("gemini_img_response - %s bytes, type=%s", len(image_bytes), mime_type)
        log.debug("prompt: %s", self.prompt)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.key,
        }
        base64_string = base64.b64encode(image_bytes).decode("utf-8")
        # image_data = f"data:{mime_type};base64,{base64_string}"
        data = {
            # "system_instruction": { "parts": [{ "text": instructions }] },
            "contents": [
                {"parts": [{"inline_data": {"mime_type": mime_type, "data": base64_string}}, {"text": self.prompt}]}
            ],
        }
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        async with httpx.AsyncClient(**self.http_options) as client:
            r = await client.post(url=url, headers=headers, json=data)
            log.error("r.status_code: %s", r.status_code)
            # log.error("r.text: %s", r.text)
            r.raise_for_status()
        return r.json()

    @staticmethod
    def get_first_url(message: discord.Message) -> Optional[str]:
        log.debug("attachments: %s", message.attachments)
        if message.attachments:
            attachment = message.attachments[0]
            if attachment.url:
                return attachment.url

        if message.embeds:
            embed = message.embeds[0]
            if embed.url:
                return embed.url

        text = message.content
        log.debug("text: %s", text)

    @staticmethod
    async def send_text(send: Callable, message: str):
        if len(message) < 2000:
            return await send(message)
        else:
            buffer = io.BytesIO(message.encode("utf-8"))
            file = discord.File(buffer, filename="response.txt")
            await send(file=file)
