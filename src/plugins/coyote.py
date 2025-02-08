from src.hardware.dg_audio_adapter import DGAudioAdapter


def init_coyote(player, logger):
    """Initialize the Coyote module.

    Args:
        player: The central audio player component.
        logger: A logger instance.

    Returns:
        An instance of DGAudioAdapter representing the optional Coyote module.
    """
    logger.info("Initializing Coyote module...")
    return DGAudioAdapter(player, logger) 