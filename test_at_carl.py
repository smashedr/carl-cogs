"""
Tests for AIChat.at_carl (aichat/aichat.py).

aichat.py cannot be imported here because it depends on `discord` and `redbot`,
which are not installed. Instead the *real* `at_carl` source is pulled straight
out of aichat.py with ast, compiled, and bound to a stub `self`, so these tests
exercise the shipped code rather than a copy of it.

Run:  python -m pytest test_at_carl.py -v
"""

import ast
import re
import types
from pathlib import Path

import pytest

AICHAT_PATH = Path(__file__).parent / "aichat" / "aichat.py"

# Must match AIChat.first_x_words / AIChat.last_x_words in aichat/aichat.py.
FIRST_X_WORDS = 10
LAST_X_WORDS = 6

BOT_ID = 1337


def _load_at_carl():
    """Compile the real at_carl out of aichat.py without importing redbot/discord."""
    tree = ast.parse(AICHAT_PATH.read_text(encoding="utf-8"))
    func = next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "at_carl"),
        None,
    )
    if func is None:
        raise RuntimeError(f"at_carl not found in {AICHAT_PATH}")
    module = ast.Module(body=[func], type_ignores=[])
    ast.fix_missing_locations(module)
    # the signature annotations are evaluated at def time, so `discord` must exist
    discord_stub = types.SimpleNamespace(Message=object, Guild=object, TextChannel=object)
    namespace = {"re": re, "discord": discord_stub}
    exec(compile(module, str(AICHAT_PATH), "exec"), namespace)
    return namespace["at_carl"]


at_carl = _load_at_carl()


class StubSelf:
    first_x_words = FIRST_X_WORDS
    last_x_words = LAST_X_WORDS


class StubMe:
    """Stand-in for discord.Guild.me (the bot's own Member).

    `mentioned_in` is a faithful port of discord.py and is kept only as the
    reference for what at_carl deliberately does NOT use:

      BaseUser.mentioned_in -> True if message.mention_everyone, else True if any
                              user mention id matches self.id.
      Member.mentioned_in  -> additionally True if a role mention is one the
                              member holds.
    Neither of them checks message replies.
    """

    id = BOT_ID

    def __init__(self, role_ids=()):
        self.role_ids = set(role_ids)

    def mentioned_in(self, message):
        if message.mention_everyone:
            return True
        if self.id in {u.id for u in message.mentions}:
            return True
        return bool(self.role_ids & {r.id for r in message.role_mentions})


class StubSnowflake:
    def __init__(self, id):
        self.id = id


class StubGuild:
    def __init__(self, me=None):
        self.me = me or StubMe()


class StubMessage:
    """Mimics the parts of discord.Message that at_carl touches.

    Per discord.py's Message._handle_mentions / _handle_mention_roles /
    mention_everyone, `mentions` holds only <@id> / <@!id> users, role pings go to
    `role_mentions`, and @everyone / @here only set the `mention_everyone` flag.
    """

    def __init__(self, content, guild=StubGuild()):
        self.content = content
        self.guild = guild
        self.mention_everyone = bool(re.search(r"@(?:here|everyone)\b", content))
        self.mentions = [StubSnowflake(int(m)) for m in re.findall(r"<@!?(\d+)>", content)]
        self.role_mentions = [StubSnowflake(int(m)) for m in re.findall(r"<@&(\d+)>", content)]


def check(content, guild=StubGuild()):
    return at_carl(StubSelf(), StubMessage(content, guild=guild))


# (sentence, expected)
MATCHES = [
    # bare / short
    "carl",
    "CARL",
    "Carl!",
    "**carl**",
    # natural address
    "hey carl, what's up",
    "yo carl",
    "carl, tell me a joke",
    "hey carl can you look at this",
    "what do you think carl",
    "carl are you there",
    # punctuation and separators
    "carl-bot is down",
    "carl's dog is cute",
    "- carl",
    "> quoted carl talking",
    'he said "carl" out loud',
    # real user mention of the bot, even with no "carl" word
    "<@1337> hello",
    "hey <@1337> can you help",
    "<@1337> status please",
    # trailing position, past the 16 word window
    "one two three four five six seven eight nine ten eleven twelve carl",
    # link stripped but the word survives in prose
    "sup carl https://example.com/carl-is-cool",
    # markup stripped, real word survives
    "<@1337> <t:1337> carl wake up",
    # domain stripped but the word survives in prose
    "email carl@example.com when you get a sec",
    # substring matching does not leak into neighbouring names
    "Scarlett and Carl are in the meeting",
    # DM: guild is None
    ("carl hello", None),
    # nickname-ish
    "hey Carl-bot status",
]

NON_MATCHES = [
    # no mention of carl at all
    "",
    "hey there, how are you doing today my friend",
    "the weather is nice",
    # substring, not the word
    "carolina is a beautiful state",
    "carlsbad weather report",
    "scarlett is streaming tonight",
    "carla is in the meeting",
    "concrete is grey",
    # inside code
    "hey `carl` can you help",
    "```\ncarl\n```",
    "print(1)",
    "```python\nimport carl\n```",
    # middle of a long message, outside first 10 and last 6
    "one two three four five six seven eight nine ten eleven carl twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty",
    # role pings, whether or not the bot holds the role
    "<@&9999> standup time",
    # @here / @everyone must not trigger Carl
    "hey @everyone important announcement",
    "@here standup in 5",
    # domain shaped text that merely contains "carl"
    "check www.carl.com out",
    "is carl.com down",
    "https://carl.example.com/docs",
    "go to carl.io/carl",
    "see file carl.txt for details",
    "version 2.10 released",
    "the U.S.A is big",
    "i.e. that is not a domain",
]

# (sentence, expected, note, guild)
EDGE_CASES = [
    (
        "<@&1337> standup time",
        False,
        "REGRESSION GUARD: discord.py Member.mentioned_in is True when a role the bot "
        "holds is mentioned; at_carl must ignore role pings",
        StubGuild(StubMe(role_ids=[1337])),
    ),
    (
        "hey @here important announcement",
        False,
        "REGRESSION GUARD: discord.py BaseUser.mentioned_in is True on "
        "message.mention_everyone; at_carl must ignore @here/@everyone",
        None,
    ),
    (
        "hey @everyone standup time",
        False,
        "REGRESSION GUARD: same, for @everyone",
        None,
    ),
    (
        "he said carl@ in passing",
        True,
        "NOTE: a bare email-like local part still counts as addressing Carl",
        None,
    ),
    (
        "my_carl_bot_is_cool",
        True,
        r"NOTE: [^\W_]+ splits on underscore, so snake_case names match",
        None,
    ),
    (
        "unclosed ```carl``` fence",
        False,
        "NOTE: the ```.*?``` alternative strips a stray leading fence",
        None,
    ),
    (
        "c@rl are you there",
        False,
        "NOTE: leetspeak obfuscation is not matched",
        None,
    ),
    (
        "version 3.14 released, carl should know",
        True,
        "NOTE: the domain alternative also eats dotted numbers like 3.14, which is "
        "harmless because the real word is what matters",
        None,
    ),
    (
        "Hi Carl.Also a question",
        False,
        "TRADEOFF: a dot-glued token is treated as a domain and stripped, so an "
        "address written with no space after the period is missed. Matching a real "
        "TLD list would fix it at the cost of a much larger pattern.",
        None,
    ),
    (
        "carl",
        True,
        "NOTE: DM (guild is None) must not raise on message.guild.me",
        None,
    ),
]


@pytest.mark.parametrize("case", MATCHES)
def test_matches(case):
    content, guild = case if isinstance(case, tuple) else (case, StubGuild())
    assert check(content, guild=guild) is True, f"expected at_carl({content!r}) to be True"


@pytest.mark.parametrize("content", NON_MATCHES)
def test_non_matches(content):
    assert check(content) is False, f"expected at_carl({content!r}) to be False"


@pytest.mark.parametrize("content,expected,note,guild", EDGE_CASES)
def test_edge_cases(content, expected, note, guild):
    assert check(content, guild=guild or StubGuild()) is expected, note


def test_mention_of_someone_else_does_not_trigger():
    """<@9999> is a different user and is stripped from the text, so nothing matches."""
    assert check("<@9999> status please") is False


def test_bot_mention_still_triggers():
    """<@1337> must match even though the markup is stripped from the text."""
    assert check("<@1337> status please") is True


def test_returns_real_bool():
    assert isinstance(check("carl"), bool)
    assert isinstance(check("nope"), bool)


def test_window_constants_match_cog():
    """Guard against the stub drifting away from the real class attributes."""
    source = AICHAT_PATH.read_text(encoding="utf-8")
    assert f"first_x_words = {FIRST_X_WORDS}" in source
    assert f"last_x_words = {LAST_X_WORDS}" in source