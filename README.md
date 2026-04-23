# ha-samsung-soundbar

A Home Assistant custom integration for Samsung soundbars (HW-Q990D, Q990C, Q930D, and others) via the SmartThings API.

Built from scratch, combining the best of:
- **[homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar)** -- OAuth token management, robust API client, debounced commands
- **[YASSI](https://github.com/samuelspagl/ha_samsung_soundbar)** -- equalizer, per-speaker volume, Space Fit Sound, media info

Modernized for current Home Assistant standards (DataUpdateCoordinator, CoordinatorEntity, proper config flow).

## Features

### Media Player
- **Power** -- on/off control via SmartThings switch capability
- **Volume** -- set, step up/down, mute/unmute with optimistic UI updates
- **Input source** -- HDMI, Bluetooth, Wi-Fi, optical, and more
- **Sound mode** -- Adaptive, Standard, Surround, Game, etc. (dynamic based on device)
- **Media transport** -- play, pause, stop with optimistic state updates
- **Track control** -- next/previous track via `mediaTrackControl` (dynamically shown only if your device supports it)
- **Media info** -- title, artist, elapsed time, and duration from `audioTrackData`
- **Progress bar** -- media position tracking in the HA media player card

### Play Media / TTS
- **TTS announcements** -- send text-to-speech audio to your soundbar from any HA TTS service
- **Play URL** -- play any audio URL directly on the soundbar
- **Smart playback modes** -- automatically chooses the right SmartThings `audioNotification` command:
  - `playTrackAndRestore` for announcements (restores volume after)
  - `playTrackAndResume` for music (resumes previous track after)
  - `playTrack` as a generic fallback

### Audio Controls
- **Advanced audio switches** -- Night Mode, Voice Amplifier, Bass Boost, Active Voice Amplifier, Space Fit Sound
- **Woofer level** -- number entity with -6 to +6 dB slider
- **Equalizer** -- EQ preset selector (optional, toggled in integration options)
- **Per-speaker volume** -- service call to adjust individual channels (center, side, rear, etc.)
- **Rear speaker mode** -- service call to switch rear speakers between front/rear positioning

### Presets & Calibration
- **Apply preset** -- set sound mode, EQ, night mode, and woofer level atomically in a single service call
- **SpaceFit calibration** -- button entity that triggers the soundbar's room calibration process

### Standalone Entities
- **Sound mode select** -- standalone select entity for dashboards and automations
- **EQ preset select** -- standalone select entity (optional)
- **Input source select** -- standalone select entity
- **Volume sensor** -- raw volume level as a sensor for automations

### Discovery & Automation
- **Zeroconf discovery** -- HA automatically detects Samsung soundbars on your local network
- **Device triggers** -- build automations in the HA UI without knowing entity IDs (sound mode changed, playback started/paused/stopped, night mode toggled, input source changed)

### Quality & Reliability
- **Rate-limit handling** -- automatic retry with exponential backoff and `Retry-After` header support for SmartThings 429 responses
- **OCF read serialization** -- per-device locking prevents interleaved OCF execute/status reads
- **Optimistic updates** -- UI updates immediately on commands without waiting for the next poll
- **Diagnostics** -- downloadable diagnostics with redacted credentials for bug reporting
- **Translations** -- full English translation coverage for config flow, options, services, and entities
- **Test suite** -- config flow and coordinator tests for development and CI

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Samsung Soundbar" and install
3. Restart Home Assistant

### Manual

Copy the `custom_components/samsung_soundbar` folder to your Home Assistant `custom_components` directory.

## Setup

### Authentication Options

This integration supports three ways to authenticate with SmartThings:

| Method | Token Lifetime | Auto-refresh | Best for |
| --- | --- | --- | --- |
| OAuth via Developer Workspace | 24h (refreshable) | Yes | Most users |
| OAuth via SmartThings CLI | 24h (refreshable) | Yes | Technical users, faster setup |
| Personal Access Token (PAT) | 24h | No | Quick testing |

### Option 1: OAuth via Developer Workspace

1. Go to the [Samsung Developer Workspace](https://smartthings.developer.samsung.com/workspace/projects)
2. Create a new project, then select **Partner managed OAuth2**
3. Set the redirect URI to `https://api.smartthings.com/oauth/callback`
4. Request scopes: `r:devices:*`, `x:devices:*`, `r:locations:*`
5. Note your **Client ID** and **Client Secret**

### Option 2: OAuth via SmartThings CLI (faster)

If you have Node.js installed, the SmartThings CLI can create an OAuth app in one command:

```bash
# Install the CLI
npm install -g @smartthings/cli

# Log in to your Samsung account
smartthings login

# Create an OAuth app with the required scopes
smartthings apps:oauth:generate \
  --client-name "HA Soundbar" \
  --scope "r:devices:* x:devices:* r:locations:*" \
  --redirect-uri "https://api.smartthings.com/oauth/callback"
```

This prints your **Client ID** and **Client Secret** directly in the terminal. No web UI needed.

You can also use the CLI to verify your soundbar is visible:

```bash
# List all devices on your account
smartthings devices

# Get detailed status of a specific device
smartthings devices:status <device-id>

# See what capabilities your soundbar exposes
smartthings devices:capabilities <device-id>
```

This is useful for debugging if the integration can't find your soundbar or if certain features don't work on your model.

### Option 3: Personal Access Token (quick testing)

Generate a token at [SmartThings Tokens](https://account.smartthings.com/tokens) with the following scopes enabled:
- **Devices**: List all devices, See all devices, Control all devices
- **Locations**: See all locations

PATs expire after 24 hours and cannot be automatically refreshed. Use OAuth for permanent setups.

### Adding the Integration

**Automatic discovery:** If your soundbar is on the same network, HA may discover it automatically and prompt you to set it up.

**Manual setup:**
1. Go to **Settings > Devices & Services > Add Integration**
2. Search for "Samsung Soundbar"
3. Choose OAuth (recommended) or Personal Access Token
4. For OAuth: enter your Client ID and Client Secret, then follow the authorization flow
5. Select your soundbar from the discovered devices
6. Optionally adjust the max volume slider range

### Feature Toggles

After setup, go to the integration options to enable/disable feature groups:
- Sound Mode selector
- Advanced Audio switches (Night Mode, Voice Amplifier, Bass Boost)
- Woofer level control
- Equalizer preset selector (off by default)

Disabling a feature group skips its OCF endpoint polling, reducing API load. Changes take effect immediately (no restart required).

## Services

### `samsung_soundbar.apply_preset`

Set multiple audio settings atomically in a single call. Only provided fields are changed.

```yaml
# Movie night preset
service: samsung_soundbar.apply_preset
data:
  sound_mode: surround
  night_mode: true
  woofer_level: 3

# Music preset
service: samsung_soundbar.apply_preset
data:
  sound_mode: "adaptive sound"
  eq_preset: Music
  night_mode: false
  woofer_level: 0
```

### `samsung_soundbar.set_speaker_level`

Adjust individual speaker channel volume.

```yaml
service: samsung_soundbar.set_speaker_level
data:
  speaker_channel: Spk_Center  # Spk_Center, Spk_Side, Spk_Wide, Spk_Front_Top, Spk_Rear, Spk_Rear_Top
  level: 3  # -6 to +6 dB
```

### `samsung_soundbar.set_rear_speaker_mode`

Switch rear speakers between front and rear positioning.

```yaml
service: samsung_soundbar.set_rear_speaker_mode
data:
  mode: Rear  # Front or Rear
```

### Play Media / TTS

```yaml
# TTS announcement (doorbell, alarm, etc.)
service: tts.speak
target:
  entity_id: media_player.soundbar
data:
  message: "Someone is at the front door"

# Play a URL
service: media_player.play_media
target:
  entity_id: media_player.soundbar
data:
  media_content_type: music
  media_content_id: "https://example.com/doorbell.mp3"

# Announcement with custom volume
service: media_player.play_media
target:
  entity_id: media_player.soundbar
data:
  media_content_type: music
  media_content_id: "https://example.com/alert.mp3"
  announce: true
  extra:
    volume: 50
```

## How It Works

This integration talks directly to the SmartThings REST API using both standard capabilities and undocumented OCF `execute` capability endpoints. No dependency on `pysmartthings`.

### Standard SmartThings Capabilities

| Feature | Capability | Commands |
| --- | --- | --- |
| Power | `switch` | `on`, `off` |
| Volume | `audioVolume` | `setVolume`, `volumeUp`, `volumeDown` |
| Mute | `audioMute` | `mute`, `unmute` |
| Input Source | `samsungvd.audioInputSource` | `setInputSource` |
| Media Playback | `mediaPlayback` | `play`, `pause`, `stop` |
| Track Control | `mediaTrackControl` | `nextTrack`, `previousTrack` |
| TTS / Play Media | `audioNotification` | `playTrack`, `playTrackAndRestore`, `playTrackAndResume` |
| Media Info | `audioTrackData` | (read-only) title, artist, elapsed, total |

### Samsung OCF Endpoints (via `execute` capability)

| Feature | OCF Endpoint | Property |
| --- | --- | --- |
| Sound Mode | `/sec/networkaudio/soundmode` | `x.com.samsung.networkaudio.soundmode` |
| Night Mode | `/sec/networkaudio/advancedaudio` | `x.com.samsung.networkaudio.nightmode` |
| Voice Amplifier | `/sec/networkaudio/advancedaudio` | `x.com.samsung.networkaudio.voiceamplifier` |
| Bass Boost | `/sec/networkaudio/advancedaudio` | `x.com.samsung.networkaudio.bassboost` |
| Woofer | `/sec/networkaudio/woofer` | `x.com.samsung.networkaudio.woofer` |
| Equalizer | `/sec/networkaudio/eq` | `x.com.samsung.networkaudio.EQname` |
| Channel Volume | `/sec/networkaudio/channelVolume` | `x.com.samsung.networkaudio.channelVolume` |
| Rear Speaker | `/sec/networkaudio/surroundspeaker` | `x.com.samsung.networkaudio.currentRearPosition` |
| Active Voice Amp | `/sec/networkaudio/activeVoiceAmplifier` | `x.com.samsung.networkaudio.activeVoiceAmplifier` |
| Space Fit Sound | `/sec/networkaudio/spacefitSound` | `x.com.samsung.networkaudio.spacefitSound` |

### Polling Strategy

OCF endpoints are polled one at a time on a rotating basis to avoid SmartThings rate limiting. A full OCF refresh takes approximately 2 minutes (with a 30-second poll interval and 3-4 enabled OCF targets). Standard capabilities are fetched every poll cycle.

State from un-polled OCF endpoints is preserved between cycles using `dataclasses.replace()`, which avoids the common bug where falsy values (Night Mode off, woofer at 0) get incorrectly overwritten.

## Entities

| Entity | Platform | Description |
| --- | --- | --- |
| Media Player | `media_player` | Main soundbar entity with all controls |
| Night Mode | `switch` | Toggle night mode |
| Voice Amplifier | `switch` | Toggle voice amplifier |
| Bass Boost | `switch` | Toggle bass boost |
| Active Voice Amplifier | `switch` | Toggle active voice amplifier |
| Space Fit Sound | `switch` | Toggle Space Fit Sound feature |
| SpaceFit Calibration | `button` | Trigger room calibration |
| Sound Mode | `select` | Standalone sound mode selector |
| EQ Preset | `select` | Standalone EQ preset selector (optional) |
| Input Source | `select` | Standalone input source selector |
| Woofer Level | `number` | Subwoofer level slider (-6 to +6 dB) |
| Volume | `sensor` | Raw volume level for automations |

## Troubleshooting

### Can't find my soundbar during setup

Use the SmartThings CLI to verify your device is visible:

```bash
smartthings devices
```

If your soundbar doesn't appear, make sure it's set up in the SmartThings mobile app first.

### Features missing or not working

Some OCF endpoints may not be available on all soundbar models. Download diagnostics and check the `state` section to see which fields are populated. You can also inspect your device's capabilities:

```bash
smartthings devices:capabilities <device-id>
```

If `execute` is not listed as a capability, the OCF-based features (sound mode, night mode, woofer, EQ) will not work on your model.

### Rate limiting (429 errors)

The integration automatically retries with backoff. If you see frequent 429 errors in the logs, try disabling feature groups you don't use in the integration options to reduce API calls.

## Diagnostics

Download diagnostic data from **Settings > Devices & Services > Samsung Soundbar > ... > Download Diagnostics**. All OAuth tokens and credentials are automatically redacted. Include this file when reporting issues.

## Supported Devices

Tested on:
- Samsung HW-Q990D
- Samsung HW-Q990C
- Samsung HW-Q930D

Should work with any Samsung soundbar that appears in the SmartThings app and exposes the `execute` capability for OCF endpoints. If your model doesn't work, open an issue with your diagnostics file.

## Credits

- SmartThings OCF endpoint documentation: [YASSI docs](https://ha-samsung-soundbar.vercel.app/)
- Original YASSI integration by [@samuelspagl](https://github.com/samuelspagl)
- OAuth pattern and API client from [homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar)

## License

MIT
