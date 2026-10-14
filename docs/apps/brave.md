# Brave Patches Guide

Technical documentation and patch catalog for Brave Private Web Browser on Android.

---

## 1. Target & Compatibility

| Property | Value |
| :--- | :--- |
| **Target App** | Brave Private Web Browser, VPN |
| **Package Name** | `com.brave.browser` |
| **Target Version** | `1.97.56` |
| **Target Package Format** | standalone APK (`Bravemonoarm64.apk` or `BraveMonoarm.apk`) |
| **Primary Architecture** | `arm64-v8a` / `armeabi-v7a` |
| **Authoritative Source** | github.com/brave/brave-browser/releases |

---

## 2. Applied Patches Catalog

| Patch Name | Typology | Default State | Dependencies | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Stop Background Sync** | `bytecodePatch` | `true` (Enabled) | None | Stops background wakeups and battery drain. |
| **Block Trackers (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Turns off analytics switches by default. |
| **Block Tracking Servers** | `rawResourcePatch` | `false` (Opt-in) | None | Redirects tracking servers to 0.0.0.0. |
| **Block Trackers** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch`, `Block Trackers (Setup)`, `Block Tracking Servers` | Blocks usage analytics, crash uploads and experiment downloads. |
| **Clean Start Page (Setup)** | `resourcePatch` | `true` (Enabled) | None | Turns off ads and news switches by default. |
| **Clean Start Page** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch`, `Clean Start Page (Setup)` | Removes sponsored wallpapers, news feed and promo cards. |
| **Keep Tabs Open** | `bytecodePatch` | `true` (Enabled) | None | Stops Brave from minimizing your tabs in the background. |
| **Remove Extra Files** | `rawResourcePatch` | `false` (Opt-in) | None | Deletes unused AI, VPN and AR files to shrink the app. |
| **Silence Promo Notifications** | `bytecodePatch` | `true` (Enabled) | None | Stops tips, reward promos and marketing notifications. |
| **Brave Origin (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Turns on Origin preference switches by default. |
| **Brave Origin** | `bytecodePatch` | `true` (Enabled) | `Brave Origin (Setup)`, `Faster Startup` (native extraction and BTI patches) | Unlocks Brave Origin feature switches. |
| **Faster Startup** | `bytecodePatch` | `true` (Enabled) | `braveNativeExtractionPatch`, `braveBtiCompatibilityPatch` | Speeds up launch by disabling carrier customizations. |
| **Block Popups & Rating Requests** | `bytecodePatch` | `true` (Enabled) | None | Blocks rating popups, review requests and promo dialogs. |
| **Select Previous Tab on Close** | `bytecodePatch` | `true` (Enabled) | `sharedExtensionPatch` | Selects the previous tab in the tab group when closing a tab. |

---

## 3. Technical Breakdown

### A. Telemetry & Background Sync Neutralization
- **Stop Background Sync**: Forces background sync check to return true (disabled), preventing periodic background tasks.
- **Block Trackers & Hosts**: Disables analytics preference toggles in settings resources, neutralizes crash dump uploads, experiment synchronization, and redirects telemetry server endpoints to `0.0.0.0`.

### B. Interface & Promo Suppression
- **Clean Start Page**: Disables sponsored background images, Brave News, and marketing cards by modifying default XML preferences and feed view models. Supports the `hideTopSites` option (`default = false`) to hide top site tiles.
- **Silence Promo Notifications**: Neutralizes scheduling and dispatch of promotional notifications, Brave Rewards onboarding tips, and marketing alerts.
- **Block Popups & Rating Requests**: Disables in-app rating eligibility checks, Play Store rating prompt dialogs, and promotional sign-up modals.

### C. Browser Navigation & Performance
- **Keep Tabs Open**: Disables inactive tab suspension and automatic tab minimization.
- **Select Previous Tab on Close**: Preselects the predecessor tab within the same tab group when the active tab is closed.
- **Faster Startup**: Disables asynchronous partner browser customization checks during startup, forces native library extraction in the manifest, and applies AArch64 Branch Target Identification compatibility adjustments to native binaries.
- **Brave Origin**: Unlocks Brave Origin feature switches and internal policy gatekeepers across Rewards, News, Wallet, and VPN surfaces.

### D. Resource Debloating
- **Remove Extra Files**: Zeroes unused native companion libraries in-situ, including Leo AI assets, VPN libraries, and AR components across target ABIs.

---

## 4. Known Limitations

- **Binary Stripping**: Applying native file removal zeroes selected components in-situ; features depending on those libraries (e.g. Leo AI or VPN) will become unavailable.
- **Standalone Builds**: Patches target official standalone release APKs (`Bravemonoarm64.apk` or `BraveMonoarm.apk`); split or bundle variants are unsupported.
