import datetime
import base64
import json

from aries_cloudagent.core.profile import Profile
from redis.asyncio import RedisCluster
from redis.exceptions import RedisError
from  typing import Union, List

def str_to_datetime(datetime_str):
    return datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M:%SZ")


def curr_datetime_to_str():
    return (datetime.datetime.now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_timedelta_seconds(rec_datetime):
    datetime_now = str_to_datetime(curr_datetime_to_str())
    timedelta_seconds = datetime_now - rec_datetime
    return timedelta_seconds.total_seconds()

def b64_to_bytes(val: Union[str, bytes], urlsafe=True) -> bytes:
    """Convert a base 64 string to bytes."""
    if isinstance(val, str):
        val = val.encode("ascii")
    if urlsafe:
        missing_padding = len(val) % 4
        if missing_padding:
            val += b"=" * (4 - missing_padding)
        return base64.urlsafe_b64decode(val)
    return base64.b64decode(val)

def _recipients_from_packed_message(packed_message: bytes) -> List[str]:
    """
    Inspect the header of the packed message and extract the recipient key.
    """
    try:
        wrapper = json.loads(packed_message)
    except Exception as err:
        raise ValueError("Invalid packed message") from err

    recips_json = b64_to_bytes(wrapper["protected"], urlsafe=True).decode("ascii")
    try:
        recips_outer = json.loads(recips_json)
    except Exception as err:
        raise ValueError("Invalid packed message recipients") from err

    return [recip["header"]["kid"] for recip in recips_outer["recipients"]]