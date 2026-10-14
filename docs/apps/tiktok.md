# TikTok Patches Guide

Technical documentation and patch catalog for TikTok on Android.

---

## 1. Target & Compatibility

| Property | Value |
| :--- | :--- |
| **Target App** | TikTok |
| **Package Name** | `com.zhiliaoapp.musically` |
| **Target Version** | `47.1.4` |
| **Target Package Format** | standalone APK (nodpi APK) |
| **Primary Architecture** | `arm64-v8a` / `armeabi-v7a` |
| **Authoritative Source** | APKMirror |

---

## 2. Applied Patches Catalog

| Patch Name | Typology | Default State | Dependencies | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Disable Push Notifications** | `bytecodePatch` | `false` (Opt-in) | None | Stops background push notifications. |
| **Instant Launch** | `bytecodePatch` | `true` (Enabled) | None | Opens the app immediately without splash screens or ad delays. |
| **Disable Live Gift Effects** | `bytecodePatch` | `false` (Opt-in) | None | Disables 3D gift animations in live streams to prevent frame drops. |
| **Remove Live Stream Files** | `rawResourcePatch` | `false` (Opt-in) | None | Removes live streaming and minigame files. Breaks lives and video calls. |
| **Block P2P Video Relay** | `rawResourcePatch` | `true` (Enabled) | None | Stops your device from uploading videos to other users. |
| **Playback & Display Governor** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Limits playback resolution and HDR to save battery, and locks the screen refresh rate. |
| **Battery & Resource Saver** | `bytecodePatch` | `true` (Enabled) | None | Stops 3D ad sensors and aggressive video preloading to save battery and data. |
| **Allow Screenshots** | `bytecodePatch` | `true` (Enabled) | None | Removes screenshot and screen recording blocking. |
| **Camera & Microphone Indicator** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Shows a corner mark while TikTok holds camera/mic open. |
| **Clean Share Links** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Removes tracking parameters from shared links. |
| **Disable On-Device AI** | `bytecodePatch` | `true` (Enabled) | None | Turns off on-device AI, the chatbot and AI search. |
| **Device Privacy Guard** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Blocks access to your contacts, location, apps and sensors. |
| **Feed Ads & Content Filter** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Filters ads, shopping tags, live cards, and clutter from your feed. |
| **Friends & Suggestions Filter** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Keeps the Friends feed strictly mutual and hides suggested accounts across the app. |
| **Disable History Recording** | `bytecodePatch` | `false` (Opt-in) | None | Prevents TikTok from recording your watch history and search queries. |
| **In-App Browser Privacy Guard** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Opens web links in your browser and blocks tracking in the remaining web views. |
| **Login Compatibility Fix** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Restores Google and Spotify sign-in on modified app builds. |
| **Bypass Mandatory Login** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Lets you browse videos and feeds without creating an account or logging in. |
| **SIM Region Selector** | `bytecodePatch` | `false` (Opt-in) | None | Locks the app to a chosen country to unlock regional content. |
| **Block Trackers (Setup)** | `resourcePatch` | `true` (Enabled) | None | Removes tracking permissions and disables telemetry components. |
| **Strip Sensitive Permissions** | `resourcePatch` | `false` (Opt-in) | None | Removes sensitive hardware, sensor, and tracking permissions. |
| **Block Trackers** | `bytecodePatch` | `true` (Enabled) | None | Neutralizes ByteDance AppLog tracking, crash monitors, and analytics. |
| **Remove Extra Files** | `rawResourcePatch` | `true` (Enabled) | None | Removes card scanners, AI engines and extra fonts to save space. |
| **Remove Creator Tools** | `rawResourcePatch` | `false` (Opt-in) | None | Removes video editing and effects tools to free up space. |
| **Remove Extra Languages** | `rawResourcePatch` | `false` (Opt-in) | None | Deletes unselected language packs. |
| **Remove Voice Tools** | `rawResourcePatch` | `false` (Opt-in) | None | Removes voice search and text-to-speech to save space. Breaks voice features. |
| **Always Show Publish Date** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Shows the upload date on all videos. |
| **Auto-Pause First Video** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Pauses the first video on launch so it plays without lag. |
| **Comment Customizer** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Takes control of comments: sort, copy, translate and hide clutter. |
| **Offline Video Limit** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Customizes the maximum number of videos saved for offline viewing. |
| **Custom Share Sheet** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Lets you hide share menu entries you do not use. |
| **Declutter Direct Messages** | `bytecodePatch` | `false` (Opt-in) | None | Cleans up chat and DM screens by hiding extra buttons. |
| **Declutter Video Interface** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Cleans up the buttons and overlays on top of videos. |
| **Declutter Navigation Bar** | `bytecodePatch` | `true` (Enabled) | None | Removes extra tabs and buttons from navigation bars. |
| **Force Auto-Scroll** | `bytecodePatch` | `true` (Enabled) | None | Enables native auto-scrolling to the next video. |
| **Hide Inbox Promos & Alerts** | `bytecodePatch` | `true` (Enabled) | None | Hides promo banners, streak cards and suggestions in your inbox. |
| **Hide Inbox Story Tray** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Hides the stories and status tray at the top of the inbox. |
| **Download Without Watermark** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Unlocks downloading and saves videos without watermarks. |
| **Remember Playback Speed** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Keeps your chosen playback speed across videos and restarts. |
| **Block Popups & Prompts** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Blocks popups, nags and promo dialogs across the app. |
| **Enable Profile Banner** | `bytecodePatch` | `true` (Enabled) | None | Unlocks the profile banner and its editing tools. |
| **Remember Clear Display** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Keeps clear-display mode active when scrolling to the next video. |
| **Resume Video After Scroll** | `bytecodePatch` | `false` (Opt-in) | None | Resumes playback from where you left off when returning to a video. |
| **Customize Search** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Customizes search suggestions, live recommendations, and autoplay. |
| **Show Author Region** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Displays the creator's country code next to their username. |
| **Show Seekbar** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Restores the video progress seekbar and scrubbing controls. |
| **Stop Video Looping** | `bytecodePatch` | `false` (Opt-in) | None | Stops videos at the end instead of replaying them in an infinite loop. |
| **Use System Font** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Uses the system font instead of bundled TikTok fonts. |
| **Video Fit Mode** | `bytecodePatch` | `false` (Opt-in) | `sharedExtensionPatch` | Lets you choose between fitting the whole video or filling the screen. |

---

## 3. Technical Breakdown

### A. Privacy, Ad Filtering & Tracking
- **Feed & Tracker Neutralization**: Filters sponsored feed ads, shopping anchors, survey popups, and live commerce cards. Neutralizes ByteDance AppLog dispatchers and strips tracking permissions from the manifest.
- **Privacy Protections**: Blocks device fingerprinting (SIM identifiers, clipboard snooping, installed package queries) and strips tracking query parameters from outgoing share URLs.
- **Browser & Login Guard**: Intercepts in-app browser requests to open them in external browsers and bypasses mandatory login hurdles.

### B. Usability & Playback Enhancements
- **Playback Controls**: Restores video scrubbing seekbars on all posts, enables persistent playback speed memory, auto-scroll, and pause on launch.
- **Clean Interface**: Declutters feed UI overlay buttons, direct message banners, inbox promotional carousels, and navigation bar tabs.
- **Media Tools**: Unlocks high-definition video downloads without watermarks and allows screenshots in secure views.

### C. Resource Governance & Slimming
- **P2P Relay & Performance**: Zeroes native peer-to-peer relay libraries (`libttquic.so`) to stop background bandwidth leeching.
- **Slimmer Axes**: Supports optional removal of creator tools, live streaming modules, speech synthesis engines, and extra localization tables.

---

## 4. Known Limitations

- **Binary Debloating Side Effects**: Zeroing creator or live streaming libraries disables video recording, camera effects, and live broadcast features.
- **Voice Tools**: Stripping speech engine binaries ceases text-to-speech narration and voice search functionality.
- **Server Enforcement**: Region selection spoofs client carrier and locale indicators; server-side geoblocks or IP-level enforcement require corresponding network routing.
