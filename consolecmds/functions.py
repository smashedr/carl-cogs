import asyncio
from ping3 import ping


async def verbose_ping(dest_addr: str, count: int = 4, interval: float = 0, *args, **kwargs):
    """
    Send pings to destination address with the given timeout and display the result.

    Args:
        dest_addr: The destination address. Ex. "192.168.1.1"/"example.com"
        count: How many pings should be sent. 0 means infinite loops until manually stopped. Default is 4, same as Windows CMD. (default 4)
        interval: How many seconds between two packets. Default is 0, which means send the next packet as soon as the previous one responsed. (default 0)
        *args and **kwargs: And all the other arguments available in ping() except `seq`.

    Returns:
        Formatted ping results printed.
    """
    timeout = kwargs.get("timeout")
    src = kwargs.get("src_addr")
    unit = kwargs.setdefault("unit", "ms")
    i = 0
    while i < count or count == 0:
        if interval > 0 and i > 0:
            await asyncio.sleep(interval)
        output_text = "ping '{}'".format(dest_addr)
        output_text += " from '{}'".format(src) if src else ""
        output_text += " ... "
        delay = ping(dest_addr, seq=i, *args, **kwargs)
        print(output_text, end="")
        if delay is None:
            print("Timeout > {}s".format(timeout) if timeout else "Timeout")
        elif delay is False:
            print("Error")
        else:
            print("{value}{unit}".format(value=int(delay), unit=unit))
        i += 1

