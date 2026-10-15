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
| **Download Target** | [APKMirror](https://www.apkmirror.com/apk/hevy-gym-workout-tracker/hevy-gym-log-workout-tracker/hevy-gym-log-workout-tracker-3-1-14-release/hevy-gym-log-workout-tracker-3-1-14-android-apk-download/) |
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
- **Stop Background Sync**:
  - *Objective*: Prevent background alarms and billing connections from draining the battery.
  - *How*: Disables background worker services, alarm receivers, and billing components in the manifest, and neutralizes background billing connection startup routines.

### B. Telemetry & Tracking Elimination
- **Block Trackers**:
  - *Objective*: Prevent transmission of usage logs, crash events, and advertising attribution data.
  - *How*: Strips advertising identifier and attribution permissions from the manifest, and stubs third-party crash reporting and event tracking methods.

### C. Pro Subscription & Feature Gating
- **Unlock Pro**:
  - *Objective*: Unlock offline workout tracking features such as unlimited routines, custom folders, and workout charts.
  - *How*: Modifies the compiled JavaScript bundle in place to force client-side subscription checks to report active Pro status.

### D. Asset Debloating
- **Remove Extra Files**:
  - *Objective*: Shrink the installed application footprint by removing unneeded media assets.
  - *How*: Purges bundled onboarding tutorial videos, editor stickers, and unused asset fonts from application resources.

---

## 4. Known Limitations

- **Server-Side Pro Assets**: Client bundle modifications unlock local Pro interface features and routine limits. Cloud-validated synchronization, social leaderboards, or remote server endpoints requiring backend entitlement checks remain gated upstream.
- **APKM Bundle Requirement**: Hevy is distributed as an APKM bundle; patching requires processing the complete bundle container.
