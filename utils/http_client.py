import requests
from typing import Optional
import time
import logging

logger = logging.getLogger(__name__)

def make_api_request(api_url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> requests.Response:
    """Make API request with improved error handling and retries"""
    session = requests.Session()
    retries = 3
    backoff_factor = 0.5

    for attempt in range(retries):
        try:
            # First try - fast attempt
            if attempt == 0:
                response = session.get(
                    api_url,
                    params=params,
                    timeout=1,
                    allow_redirects=False
                )
                response.raise_for_status()
                return response

            # Subsequent retries - more robust attempt
            headers = headers or {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
            }
            
            # Add exponential backoff delay
            time.sleep(backoff_factor * (2 ** attempt))
            
            response = session.get(
                api_url,
                params=params,
                headers=headers,
                timeout=10,
                allow_redirects=True,
                verify=True
            )
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:  # Last attempt
                raise
            logger.warning(f"Request failed (attempt {attempt + 1}/{retries}): {str(e)}")
            continue
