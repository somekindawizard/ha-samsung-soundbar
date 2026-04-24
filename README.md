<div align="center">

# 🔊 Samsung Soundbar for Home Assistant

**Full-featured Home Assistant integration for Samsung soundbars via SmartThings API**

[![HACS][hacs-badge]][hacs-url]
[![Home Assistant][ha-badge]][ha-url]
[![GitHub Release][release-badge]][release-url]
[![License][license-badge]][license-url]
[![GitHub Last Commit][commit-badge]][commit-url]
[![GitHub Issues][issues-badge]][issues-url]

Control power, volume, input sources, sound modes, EQ, per-speaker levels, TTS,<br>
and more — directly from your dashboard and automations.

[Install via HACS](#-installation) · [Setup Guide](#-setup--authentication) · [Services](#-services) · [Report a Bug][issues-url]

</div>

---

> **Built from scratch**, combining the strengths of [homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar) (OAuth management, robust API client) and [YASSI](https://github.com/samuelspagl/ha_samsung_soundbar) (EQ, per-speaker volume, Space Fit Sound). Modernized for current Home Assistant standards using `DataUpdateCoordinator`, `CoordinatorEntity`, and a proper config flow.

---

## ⚡ Quick Start

```
1.  Add custom repo in HACS  →  https://github.com/somekindawizard/ha-samsung-soundbar
2.  Install "Samsung Soundbar" and restart Home Assistant
3.  Settings → Devices & Services → Add Integration → Samsung Soundbar
```

> **Need detailed steps?** Jump to [Installation](#-installation) or [Setup & Authentication](#-setup--authentication).

---

## ✨ Features

<table>
<tr>
<td width="50%" valign="top">

### 🎵 Media Player
- Power on/off control
- Volume level, step up/down, mute/unmute
- Input source switching (HDMI, Bluetooth, Wi-Fi, Optical…)
- Sound mode selection (Adaptive, Standard, Surround, Game…)
- Play, pause, stop with optimistic state updates
- Next/previous track control
- Media info: title, artist, elapsed time, duration
- Real-time progress bar in HA media player card

</td>
<td width="50%" valign="top">

### 🔊 Audio Controls
- **Night Mode** — reduce bass and limit volume
- **Voice Amplifier** — boost dialogue clarity
- **Bass Boost** — enhance low-frequency output
- **Active Voice Amplifier** — dynamic dialogue enhancement
- **Space Fit Sound** — room-aware audio optimization
- **Woofer Level** — slider from -6 to +6 dB
- **Equalizer** — EQ preset selector *(optional)*
- **Per-Speaker Volume** — adjust individual channels

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📢 Play Media & TTS
- Send TTS announcements to your soundbar
- Stream any audio URL directly
- Smart playback modes:
  - `playTrackAndRestore` — announcements (restores volume)
  - `playTrackAndResume` — music (resumes previous track)
  - `playTrack` — simple playback fallback

</td>
<td width="50%" valign="top">

### 🛡️ Reliability
- **Auto re-auth** — prompts when tokens expire
- **Error feedback** — failed commands surface in HA UI
- **Post-write refresh** — immediate state confirmation
- **Rate-limit handling** — exponential backoff + `Retry-After`
- **OCF read serialization** — prevents interleaved requests
- **Optimistic updates** — instant UI feedback

</td>
</tr>
</table>

**Also includes:**
- 🎛️ **Apply Preset** — set sound mode, EQ, night mode, and woofer level atomically in one call
- 🔍 **Zeroconf Discovery** — automatic detection of soundbars on your network
- ⚙️ **Device Triggers** — build HA automations without knowing entity IDs
- 📐 **SpaceFit Calibration** — trigger room calibration via a button entity

---

## 🎧 Supported Devices

| Status | Models |
|:---:|---|
| ✅ Tested | **HW-Q990D** · **HW-Q990C** · **HW-Q930D** |
| 🔄 Compatible | Any Samsung soundbar visible in SmartThings with `execute` capability |

> **Your model not listed?** It will likely work. If it doesn't, [open an issue][issues-url] with your diagnostics file attached.

---

## 📦 Installation

### Option A: HACS (Recommended)

1. In HACS, go to **Integrations** → three-dot menu → **Custom repositories**
2. Add this URL with category **Integration**:
   ```
   https://github.com/somekindawizard/ha-samsung-soundbar
   ```
3. Search for **Samsung Soundbar** and click **Install**
4. **Restart Home Assistant**

### Option B: Manual

1. Download or clone this repository
2. Copy `custom_components/samsung_soundbar` into your HA `custom_components/` directory
3. **Restart Home Assistant**

---

## 🔐 Setup & Authentication

### Choosing an Auth Method

| | **OAuth** ✅ Recommended | **Personal Access Token** |
|---|---|---|
| **Token Lifetime** | 24h (auto-refreshable) | 24h (not refreshable) |
| **Auto-Refresh** | ✅ Yes | ❌ No |
| **Re-Auth Frequency** | Rarely (only if refresh token revoked) | Every 24 hours |
| **Best For** | Permanent installations | Quick testing / OAuth fallback |

> **💡 Why offer PAT?** OAuth requires a Samsung Developer Workspace project, which can be finicky. PAT lets you verify the integration works in 30 seconds before committing to OAuth. When it expires, HA prompts you to enter a new one or switch to OAuth.

---

<details>
<summary><h3>🔑 OAuth Setup (Recommended) — click to expand</h3></summary>

You can create OAuth credentials via the **web UI** or the **SmartThings CLI**.

#### Via Developer Workspace (Web UI)

1. Navigate to the [Samsung Developer Workspace](https://smartthings.developer.samsung.com/workspace/projects)
2. Create a **new project** → select **Partner managed OAuth2**
3. Set the **Redirect URI**:
   ```
   https://api.smartthings.com/oauth/callback
   ```
4. Request these **scopes**:
   - `r:devices:*`
   - `x:devices:*`
   - `r:locations:*`
5. Save your **Client ID** and **Client Secret**

#### Via SmartThings CLI (Faster)

```bash
# Install the CLI
npm install -g @smartthings/cli

# Log in
smartthings login

# Create an OAuth app
smartthings apps:oauth:generate \
  --client-name "HA Soundbar" \
  --scope "r:devices:* x:devices:* r:locations:*" \
  --redirect-uri "https://api.smartthings.com/oauth/callback"
```

Your **Client ID** and **Client Secret** are printed directly in the terminal.

#### Verify Your Soundbar (Optional)

```bash
smartthings devices                          # List all devices
smartthings devices:status <device-id>       # Detailed device status
smartthings devices:capabilities <device-id> # Supported capabilities
```

</details>

---

<details>
<summary><h3>🎫 Personal Access Token Setup (Quick Testing) — click to expand</h3></summary>

1. Go to [SmartThings Tokens](https://account.smartthings.com/tokens)
2. Generate a new token with these scopes:
   - **Devices:** List all devices, See all devices, Control all devices
   - **Locations:** See all locations
3. Copy the generated token

> ⚠️ **PATs expire after 24 hours** and cannot be auto-refreshed. When expired, HA will prompt you to enter a new one. For permanent use, switch to OAuth.

</details>

---

### Adding the Integration

**🔍 Automatic Discovery:**
If your soundbar is on the same network, Home Assistant may detect it automatically via Zeroconf.

**✋ Manual Setup:**

1. **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Samsung Soundbar**
3. Choose your auth method (OAuth or PAT)
4. **OAuth:** Enter Client ID + Secret, complete browser authorization
5. **PAT:** Paste your token
6. Select your soundbar from the discovered devices
7. *(Optional)* Adjust the maximum volume slider range

---

### Feature Toggles

After setup, visit the integration's **Options** page to enable/disable features:

| Feature Group | Default | Notes |
|---|:---:|---|
| Sound Mode Selector | ✅ On | Standalone `select` entity |
| Advanced Audio Switches | ✅ On | Night Mode, Voice Amp, Bass Boost |
| Woofer Level Control | ✅ On | Subwoofer `number` entity |
| Equalizer Preset Selector | ⬚ Off | EQ preset `select` entity |

> **💡 Performance tip:** Disabling a feature group skips its OCF endpoint polling, reducing API calls. Changes apply immediately with no restart required.

---

## 📋 Entity Reference

| Entity | Platform | Description |
|---|---|---|
| Media Player | `media_player` | Main entity — playback, volume, source, sound mode |
| Night Mode | `switch` | Toggle night mode |
| Voice Amplifier | `switch` | Toggle voice amplifier |
| Bass Boost | `switch` | Toggle bass boost |
| Active Voice Amplifier | `switch` | Toggle active voice amplifier |
| Space Fit Sound | `switch` | Toggle Space Fit Sound |
| SpaceFit Calibration | `button` | Trigger room calibration |
| Sound Mode | `select` | Standalone sound mode picker |
| EQ Preset | `select` | EQ preset picker *(optional)* |
| Input Source | `select` | Standalone input source picker |
| Woofer Level | `number` | Subwoofer slider (-6 to +6 dB) |
| Volume | `sensor` | Raw volume for automations/templates |

---

## 🎛 Services

<details open>
<summary><strong><code>samsung_soundbar.apply_preset</code></strong> — Set multiple audio settings atomically</summary>

&nbsp;

Only the fields you provide are changed; everything else stays untouched.

| Field | Type | Required | Description |
|---|---|:---:|---|
| `sound_mode` | string | | Sound mode name (e.g. `surround`, `adaptive sound`) |
| `eq_preset` | string | | EQ preset name (e.g. `Music`, `Movie`) |
| `night_mode` | boolean | | Enable or disable night mode |
| `woofer_level` | integer | | Woofer level from -6 to +6 |

```yaml
# Movie night
service: samsung_soundbar.apply_preset
data:
  sound_mode: surround
  night_mode: true
  woofer_level: 3

# Music listening
service: samsung_soundbar.apply_preset
data:
  sound_mode: "adaptive sound"
  eq_preset: Music
  night_mode: false
  woofer_level: 0
```

</details>

<details>
<summary><strong><code>samsung_soundbar.set_speaker_level</code></strong> — Adjust individual speaker channels</summary>

&nbsp;

| Field | Type | Required | Description |
|---|---|:---:|---|
| `speaker_channel` | string | ✅ | `Spk_Center`, `Spk_Side`, `Spk_Wide`, `Spk_Front_Top`, `Spk_Rear`, `Spk_Rear_Top` |
| `level` | integer | ✅ | Volume level from -6 to +6 dB |

```yaml
service: samsung_soundbar.set_speaker_level
data:
  speaker_channel: Spk_Center
  level: 3
```

</details>

<details>
<summary><strong><code>samsung_soundbar.set_rear_speaker_mode</code></strong> — Switch rear speaker positioning</summary>

&nbsp;

| Field | Type | Required | Description |
|---|---|:---:|---|
| `mode` | string | ✅ | Either `Front` or `Rear` |

```yaml
service: samsung_soundbar.set_rear_speaker_mode
data:
  mode: Rear
```

</details>

<details>
<summary><strong>Play Media & TTS Examples</strong></summary>

&nbsp;

```yaml
# TTS announcement
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

</details>

---

## 🎵 Sound Modes

Sound modes are dynamically populated from your device via the Samsung OCF `/sec/networkaudio/soundmode` endpoint. The exact list depends on your soundbar model and firmware.

<details>
<summary><strong>Default & Additional Sound Modes</strong> — click to expand</summary>

&nbsp;

#### Default Modes (available before first OCF poll)

| Mode | Description |
|---|---|
| **Adaptive Sound** | Real-time content analysis with automatic optimization. Best for mixed-use. |
| **Standard** | Balanced, neutral profile. Good general-purpose default. |
| **Surround** | Expanded soundstage for immersive surround experience. Ideal for movies/TV. |
| **Game** | Enhanced spatial cues and directional audio for gaming. |

#### Additional Modes (model-dependent)

| Mode | Description |
|---|---|
| **Game Pro** | Enhanced gaming mode with further optimized spatial processing. |
| **Movie** | Cinematic audio: dialogue clarity + low-frequency effects. |
| **Music** | Musical clarity and dynamic range emphasis. |
| **Voice** | Prioritizes dialogue/vocal clarity for speech-heavy content. |

> **💡 Tip:** Check the **Sound Mode** select entity after the first poll, or inspect `supported_sound_modes` in your diagnostics.

</details>

<details>
<summary><strong>Sound Mode Control Methods</strong> — click to expand</summary>

&nbsp;

**1. Via Media Player entity:**
```yaml
service: media_player.select_sound_mode
target:
  entity_id: media_player.soundbar
data:
  sound_mode: "adaptive sound"
```

**2. Via standalone Select entity:**
```yaml
service: select.select_option
target:
  entity_id: select.soundbar_sound_mode
data:
  option: "surround"
```

**3. Via Apply Preset service:**
```yaml
service: samsung_soundbar.apply_preset
data:
  sound_mode: "game"
  woofer_level: 4
  night_mode: false
```

</details>

<details>
<summary><strong>Automation Examples</strong> — click to expand</summary>

&nbsp;

```yaml
# Switch to Game mode when PS5 starts
automation:
  - alias: "Game mode when PS5 starts"
    trigger:
      - platform: state
        entity_id: media_player.soundbar
        attribute: source
        to: "HDMI2"
    action:
      - service: media_player.select_sound_mode
        target:
          entity_id: media_player.soundbar
        data:
          sound_mode: "game"

# Movie night: surround + boosted woofer
automation:
  - alias: "Movie night preset"
    trigger:
      - platform: state
        entity_id: media_player.soundbar
        to: "playing"
    condition:
      - condition: time
        after: "19:00:00"
    action:
      - service: samsung_soundbar.apply_preset
        data:
          sound_mode: "surround"
          woofer_level: 3
          night_mode: false

# Late night: quieter settings
automation:
  - alias: "Late night mode"
    trigger:
      - platform: time
        at: "22:00:00"
    condition:
      - condition: state
        entity_id: media_player.soundbar
        state: "playing"
    action:
      - service: samsung_soundbar.apply_preset
        data:
          sound_mode: "adaptive sound"
          night_mode: true
          woofer_level: -2
```

</details>

---

## ⚙️ How It Works

This integration communicates directly with the SmartThings REST API using both standard capabilities and undocumented Samsung OCF `execute` endpoints. **No dependency on `pysmartthings`.**

<details>
<summary><strong>Standard SmartThings Capabilities</strong></summary>

&nbsp;

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

</details>

<details>
<summary><strong>Samsung OCF Endpoints</strong></summary>

&nbsp;

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

</details>

<details>
<summary><strong>Polling Strategy</strong></summary>

&nbsp;

- **OCF endpoints** are polled one at a time on a rotating basis to avoid rate limiting. A full OCF refresh takes ~2 minutes (30s poll interval with 3-4 enabled targets).
- **Standard capabilities** are fetched every poll cycle.
- **State preservation:** Un-polled OCF values are preserved between cycles using `dataclasses.replace()`, preventing falsy values (Night Mode off, woofer at 0) from being overwritten.
- **Post-write refresh:** Write commands trigger an immediate coordinator refresh, so device state is confirmed within one cycle.

</details>

<details>
<summary><strong>Re-authentication Flow</strong></summary>

&nbsp;

1. **Detection** — The integration detects `401`/`403` responses during polling
2. **Notification** — A persistent notification appears: *"Samsung Soundbar requires re-authentication."*
3. **Re-auth flow** — Click the notification to open re-authentication:
   - **OAuth:** Presented with a new authorization URL
   - **PAT:** Prompted to paste a new token
4. **Recovery** — Integration reloads automatically and resumes

**Expected frequency:**
- **OAuth users:** Rarely. Only if the refresh token itself is revoked.
- **PAT users:** Every 24 hours. If that becomes cumbersome, switch to OAuth.

</details>

---

## 🔧 Troubleshooting

<details>
<summary><strong>Soundbar not found during setup</strong></summary>

&nbsp;

Verify your device is visible to SmartThings:

```bash
smartthings devices
```

If your soundbar doesn't appear, make sure it has been set up in the **SmartThings mobile app** first.

</details>

<details>
<summary><strong>"Requires re-authentication" keeps appearing</strong></summary>

&nbsp;

| Auth Method | Cause | Solution |
|---|---|---|
| **PAT** | Expected (24h expiration) | Switch to OAuth |
| **OAuth** | Refresh token revoked/expired | Verify your OAuth app is active in the [Developer Workspace](https://smartthings.developer.samsung.com/workspace/projects), then re-auth via HA notification |

</details>

<details>
<summary><strong>Features missing or not working</strong></summary>

&nbsp;

Some OCF endpoints may not be available on all models.

1. Download **diagnostics** from the integration page and check the `state` section
2. Inspect capabilities:
   ```bash
   smartthings devices:capabilities <device-id>
   ```
3. If `execute` is **not** listed, OCF-based features (sound mode, night mode, woofer, EQ) won't work on your model

</details>

<details>
<summary><strong>Rate limiting (429 errors)</strong></summary>

&nbsp;

The integration retries automatically with exponential backoff. If you see frequent 429 errors, **disable feature groups** you don't use in the integration options to reduce API calls.

</details>

<details>
<summary><strong>Commands fail with error notifications</strong></summary>

&nbsp;

1. **Check HA logs** for the specific SmartThings error code
2. **Verify the soundbar is powered on** — some commands are rejected when off
3. **Check for SmartThings outages** — the API occasionally has downtime

</details>

---

## 🙏 Credits

| | |
|---|---|
| OCF endpoint documentation | [YASSI Docs](https://ha-samsung-soundbar.vercel.app/) |
| Original YASSI integration | [@samuelspagl](https://github.com/samuelspagl) |
| OAuth pattern & API client | [homebridge-q990d-soundbar](https://github.com/somekindawizard/homebridge-q990d-soundbar) |

## 📄 License

[MIT](LICENSE)

---

<div align="center">

**[⬆ Back to top](#-samsung-soundbar-for-home-assistant)**

</div>

<!-- Badge References -->
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square
[hacs-url]: https://hacs.xyz
[ha-badge]: https://img.shields.io/badge/Home%20Assistant-2024.12%2B-blue.svg?style=flat-square&logo=home-assistant&logoColor=white
[ha-url]: https://www.home-assistant.io/
[release-badge]: https://img.shields.io/github/v/release/somekindawizard/ha-samsung-soundbar?style=flat-square&color=brightgreen
[release-url]: https://github.com/somekindawizard/ha-samsung-soundbar/releases/latest
[license-badge]: https://img.shields.io/github/license/somekindawizard/ha-samsung-soundbar?style=flat-square&color=green
[license-url]: LICENSE
[commit-badge]: https://img.shields.io/github/last-commit/somekindawizard/ha-samsung-soundbar?style=flat-square
[commit-url]: https://github.com/somekindawizard/ha-samsung-soundbar/commits
[issues-badge]: https://img.shields.io/github/issues/somekindawizard/ha-samsung-soundbar?style=flat-square
[issues-url]: https://github.com/somekindawizard/ha-samsung-soundbar/issues
