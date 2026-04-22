"""Constants for the Samsung Soundbar integration."""

from enum import StrEnum

DOMAIN = "samsung_soundbar"

# ── Config entry keys ────────────────────────────────────────────────
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "device_name"
CONF_MAX_VOLUME = "max_volume"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRES_AT = "token_expires_at"

# ── Feature toggles (options flow) ───────────────────────────────────
OPT_ENABLE_SOUNDMODE = "enable_soundmode"
OPT_ENABLE_EQ = "enable_eq"
OPT_ENABLE_ADVANCED_AUDIO = "enable_advanced_audio"
OPT_ENABLE_WOOFER = "enable_woofer"

# ── SmartThings API ──────────────────────────────────────────────────
ST_API_BASE = "https://api.smartthings.com/v1"
ST_TOKEN_URL = "https://api.smartthings.com/oauth/token"
ST_AUTHORIZE_URL = "https://api.smartthings.com/oauth/authorize"

# ── OCF endpoint hrefs ──────────────────────────────────────────────
HREF_SOUNDMODE = "/sec/networkaudio/soundmode"
HREF_ADVANCED_AUDIO = "/sec/networkaudio/advancedaudio"
HREF_WOOFER = "/sec/networkaudio/woofer"
HREF_EQ = "/sec/networkaudio/eq"
HREF_CHANNEL_VOLUME = "/sec/networkaudio/channelVolume"
HREF_SURROUND_SPEAKER = "/sec/networkaudio/surroundspeaker"
HREF_ACTIVE_VOICE_AMP = "/sec/networkaudio/activeVoiceAmplifier"
HREF_SPACEFIT_SOUND = "/sec/networkaudio/spacefitSound"

# ── OCF property keys ───────────────────────────────────────────────
PROP_SOUNDMODE = "x.com.samsung.networkaudio.soundmode"
PROP_SUPPORTED_SOUNDMODE = "x.com.samsung.networkaudio.supportedSoundmode"
PROP_NIGHTMODE = "x.com.samsung.networkaudio.nightmode"
PROP_VOICE_AMP = "x.com.samsung.networkaudio.voiceamplifier"
PROP_BASS_BOOST = "x.com.samsung.networkaudio.bassboost"
PROP_WOOFER = "x.com.samsung.networkaudio.woofer"
PROP_WOOFER_CONNECTION = "x.com.samsung.networkaudio.connection"
PROP_EQ_NAME = "x.com.samsung.networkaudio.EQname"
PROP_EQ_SUPPORTED = "x.com.samsung.networkaudio.supportedList"
PROP_EQ_ACTION = "x.com.samsung.networkaudio.action"
PROP_EQ_BANDS = "x.com.samsung.networkaudio.EQband"
PROP_CHANNEL_VOLUME = "x.com.samsung.networkaudio.channelVolume"
PROP_REAR_POSITION = "x.com.samsung.networkaudio.currentRearPosition"
PROP_ACTIVE_VOICE_AMP = "x.com.samsung.networkaudio.activeVoiceAmplifier"
PROP_SPACEFIT_SOUND = "x.com.samsung.networkaudio.spacefitSound"

# ── Polling ──────────────────────────────────────────────────────────
DEFAULT_POLL_INTERVAL = 30  # seconds
TOKEN_REFRESH_BUFFER = 300  # refresh 5 min before expiry


# ── Enums ────────────────────────────────────────────────────────────
class SpeakerChannel(StrEnum):
    """Individual speaker channels for per-speaker volume."""

    CENTER = "Spk_Center"
    SIDE = "Spk_Side"
    WIDE = "Spk_Wide"
    FRONT_TOP = "Spk_Front_Top"
    REAR = "Spk_Rear"
    REAR_TOP = "Spk_Rear_Top"


class RearSpeakerMode(StrEnum):
    """Rear speaker positioning mode."""

    FRONT = "Front"
    REAR = "Rear"
