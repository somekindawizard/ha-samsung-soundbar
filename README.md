# ha-samsung-soundbar

A Home Assistant custom integration for Samsung soundbars (HW-Q990D, Q990C, Q930D, and others) via the SmartThings API.

Built from scratch, combining the best of:
- **[homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar)** — OAuth token management, robust API client, debounced commands
- **[YASSI](https://github.com/samuelspagl/ha_samsung_soundbar)** — equalizer, per-speaker volume, Space Fit Sound, media info

Modernized for current Home Assistant standards (DataUpdateCoordinator, CoordinatorEntity, proper config flow).

## Features

- **OAuth authentication** — secure SmartThings OAuth2 flow with automatic token refresh (no Personal Access Tokens)
- **Media player** — power, volume, mute, input source, sound mode, media transport controls
- **Sound mode** — select from all supported modes (Adaptive, Standard, Surround, Game, etc.) via the media player or a standalone select entity
- **Advanced audio switches** — Night Mode, Voice Amplifier, Bass Boost, Active Voice Amplifier, Space Fit Sound
- **Woofer level** — number entity with -6 to +6 dB slider
- **Equalizer** — EQ preset selector (optional, toggled in integration options)
- **Input source** — standalone select entity for HDMI/Bluetooth/Wi-Fi input switching
- **Per-speaker volume** — service call to adjust individual channels (center, side, rear, etc.)
- **Rear speaker mode** — service call to switch rear speakers between front/rear positioning
- **Volume sensor** — raw volume level as a sensor for automations

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Samsung Soundbar" and install
3. Restart Home Assistant

### Manual

Copy the `custom_components/samsung_soundbar` folder to your Home Assistant `custom_components` directory.

## Setup

### Prerequisites

You need a SmartThings OAuth application:

1. Go to the [Samsung Developer Workspace](https://smartthings.developer.samsung.com/workspace/projects)
2. Create a new project → select **Partner managed OAuth2**
3. Set the redirect URI to `https://api.smartthings.com/oauth/callback`
4. Request scopes: `r:devices:*`, `x:devices:*`, `r:locations:*`
5. Note your **Client ID** and **Client Secret**

### Adding the Integration

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Samsung Soundbar"
3. Enter your Client ID and Client Secret
4. Open the authorization URL, log in with your Samsung account, authorize
5. Copy the `code` parameter from the redirect URL and paste it back
6. Select your soundbar from the discovered devices
7. Optionally adjust the max volume slider range

### Feature Toggles

After setup, go to the integration options to enable/disable feature groups:
- Sound Mode selector
- Advanced Audio switches
- Woofer level control
- Equalizer preset selector (off by default)

Disabling a feature group skips its OCF endpoint polling, reducing API load.

## How It Works

This integration talks directly to the SmartThings REST API using the same undocumented OCF `execute` capability endpoints that the SmartThings app uses. No dependency on `pysmartthings`.

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
| Power | Standard `switch` capability | — |
| Volume | Standard `audioVolume` capability | — |
| Input Source | Standard `mediaInputSource` capability | — |

## Credits

- SmartThings OCF endpoint documentation: [YASSI docs](https://ha-samsung-soundbar.vercel.app/)
- Original YASSI integration by [@samuelspagl](https://github.com/samuelspagl)
- OAuth pattern and API client from [homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar)

## License

MIT
