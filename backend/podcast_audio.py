import os

from podcast_drivers import ElevenLabsPodcastAudioDriver, PodcastAudioDriver


def get_podcast_audio_driver() -> PodcastAudioDriver:
    driver_name = (os.getenv("PODCAST_AUDIO_DRIVER") or "elevenlabs").lower()
    if driver_name == "elevenlabs":
        return ElevenLabsPodcastAudioDriver()
    raise RuntimeError(f"unsupported_podcast_audio_driver:{driver_name}")
