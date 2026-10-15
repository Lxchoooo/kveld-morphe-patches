# Xiaomi Earbuds Patches Guide

Technical documentation and patch catalog for Xiaomi Earbuds on Android.

---

## 1. Target & Compatibility

| Property | Value |
| :--- | :--- |
| **Target App** | Xiaomi Earbuds |
| **Package Name** | `com.mi.earphone` |
| **Target Version** | `1.38.0i` |
| **Target Package Format** | XAPK bundle |
| **Primary Architecture** | universal (`arm64-v8a` / `armeabi-v7a`) |
| **Download Target** | [APKPure](https://d.apkpure.com/b/XAPK/com.mi.earphone?versionCode=138000) |
| **Authoritative Source** | APKPure |

---

## 2. Applied Patches Catalog

| Patch Name | Typology | Default State | Dependencies | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Run on Rooted Devices** | `bytecodePatch` | `true` (Enabled) | None | Lets the app run on rooted phones and network tools without crashing. |
| **Stop Background Activity (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Turns off background services in the manifest. |
| **Stop Background Activity** | `bytecodePatch` | `true` (Enabled) | `Stop Background Activity (Setup)` | Stops persistent notifications and background battery drain. |
| **Block Trackers (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Removes ad permissions and disables tracking components in the manifest. |
| **Block Trackers** | `bytecodePatch` | `true` (Enabled) | `Block Trackers (Setup)` | Stops analytics and usage reporting. |
| **Device Privacy Guard (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Removes location permissions in the manifest. |
| **Device Privacy Guard** | `bytecodePatch` | `true` (Enabled) | `Device Privacy Guard (Setup)` | Hides hardware IDs and lets Bluetooth work without location. |
| **Skip Popups & Tutorials** | `bytecodePatch` | `true` (Enabled) | None | Skips startup agreements, tutorials, and promo banners. |
| **Update Without Account** | `bytecodePatch` | `true` (Enabled) | None | Lets guests check and install earbud firmware updates. |
| **Show All Models** | `bytecodePatch` | `true` (Enabled) | None | Shows every earbud model for pairing. |
| **Safer Connections (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Blocks unencrypted traffic and trusts user certificates. |
| **Safer Connections** | `bytecodePatch` | `true` (Enabled) | `Safer Connections (Setup)` | Blocks unencrypted traffic and disables certificate pinning. |
| **Offline Only (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Removes internet and network permissions in the manifest. |
| **Offline Only** | `bytecodePatch` | `false` (Opt-in) | `Offline Only (Setup)` | Fully disconnects the app from the internet. Pair your earbuds first. |
| **Unlock Sound Features** | `bytecodePatch` | `true` (Enabled) | None | Enables spatial audio and hearing features on all devices. |
| **Unlock for Other Phones** | `bytecodePatch` | `true` (Enabled) | None | Enables full features on Samsung, Pixel, and other non-Xiaomi phones. |

---

## 3. Technical Breakdown

### A. OEM & Feature Unlocks
- **Unlock for Other Phones**:
  - *Objective*: Enable complete feature settings and prevent warning dialogs on non-Xiaomi devices.
  - *How*: Bypasses brand checks by spoofing Xiaomi device attributes and removing account requirements for smart settings.
- **Unlock Sound Features**:
  - *Objective*: Enable spatial audio, dimensional sound, and low-latency audio options regardless of device restrictions.
  - *How*: Lifts device restriction checks and forces audio setting feature flags to return supported.
- **Show All Models**:
  - *Objective*: Display the full pairing catalog for all earbud models without region filtering.
  - *How*: Forces product visibility checks to always return true during device discovery.
- **Update Without Account**:
  - *Objective*: Allow checking and downloading firmware updates without requiring a Xiaomi account login.
  - *How*: Bypasses account authentication checks during OTA update requests.

### B. Security, Root & Privacy Guards
- **Run on Rooted Devices**:
  - *Objective*: Allow the app to run on rooted devices or alongside debugging tools without crashing.
  - *How*: Neutralizes root detection checks, Magisk and KernelSU heuristic scans, and debugger detection routines.
- **Device Privacy Guard**:
  - *Objective*: Prevent tracking through persistent device identifiers and remove unnecessary location permissions.
  - *How*: Spoofs hardware IDs such as IMEI and MAC addresses, strips location permissions, and allows Bluetooth scanning without fine location access.
- **Safer Connections**:
  - *Objective*: Support custom certificates and protect against unencrypted transmission.
  - *How*: Disables SSL certificate pinning and inserts network security configurations permitting user-installed certificates.
- **Skip Popups & Tutorials**:
  - *Objective*: Suppress initial privacy agreements, tutorial carousels, and promotional prompts.
  - *How*: Forces startup agreement and tutorial completion flags to true and suppresses permission nag dialogs.

### C. Background Optimization & Offline Mode
- **Stop Background Activity**:
  - *Objective*: Eliminate persistent background notifications and reduce standby battery drain.
  - *How*: Disables foreground service keep-alives and background listener components in both the manifest and bytecode.
- **Offline Only**:
  - *Objective*: Run the application completely severed from the internet.
  - *How*: Strips network permissions from the manifest and stubs HTTP clients and DNS resolvers to prevent network calls.

---

## 4. Known Limitations

- **Offline Mode Workflow**: Disconnecting the app from the internet prevents cloud device synchronization and remote firmware checks. Earbuds must be paired initially before applying offline mode.
- **Hardware-Constrained Audio**: Unlocking spatial audio and low latency profiles enables the software toggles; physical DSP support depends on earbud firmware capabilities.
