"""Redis Convenience classes
"""
import json
import logging
import time

import redis

from redis.connection import SERVER_CLOSED_CONNECTION_ERROR


# Maximum time to wait for the Redis server to respond.
REDIS_MAX_WAIT = 60


class RedisChannelSubscriberError(Exception):
    pass


class RedisChannelSubscriber:
    """RedisChannelSubscriber - encapsulate semantic behaviors we require as a
    subscriber of a pub/sub Redis channel.
    """

    ONLYONE = "only-one"
    ONEOFMANY = "one-of-many"
    CHANNEL_TYPES = frozenset((ONLYONE, ONEOFMANY))

    def __init__(self, redis_server, channel_name, channel_type=ONLYONE):
        """RedisChannelSubscriber constructor - responsible for setting up the
        subscription to the given channel name, and verifying the subscription
        worked properly.

        :redis_server: - The Redis() server client object
        :channel_name: - The name of the channel to subscribe to
        :channel_type: - Can be either ONLYONE or ONEOFMANY, indicating how
                         many subscribers to expect on the channel.
        """
        self.channel_name = channel_name
        assert (
            channel_type in self.CHANNEL_TYPES
        ), f"unexepcted channel_type, {channel_type}"

        # Setup the Redis server channel subscription
        timeout = time.time() + REDIS_MAX_WAIT
        redis_connection_state = "connecting"
        self._pubsub = redis_server.pubsub()
        while redis_connection_state == "connecting":
            try:
                self._pubsub.subscribe(channel_name)
                channel = self._pubsub.listen()
                # Pull off first message which is an acknowledgement we have
                # successfully subscribed.
                resp = next(channel)
            except redis.ConnectionError:
                if time.time() > timeout:
                    raise
                time.sleep(0.1)
            else:
                redis_connection_state = "connected"
        self.channel = channel
        if resp["type"] != "subscribe":
            raise RedisChannelSubscriberError(f"bad type: {resp!r}")
        if resp["pattern"] is not None:
            raise RedisChannelSubscriberError(f"bad pattern: {resp!r}")
        if resp["channel"].decode("utf-8") != self.channel_name:
            raise RedisChannelSubscriberError(f"bad channel: {resp!r}")
        if channel_type == "only-one":
            if resp["data"] != 1:
                raise RedisChannelSubscriberError(f"bad data: {resp!r}")
        else:
            assert channel_type == "one-of-many"
            if resp["data"] < 1:
                raise RedisChannelSubscriberError(f"bad data: {resp!r}")

    def fetch_message(self, logger):
        """fetch_message - generator for pulling messages off the subscribed
        channel.

        The message payload is returned as proper UTF-8 string object.  Any
        errors encountered processing the received payload are logged, but
        otherwise ignored.  A dropped connection to the Redis server will be
        logged, and terminate the generator normally.

        Yields a string representing the received message.
        """
        try:
            logger.debug("next %s", self.channel_name)
            for payload in self.channel:
                logger.debug("payload from %s: %r", self.channel_name, payload)
                if payload["channel"].decode("utf-8") != self.channel_name:
                    logger.error(
                        "Payload from %s has unexpected channel, %r",
                        self.channel_name,
                        payload,
                    )
                    continue
                if payload["pattern"] is not None:
                    logger.debug(
                        "unexpected pattern in payload on channel %s, %r",
                        self.channel_name,
                        payload,
                    )
                if payload["type"] == "unsubscribe":
                    if payload["data"] != 0:
                        logger.debug(
                            "unexpected data value in payload on channel %s, %r",
                            self.channel_name,
                            payload,
                        )
                    break
                if payload["type"] != "message":
                    logger.error(
                        "Ignoring non-message types in payload on channel %s, %r",
                        self.channel_name,
                        payload,
                    )
                    continue
                try:
                    message = payload["data"].decode("utf-8")
                except Exception:
                    logger.warning(
                        "Data payload in message not UTF-8 on channel %s, %r",
                        self.channel_name,
                        payload,
                    )
                else:
                    logger.debug("channel %s payload, %r", self.channel_name, message)
                    yield message
                logger.debug("next %s", self.channel_name)
        except redis.ConnectionError as exc:
            try:
                msg = exc.args[0]
            except Exception:
                msg = ""
            if msg.startswith(SERVER_CLOSED_CONNECTION_ERROR):
                # Redis disconnected, shutdown as gracefully as possible.
                # FIXME: Consider adding connection drop error handling, retry loop
                # re-establishing a connection, etc..
                self._pubsub = None
                logger.error(
                    "lost connection to redis server on channel %s", self.channel_name
                )
            else:
                raise

    def fetch_json(self, logger):
        """fetch_json - a simple wrapper around fetch_message() to decode the
        string as a JSON document.

        If the message is not valid JSON a warning is logged, and the message
        is ignored.

        Yields a JSON document.
        """
        for json_str in self.fetch_message(logger):
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                logger.warning(
                    "data payload in message not JSON on channel %s, '%s'",
                    self.channel_name,
                    json_str,
                )
            else:
                yield data

    def unsubscribe(self):
        """unsubscribe - unsubscribes from the channel, leaving the pub/sub
        object alone.
        """
        if self._pubsub is not None:
            self._pubsub.unsubscribe()

    def close(self):
        """close - unsubscribes from the channel, and closes the pub/sub object.
        """
        if self._pubsub is not None:
            self._pubsub.unsubscribe()
            self._pubsub.close()


class RedisHandler(logging.Handler):
    """Publish messages to a given channel on a Redis server.
    """

    def __init__(
        self,
        channel,
        hostname=None,
        redis_client=None,
        level=logging.NOTSET,
        **redis_kwargs,
    ):
        """Create a new logger for the given channel and redis_client.
        """
        super().__init__(level)
        self.channel = channel
        self.hostname = hostname
        self.redis_client = redis_client or redis.Redis(**redis_kwargs)
        self.counter = 0
        self.errors = 0
        self.redis_errors = 0
        self.dropped = 0

    def emit(self, record):
        """Publish record to redis logging channel
        """
        try:
            formatted_record = self.format(record)
            num_present = self.redis_client.publish(
                self.channel, f"{self.hostname} {self.counter:04d} {formatted_record}"
            )
        except redis.RedisError:
            self.redis_errors += 1
        except Exception:
            self.errors += 1
        else:
            if num_present == 0:
                self.dropped += 1
        finally:
            self.counter += 1


def wait_for_conn_and_key(redis_server: redis.Redis, key: str, prog: str) -> str:
    """wait_for_conn_and_key - convenience method of both the Tool Meister and
    the Tool Data Sink to startup and wait for an initial connection to the
    Redis server, and for the expected key to show up.

    Arguments:

        redis_server: a Redis client object
        key: the key name as a string
        prog: the program name of our caller

    Returns the payload value of the key as a string.

    If successful on the first connection attempt, and the value of the key is
    retrieved, no messages are issued on stdout.  If the key does not exist yet,
    we'll report the missing key every 10 seconds from the last successful
    connection.

    If on the first connection attempt the connection to the Redis server fails,
    we emit a message to that effect, once.  After that, we'll report each time
    we are disconnected or re-connected to the Redis server.
    """
    # Loop waiting for the key to show up.
    connected = None
    payload = None
    attempts = 0
    errors = 0
    missing = 0
    while payload is None:
        attempts += 1
        try:
            payload = redis_server.get(key)
        except redis.ConnectionError:
            errors += 1
            # Reset the missing count if we get disconnected
            missing = 0
            if connected is None:
                # Only emit this message once for the initial attempt.
                print(
                    f"{prog}: waiting to connect to Redis server {redis_server}",
                    flush=True,
                )
                connected = False
            elif connected:
                # We always report disconnections.
                print(
                    f"{prog}: disconnected from Redis server {redis_server}",
                    flush=True,
                )
                connected = False
            time.sleep(1)
        else:
            if connected is False:
                # We always report re-connections (connections was not None).
                print(
                    f"{prog}: connected to Redis server {redis_server}", flush=True,
                )
            connected = True
            if payload is None:
                missing += 1
                if (missing % 10) == 0:
                    # Only emit missing key notice every 10 seconds
                    print(f"{prog}: key '{key}' does not exist yet", flush=True)
                time.sleep(1)

    if attempts > 1:
        # Always report stats if it took multiple attempts.
        print(
            f"{prog}: connected to Redis server after {attempts:d}"
            f" attempts (with {errors:d} error(s))",
            flush=True,
        )

    return payload.decode("utf-8")
