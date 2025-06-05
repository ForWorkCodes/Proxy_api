from fastapi import APIRouter, HTTPException, Query
from app.core.config import settings
from app.core.cache import cache
import httpx
from typing import Optional
import logging
import os
from datetime import datetime
from app.core.constants import PROXY_TYPE_MAPPING

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
log_filename = f'logs/proxy_api_{datetime.now().strftime("%Y%m%d")}.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()  # This will keep console output as well
    ]
)
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/countries")
async def get_countries(version: Optional[str] = Query(None, description="Proxy version: ipv4, ipv6, or ipv4shared")):
    logger.info(f"Received request for countries with version: {version}")
    
    cache_key = f"proxy:countries:{version if version else 'default'}"
    cached = await cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for version: {version}")
        return cached

    params = {}
    if version:
        if version not in PROXY_TYPE_MAPPING:
            logger.error(f"Invalid proxy version received: {version}")
            raise HTTPException(status_code=400, detail=f"Invalid proxy version. Must be one of: {', '.join(PROXY_TYPE_MAPPING.keys())}")
        params["version"] = PROXY_TYPE_MAPPING[version]

    api_url = f"{settings.PROXY_API_URL}/{settings.PROXY_API_KEY}/getcountry"
    logger.info(f"Making request to proxy API: {api_url} with params: {params}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Received response from proxy API: {data}")
        except httpx.HTTPError as e:
            logger.error(f"Proxy API error: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")

    if data.get("status") != "yes":
        error_msg = f"Proxy API returned error: {data.get('error')}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    await cache.set(cache_key, data['list'])
    logger.info(f"Successfully cached and returning countries list for version: {version}")
    return data['list']


@router.get("/availability")
async def check_availability(
    version: str = Query(..., description="Proxy version: ipv4, ipv6, or ipv4shared"),
    country: str = Query(..., description="2-letter country code"),
    quantity: int = Query(..., description="Requested quantity of proxies")
):
    logger.info(f"Checking availability: version={version}, country={country}, quantity={quantity}")

    if version not in PROXY_TYPE_MAPPING:
        logger.error(f"Invalid proxy version received: {version}")
        raise HTTPException(status_code=400, detail=f"Invalid proxy version. Must be one of: {', '.join(PROXY_TYPE_MAPPING.keys())}")

    version = PROXY_TYPE_MAPPING[version]
    api_url = f"{settings.PROXY_API_URL}/{settings.PROXY_API_KEY}/getcount"
    params = {"country": country.lower(), "version": version}
    cache_key = f"proxy:availability:{version}:{country}"

    cached = await cache.get(cache_key)
    if cached:
        logger.info(f"Cache hit for availability {cache_key}")
        available_quantity = int(cached)
        return {
            "available": available_quantity >= quantity,
            "available_quantity": available_quantity
        }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
            logger.info(f"Response from proxy API: {data}")
        except httpx.HTTPError as e:
            logger.error(f"Proxy API error: {str(e)}")
            raise HTTPException(status_code=502, detail=f"Proxy error: {str(e)}")

    if data.get("status") != "yes":
        error_msg = f"Proxy API returned error: {data.get('error')}"
        logger.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)

    available_quantity = data.get("count", 0)
    is_available = available_quantity >= quantity

    await cache.set(cache_key, str(available_quantity), ttl=10)
    logger.info(f"Cached availability: {cache_key} -> {available_quantity} (10s)")

    return {
        "available": is_available,
        "available_quantity": available_quantity
    }
