# Hevy Patches Guide

Technical documentation and patch catalog for Hevy Gym Log Workout Tracker on Android.

---

## 1. Target & Compatibility

| Property | Value |
| :--- | :--- |
| **Target App** | Hevy - Gym Log Workout Tracker |
| **Package Name** | `com.hevy` |
| **Target Version** | `3.1.14` |
| **Target Package Format** | APKM bundle |
| **Primary Architecture** | `arm64-v8a` / `armeabi-v7a` |
| **Authoritative Source** | APKMirror |

---

## 2. Applied Patches Catalog

| Patch Name | Typology | Default State | Dependencies | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Stop Background Sync (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Turns off billing components and background services. |
| **Stop Background Sync** | `bytecodePatch` | `true` (Enabled) | `Stop Background Sync (Setup)` | Stops background sync tasks and alarms that drain the battery. |
| **Remove Trackers (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Removes tracking permissions and turns off crash-reporting providers. |
| **Block Trackers** | `bytecodePatch` | `true` (Enabled) | `Remove Trackers (Setup)` | Blocks crash reporting, ad attribution and referral tracking. |
| **Remove Extra Files** | `resourcePatch` | `true` (Enabled) | None | Deletes tutorial videos, editor stickers and junk to shrink the app. |
| **Unlock Pro** | `rawResourcePatch` | `false` (Opt-in) | None | Unlocks Pro features stored on the device (routines, folders, charts). Server-limited items may still need a subscription. |

---

## 3. Technical Breakdown

### A. Background Sync & Battery Optimization
- **Manifest Component Disabling**: Disables billing services, background work managers, and job schedulers in `AndroidManifest.xml`.
- **Bytecode Alarms & Sync Neutralization**: Neutralizes periodic synchronization alarms and background worker dispatchers.

### B. Telemetry & Tracking Elimination
- **Permission Stripping**: Removes ad and tracking permissions (`ACCESS_ADSERVICES_AD_ID`, `ACCESS_ADSERVICES_ATTRIBUTION`, `BIND_GET_INSTALL_REFERRER_SERVICE`).
- **Provider & Dispatcher Neutralization**: Disables third-party crash analytics initialization providers, AppsFlyer referral tracking, and event loggers.

### C. Pro Subscription & Feature Gating
- **Unlock Pro**: Modifies compiled JavaScript bundles (`index.android.bundle`) in-situ to force Pro entitlements (`isPro = true`, `hasActiveSubscription = true`).
- Enables client-side Pro capabilities such as unlimited routines, custom workout folders, advanced statistics, and charts.

### D. Asset Debloating
- **Remove Extra Files**: Purges bundled tutorial media, uncompressed promotional videos, and unused graphic assets from application resources.

---

## 4. Known Limitations

- **Server-Side Pro Assets**: Client bundle modifications unlock local Pro interface features and routine limits. Cloud-validated synchronization, social leaderboards, or remote server endpoints requiring backend entitlement checks remain gated upstream.
- **APKM Bundle Requirement**: Hevy is distributed as an APKM bundle; patching requires processing the complete bundle container.
