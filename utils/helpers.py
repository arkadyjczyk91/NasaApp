def shorten_url(url, maxlen=46):
    """Shorten a URL string for display purposes."""
    if len(url) <= maxlen:
        return url
    return url[:maxlen//2-2] + "..." + url[-maxlen//2+2:]