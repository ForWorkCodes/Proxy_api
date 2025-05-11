from aiocache import Cache
from aiocache.serializers import JsonSerializer

cache = Cache(
    Cache.MEMORY,  # или REDIS, если надо
    serializer=JsonSerializer(),
    ttl=600  # 10 minutes
)