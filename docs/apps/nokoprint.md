# NokoPrint Patches Guide

Technical documentation and patch catalog for NokoPrint on Android.

---

## 1. Target & Compatibility

| Property | Value |
| :--- | :--- |
| **Target App** | NokoPrint - WiFi, Bluetooth, USB |
| **Package Name** | `com.nokoprint` |
| **Target Version** | `5.28.6` |
| **Target Package Format** | XAPK bundle |
| **Primary Architecture** | universal (`arm64-v8a` / `armeabi-v7a` / `x86` / `x86_64`) |
| **Authoritative Source** | APKPure |

---

## 2. Applied Patches Catalog

| Patch Name | Typology | Default State | Dependencies | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Block Ads (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Removes ad screens and ad startup components. |
| **Block Ads** | `bytecodePatch` | `true` (Enabled) | `Block Ads (Setup)` | Blocks ad loaders and unlocks ad-free status. |
| **Remove Extra Files** | `rawResourcePatch` | `true` (Enabled) | None | Deletes hidden ad files and trackers to shrink the app. |
| **Stop Background Sync (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Turns off background alarms and schedulers. |
| **Stop Background Sync** | `bytecodePatch` | `true` (Enabled) | `Stop Background Sync (Setup)` | Stops background tasks that drain the battery. |
| **Block Trackers (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Removes ad permissions and disables tracking components. |
| **Block Trackers** | `bytecodePatch` | `true` (Enabled) | `Block Trackers (Setup)` | Blocks analytics and ad tracking. |
| **Remove Extra Stores** | `resourcePatch` | `true` (Enabled) | None | Disables payment components for other app stores you do not use. |
| **Safer Connections** | `resourcePatch` | `true` (Enabled) | None | Uses trusted certificates while keeping printer downloads working. |
| **Skip Welcome Screen** | `bytecodePatch` | `true` (Enabled) | None | Skips the first-launch popup (the About menu still works). |

---

## 3. Technical Breakdown

### A. Ad Removal & Premium Unlock
- **Ad Manifest Purge**: Strips AdMob and mediation activities, receivers, and initialization providers from `AndroidManifest.xml`.
- **Bytecode Ad Neutralization**: Forces ad-free status flags to true and short-circuits full-screen and banner ad dispatchers.
- **Asset Debloating**: Deletes embedded ad SDK HTML assets, web tracking templates, and mediation configuration files.

### B. Telemetry & Background Sync
- **Block Trackers**: Strips advertising identifier permissions (`AD_ID`), disables Firebase and Google Analytics providers, and neutralizes runtime event tracking calls.
- **Background Sync Optimization**: Disables periodic worker jobs, wake locks, and update check services in the manifest and runtime schedulers.

### C. Network Hardening & UX Cleanups
- **Remove Extra Stores**: Strips alternative app store billing frameworks (Huawei AppGallery, Samsung Galaxy Store, Amazon Appstore), keeping only Google Play billing interfaces intact.
- **Safer Connections**: Configures network security configuration to enforce secure transport while ensuring local network printer discovery and online driver downloads function normally.
- **Skip Welcome Screen**: Suppresses initial welcome and setup modals upon first launch while preserving manual access through settings.

---

## 4. Known Limitations

- **XAPK Container Format**: Target package is distributed as an XAPK container containing split architecture binaries.
- **Driver Download Connectivity**: Hardening network security preserves HTTP endpoints required by legacy network printers and remote driver repositories.
