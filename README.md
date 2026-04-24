# Samsung Soundbar for Home Assistant

[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

A custom Home Assistant integration for Samsung soundbars (HW-Q990D, HW-Q990C, HW-Q930D, and others) using the SmartThings API. Control power, volume, input sources, sound modes, EQ, per-speaker levels, and more directly from your HA dashboard and automations.

> **Built from scratch**, combining the strengths of [homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar) (OAuth management, robust API client) and [YASSI](https://github.com/samuelspagl/ha_samsung_soundbar) (EQ, per-speaker volume, Space Fit Sound). Modernized for current Home Assistant standards using `DataUpdateCoordinator`, `CoordinatorEntity`, and a proper config flow.

---

## Table of Contents

- [Features](#features)
- [Supported Devices](#supported-devices)
- [Installation](#installation)
- [Setup & Authentication](#setup--authentication)
- [Entity Reference](#entity-reference)
- [Services](#services)
- [How It Works](#how-it-works)
- [Troubleshooting](#troubleshooting)
- [Credits](#credits)
- [License](#license)

---

## Features

### 🎵 Media Player

| Feature | Description |
|---|---|
| **Power** | On/off control via the SmartThings `switch` capability |
| **Volume** | Set level, step up/down, mute/unmute with optimistic UI updates |
| **Input Source** | Switch between HDMI, Bluetooth, Wi-Fi, Optical, and more |
| **Sound Mode** | Adaptive, Standard, Surround, Game, etc. (dynamically populated per device) |
| **Media Transport** | Play, pause, and stop with optimistic state updates |
| **Track Control** | Next/previous track (shown only if your device supports `mediaTrackControl`) |
| **Media Info** | Title, artist, elapsed time, and duration from `audioTrackData` |
| **Progress Bar** | Real-time media position tracking in the HA media player card |

### 🔊 Audio Controls

| Feature | Description |
|---|---|
| **Advanced Audio Switches** | Night Mode, Voice Amplifier, Bass Boost, Active Voice Amplifier, Space Fit Sound |
| **Woofer Level** | Number entity with a slider ranging from -6 to +6 dB |
| **Equalizer** | EQ preset selector (optional; toggle in integration options) |
| **Per-Speaker Volume** | Service call to adjust individual channels (center, side, rear, etc.) |
| **Rear Speaker Mode** | Service call to switch rear speakers between front and rear positioning |

### 📢 Play Media & TTS

| Feature | Description |
|---|---|
| **TTS Announcements** | Send text-to-speech audio to your soundbar from any HA TTS service |
| **Play URL** | Stream any audio URL directly on the soundbar |
| **Smart Playback Modes** | Automatically selects the right SmartThings command: `playTrackAndRestore` for announcements (restores volume after), `playTrackAndResume` for music (resumes previous track), or `playTrack` as a fallback |

### 🎛️ Presets & Calibration

- **Apply Preset** — Set sound mode, EQ, night mode, and woofer level atomically in a single service call.
- **SpaceFit Calibration** — Button entity that triggers your soundbar's room calibration process.

### 🔍 Discovery & Automation

- **Zeroconf Discovery** — Home Assistant automatically detects Samsung soundbars on your local network.
- **Device Triggers** — Build automations in the HA UI without knowing entity IDs (triggers: sound mode changed, playback started/paused/stopped, night mode toggled, input source changed).

### 🛡️ Reliability

| Feature | Description |
|---|---|
| **Automatic Re-authentication** | When tokens expire, HA prompts you to re-authenticate instead of silently failing |
| **Error Feedback** | Failed commands surface a notification in the HA UI |
| **Post-Write Refresh** | OCF commands trigger an immediate state refresh to confirm changes |
| **Rate-Limit Handling** | Automatic retry with exponential backoff and `Retry-After` header support for 429 responses |
| **OCF Read Serialization** | Per-device locking prevents interleaved OCF execute/status reads |
| **Optimistic Updates** | UI updates immediately on commands without waiting for the next poll |

---

## Supported Devices

**Tested on:**
- Samsung HW-Q990D
- Samsung HW-Q990C
- Samsung HW-Q930D

**Compatibility:** Should work with any Samsung soundbar that appears in the SmartThings app and exposes the `execute` capability for OCF endpoints. If your model doesn't work, please [open an issue](https://github.com/somekindawizard/ha-samsung-soundbar/issues) with your diagnostics file attached.

---

## Installation

### Option A: HACS (Recommended)

1. In HACS, go to **Integrations** and click the three-dot menu.
2. Select **Custom repositories** and add:
   ```
   https://github.com/somekindawizard/ha-samsung-soundbar
   ```
   with category **Integration**.
3. Search for **Samsung Soundbar** and click **Install**.
4. Restart Home Assistant.

### Option B: Manual

1. Download or clone this repository.
2. Copy the `custom_components/samsung_soundbar` folder into your Home Assistant `custom_components/` directory.
3. Restart Home Assistant.

---

## Setup & Authentication

### Choosing an Authentication Method

This integration supports two methods for authenticating with SmartThings:

| Method | Token Lifetime | Auto-Refresh | Re-Auth Behavior | Recommended For |
|---|---|---|---|---|
| **OAuth** ✅ | 24 hours (auto-refreshable) | Yes | Prompts only if refresh token is revoked | Permanent installations |
| **Personal Access Token (PAT)** | 24 hours (not refreshable) | No | Prompts for a new token every 24h | Quick testing or OAuth fallback |

> **💡 Why is PAT still available?** OAuth setup requires creating a Samsung Developer Workspace project, which can be finicky. PAT lets you get running in 30 seconds to verify the integration works with your soundbar before committing to the full OAuth setup. When the PAT expires, HA will prompt you to enter a new one or reconfigure with OAuth.

---

### OAuth Setup (Recommended)

You can create the required OAuth credentials using either the Samsung Developer Workspace web UI or the SmartThings CLI.

#### Via Developer Workspace (Web UI)

1. Navigate to the [Samsung Developer Workspace](https://smartthings.developer.samsung.com/workspace/projects).
2. Create a **new project** and select **Partner managed OAuth2**.
3. Set the **Redirect URI** to:
   ```
   https://api.smartthings.com/oauth/callback
   ```
4. Request the following **scopes**:
   - `r:devices:*`
   - `x:devices:*`
   - `r:locations:*`
5. Save your **Client ID** and **Client Secret**.

#### Via SmartThings CLI (Faster)

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

Your **Client ID** and **Client Secret** are printed directly in the terminal.

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

---

### Personal Access Token Setup (Quick Testing)

1. Go to [SmartThings Tokens](https://account.smartthings.com/tokens).
2. Generate a new token with the following scopes enabled:
   - **Devices:** List all devices, See all devices, Control all devices
   - **Locations:** See all locations
3. Copy the generated token.

> ⚠️ **PATs expire after 24 hours** and cannot be automatically refreshed. When your PAT expires, HA will show a notification prompting you to enter a new one. For a permanent setup, use OAuth.

---

### Adding the Integration to Home Assistant

**Automatic Discovery:**
If your soundbar is on the same network, Home Assistant may discover it automatically via Zeroconf and prompt you to configure it.

**Manual Setup:**

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for **Samsung Soundbar**.
3. Choose your authentication method (OAuth or PAT).
4. **For OAuth:** Enter your Client ID and Client Secret, then complete the authorization flow in your browser.
5. **For PAT:** Paste your Personal Access Token.
6. Select your soundbar from the list of discovered devices.
7. (Optional) Adjust the maximum volume slider range.

---

### Feature Toggles

After setup, go to the integration's **Options** page to enable or disable feature groups:

| Feature Group | Default | Description |
|---|---|---|
| Sound Mode Selector | Enabled | Standalone select entity for sound mode |
| Advanced Audio Switches | Enabled | Night Mode, Voice Amplifier, Bass Boost toggles |
| Woofer Level Control | Enabled | Subwoofer level number entity |
| Equalizer Preset Selector | **Disabled** | EQ preset select entity |

> **Performance note:** Disabling a feature group skips its OCF endpoint polling, reducing API load. Changes take effect immediately with no restart required.

---

## Entity Reference

The integration creates the following entities for your soundbar:

| Entity | Platform | Description |
|---|---|---|
| Media Player | `media_player` | Main soundbar entity with all playback and volume controls |
| Night Mode | `switch` | Toggle night mode on/off |
| Voice Amplifier | `switch` | Toggle voice amplifier on/off |
| Bass Boost | `switch` | Toggle bass boost on/off |
| Active Voice Amplifier | `switch` | Toggle active voice amplifier on/off |
| Space Fit Sound | `switch` | Toggle the Space Fit Sound feature on/off |
| SpaceFit Calibration | `button` | Trigger room calibration |
| Sound Mode | `select` | Standalone sound mode selector for dashboards and automations |
| EQ Preset | `select` | Standalone EQ preset selector *(optional, disabled by default)* |
| Input Source | `select` | Standalone input source selector |
| Woofer Level | `number` | Subwoofer level slider (-6 to +6 dB) |
| Volume | `sensor` | Raw volume level for use in automations and templates |

---

## Services

### `samsung_soundbar.apply_preset`

Set multiple audio settings atomically in a single call. Only the fields you provide are changed; everything else remains untouched.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `sound_mode` | string | No | Sound mode name (e.g., `surround`, `adaptive sound`) |
| `eq_preset` | string | No | EQ preset name (e.g., `Music`, `Movie`) |
| `night_mode` | boolean | No | Enable or disable night mode |
| `woofer_level` | integer | No | Woofer level from -6 to +6 |

**Examples:**

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

---

### `samsung_soundbar.set_speaker_level`

Adjust the volume of an individual speaker channel.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `speaker_channel` | string | Yes | One of: `Spk_Center`, `Spk_Side`, `Spk_Wide`, `Spk_Front_Top`, `Spk_Rear`, `Spk_Rear_Top` |
| `level` | integer | Yes | Volume level from -6 to +6 dB |

**Example:**

```yaml
service: samsung_soundbar.set_speaker_level
data:
  speaker_channel: Spk_Center
  level: 3
```

---

### `samsung_soundbar.set_rear_speaker_mode`

Switch rear speakers between front and rear positioning.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `mode` | string | Yes | Either `Front` or `Rear` |

**Example:**

```yaml
service: samsung_soundbar.set_rear_speaker_mode
data:
  mode: Rear
```

---

### Play Media & TTS Examples

```yaml
# TTS announcement (e.g., doorbell or alarm)
service: tts.speak
target:
  entity_id: media_player.soundbar
data:
  message: "Someone is at the front door"

# Play an audio URL
service: media_player.play_media
target:
  entity_id: media_player.soundbar
data:
  media_content_type: music
  media_content_id: "https://example.com/doorbell.mp3"

# Announcement with a custom volume level
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

---

## How It Works

This integration communicates directly with the SmartThings REST API using both standard capabilities and undocumented Samsung OCF `execute` endpoints. There is **no dependency on `pysmartthings`**.

### Standard SmartThings Capabilities

| Feature | Capability | Commands |
|---|---|---|
| Power | `switch` | `on`, `off` |
| Volume | `audioVolume` | `setVolume`, `volumeUp`, `volumeDown` |
| Mute | `audioMute` | `mute`, `unmute` |
| Input Source | `samsungvd.audioInputSource` | `setInputSource` |
| Media Playback | `mediaPlayback` | `play`, `pause`, `stop` |
| Track Control | `mediaTrackControl` | `nextTrack`, `previousTrack` |
| TTS / Play Media | `audioNotification` | `playTrack`, `playTrackAndRestore`, `playTrackAndResume` |
| Media Info | `audioTrackData` | *(read-only)* title, artist, elapsed, total |

### Samsung OCF Endpoints (via `execute` capability)

| Feature | OCF Endpoint | Property |
|---|---|---|
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

- **OCF endpoints** are polled one at a time on a rotating basis to avoid SmartThings rate limiting. A full OCF refresh takes approximately **2 minutes** (at a 30-second poll interval with 3 to 4 enabled OCF targets).
- **Standard capabilities** are fetched on every poll cycle.
- **State preservation:** Un-polled OCF endpoint values are preserved between cycles using `dataclasses.replace()`, preventing a common bug where falsy values (Night Mode off, woofer at 0) get incorrectly overwritten.
- **Post-write refresh:** Write commands (sound mode, EQ, etc.) trigger an immediate coordinator refresh after the optimistic UI update, so device state is confirmed within one cycle rather than waiting for the rotation to come back around.

---

## Re-authentication

When your SmartThings credentials expire or become invalid, the integration handles it gracefully:

1. **Detection** — The integration detects `401`/`403` responses during polling.
2. **Notification** — A persistent notification appears: *"Samsung Soundbar requires re-authentication."*
3. **Re-auth flow** — Clicking the notification opens a re-authentication form:
   - **OAuth users:** Presented with a new authorization URL to get a fresh auth code.
   - **PAT users:** Prompted to paste a new Personal Access Token.
4. **Recovery** — After re-authenticating, the integration reloads automatically and resumes normal operation.

**What to expect:**
- **OAuth users** should rarely see this, since tokens auto-refresh. You will only be prompted if the refresh token itself expires or is revoked.
- **PAT users** will see this every 24 hours. If that becomes cumbersome, it is a good signal to switch to OAuth.

---

## Troubleshooting

### Soundbar not found during setup

Verify your device is visible to SmartThings:

```bash
smartthings devices
```

If your soundbar doesn't appear, make sure it has been set up in the **SmartThings mobile app** first.

### "Requires re-authentication" keeps appearing

| Auth Method | Cause | Solution |
|---|---|---|
| **PAT** | Expected behavior (24-hour expiration) | Switch to OAuth for a permanent setup |
| **OAuth** | Refresh token revoked or expired | Verify your OAuth app is active in the [Developer Workspace](https://smartthings.developer.samsung.com/workspace/projects), then re-authenticate via the HA notification |

### Features missing or not working

Some OCF endpoints may not be available on all soundbar models.

1. Download **diagnostics** from the integration page and check the `state` section for populated fields.
2. Inspect your device's capabilities:
   ```bash
   smartthings devices:capabilities <device-id>
   ```
3. If `execute` is **not** listed as a capability, the OCF-based features (sound mode, night mode, woofer, EQ) will not work on your model.

### Rate limiting (429 errors)

The integration retries automatically with exponential backoff. If you see frequent 429 errors in the logs, try **disabling feature groups** you don't use in the integration options to reduce API calls.

### Commands fail with error notifications

If you see error toasts when controlling the soundbar:

1. **Check the HA logs** for the specific SmartThings error code.
2. **Verify the soundbar is powered on.** Some commands are rejected when the device is off.
3. **Check for SmartThings outages.** The API occasionally has downtime.

---

## Credits

- SmartThings OCF endpoint documentation: [YASSI Docs](https://ha-samsung-soundbar.vercel.app/)
- Original YASSI integration by [@samuelspagl](https://github.com/samuelspagl)
- OAuth pattern and API client from [homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar)

## License

[MIT](LICENSE)
