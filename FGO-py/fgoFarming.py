from fgoLogging import getLogger

logger=getLogger("Farming")

def farming():
    """Return extra idle seconds, or None when no farming task is scheduled."""
    logger.warning('No farming now')
    return None
