import requests
import logging

logger = logging.getLogger(__name__)

def fetch_as_markdown(url: str) -> str | None:
    """
    Fetches a URL and converts its content to Markdown using an external service.

    Args:
        url: The URL of the webpage to convert.

    Returns:
        The Markdown content as a string, or None if the conversion fails.
    """
    service_url = "https://urltomarkdown.herokuapp.com/"
    params = {'url': url, 'links': 'true'} # Ensure links are included
    
    try:
        response = requests.get(service_url, params=params, timeout=45)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        logger.info(f"Successfully converted {url} to markdown.")
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to convert {url} to markdown. Error: {e}")
        return None
