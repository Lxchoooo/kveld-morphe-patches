# Gboard Lite Patches Guide

Technical documentation and patch catalog for Gboard Lite on Android.

---

## 1. Target & Compatibility

| Property | Value |
| :--- | :--- |
| **Target App** | Gboard Lite |
| **Package Name** | `com.google.android.inputmethod.latin` |
| **Target Version** | `18.5.1.993608717-lite_beta-arm64-v8a` / `18.5.1.993608717-lite_beta-armeabi-v7a` |
| **Target Package Format** | standalone APK (APK nodpi) |
| **Primary Architecture** | `arm64-v8a` / `armeabi-v7a` |
| **Authoritative Source** | APKMirror |

---

## 2. Applied Patches Catalog

| Patch Name | Typology | Default State | Dependencies | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Keyboard Settings** | `resourcePatch` | `true` (Enabled) | AMOLED, Inset, Incognito, Clipboard, Feature Flags, Toolbar, Seekbar, Core Integrity, Haptics | Adds a settings screen inside Gboard: theme, vibration, clipboard and more. |
| **Block Trackers** | `bytecodePatch` | `true` (Enabled) | None | Stops background metrics, event logging and crash reporting. |
| **Install a Copy** | `resourcePatch` | `true` (Enabled) | `gboardCoreIntegrityPatch` | Installs this Gboard next to the original one. |
| **Stop Background Sync** | `bytecodePatch` | `false` (Opt-in) | None | Stops background downloads and sync to save battery. |
| **Disable Cloud Backup** | `resourcePatch` | `true` (Enabled) | None | Keeps keyboard data off Google Drive backups. |
| **Stop Remote Updates** | `bytecodePatch` | `true` (Enabled) | None | Stops Google from changing settings remotely. |
| **Disable Play Services** | `bytecodePatch` | `false` (Opt-in) | None | Runs without Google Play services. Also turns off inline Translate. |
| **Block App Hijacking** | `bytecodePatch` | `true` (Enabled) | `gboardRemoveWebDebugBridgePatch` | Protects against other apps hijacking Gboard and removes debug tools. |
| **Go Offline (Setup)** | `resourcePatch` | `false` (Opt-in) | None | Removes network permissions. |
| **Offline Only** | `bytecodePatch` | `false` (Opt-in) | `Go Offline (Setup)` | Fully disconnects Gboard. Download dictionaries first. |
| **Remove Extra Files** | `resourcePatch` | `true` (Enabled) | None | Deletes licenses, tutorial animations and junk. |
| **Remove Permissions** | `resourcePatch` | `false` (Opt-in) | None | Removes permissions you pick below. |

---

## 3. Technical Breakdown

### A. Modular Settings Sub-Patches
The `Keyboard Settings` patch incorporates several internal bytecode and resource layers:
- **Pure Black (AMOLED)**: Replaces default dark theme background definitions with pure black (`#000000`) color values.
- **Zero Bottom Inset & Custom Padding**: Bypasses system navigation bar insets and provides user-configurable bottom padding.
- **Force Incognito Mode**: Enforces incognito keyboard input mode, hides the incognito indicator icon, and guards clipboard capture during private sessions.
- **Voice Typing Incognito**: Forces speech recognition to run in private mode without remote transcript logging.
- **Clipboard Enhancements**: Extends clipboard retention time limits, raises unpinned item counts, enables grid layout mode, and expands character limits.
- **Modern Haptics & Decoupled Feedback**: Separates keyboard haptics from system touch vibration toggles and unlocks modern haptic feedback patterns.
- **Top Toolbar Customization**: Adjusts the number of visible items on the top access points bar.

### B. Telemetry & Remote Control Suppression
- **Block Trackers**: Disables event logging, Clearcut metrics, and crash reporting services.
- **Stop Remote Updates**: Neutralizes Google Phenotype configuration synchronization, preventing server-driven experiment flag overwrites.
- **Disable Cloud Backup**: Strips cloud backup transport agents from the application manifest.
- **Block App Hijacking**: Restricts exported broadcast receivers and purges debugging bridge components.

### C. Offline Operation & Permission Stripping
- **Offline Only**: Strips network permissions (`INTERNET`, `ACCESS_WIFI_STATE`), disables background sync services, and forces network monitors to report offline state.
- **Disable Play Services**: Bypasses Google Play Services availability checks; inline Google Translate is disabled as a result.
- **Remove Permissions**: Opt-in removal of sensitive permissions including Contacts, Microphone, Storage, and Notifications.

---

## 4. Known Limitations

- **Offline Mode Prerequisites**: Offline patches completely sever network access. Language packs, layout models, and dictionaries must be installed prior to enabling offline enforcement.
- **Play Services Decoupling**: Disabling Google Play Services breaks cloud-dependent features such as inline translation.
- **Permission Removal Effects**: Stripping optional permissions directly disables corresponding features (e.g. removing Contacts disables contact name autocompletion suggestions).
