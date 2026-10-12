---
name: privacy-controls
description: Methodology and patterns for user-controlled privacy axes in Morphe patches: screen and audio capture protection bypass (FLAG_SECURE, allowAudioPlaybackCapture), user-selected permission removal, and opt-in offline mode. Use when building dedicated per-app privacy-control patches.
---

<!-- Shared skill: canonical source is kveld-morphe-patches; scripts/sync_shared_skills.sh mirrors it byte-identically into kveld-extra-morphe-patches (.claude/skills is a symlink to .agents/skills in each repo). Edit only in kveld-morphe-patches; the sibling pre-commit hook rejects direct edits. -->

# Privacy Controls: Capture, Permissions & Offline Guidelines

## 1. Scope & Preservation Rules

This skill governs three user-controlled privacy axes implemented as universal patches in the Morphe ecosystem:
1. **Screen and audio capture protection bypass**: neutralizing `FLAG_SECURE`, enabling `allowAudioPlaybackCapture`, and suppressing screenshot/recording detection callbacks.
2. **User-selected permission removal**: stripping sensitive hardware, location, contact, and sensor permissions from `AndroidManifest.xml`.
3. **Opt-in offline mode**: removing network access permissions and enforcing cleartext traffic blocks.

### Mandatory Preservation Invariants

- **Strict Opt-In Invariant**: Every privacy-control axis and configurable option must remain an explicit user opt-in (`default = false`):
  - Screen capture bypass (`UniversalScreenshotProtectionBypassPatch.kt:28-32,61-65`): `screenshotProtectionBypassResourcePatch` ("Allow Screen Capture (Setup)") has `default = false`; `universalScreenshotProtectionBypassPatch` ("Allow Screenshots") has `default = false`.
  - Privacy permissions stripper (`UniversalPrivacyPermissionsPatch.kt:128-132,135-205`): `universalPrivacyPermissionsPatch` ("Remove Permissions") has `default = false`; all 9 boolean options (`stripNotifications`, `stripCamera`, `stripMicrophone`, `stripMediaAndStorage`, `stripLocation`, `stripContacts`, `stripCalendar`, `stripNearbyDevices`, `stripSensors`) have `default = false`.
  - Offline mode (`UniversalOfflinePatch.kt:102-106,108-146`): `universalOfflinePatch` ("Go Fully Offline") has `default = false`; `stripNetworkState` has `default = false`. Secondary options (`stripWifiControls = true`, `stripPush = false`, `stripGoogleServices = false`, `blockCleartext = true`) execute only when the parent patch is explicitly enabled by the user.
- **Sanctioned Network Access Removal**:
  - The offline axis is the **only** sanctioned removal of `android.permission.INTERNET` in the repository.
  - In telemetry-blocking and compatibility patches, stripping `android.permission.INTERNET` or `android.permission.ACCESS_NETWORK_STATE` is strictly prohibited (`compat-bypass/SKILL.md:302`).
  - Offline mode does not relax this prohibition for other patch types; stripping `INTERNET` is permitted solely within an explicit, dedicated offline patch opted into by the user.
- **Offline Applicability Gate**:
  - Create a dedicated offline patch only when the app's core function works without network (offline-first tools, local utilities, hardware controllers, readers or editors of local files).
  - Never create one for apps whose primary function requires network (streaming, social feeds, messaging, cloud sync, online services). Record the decision and the reason in the app guide.
- **Keep-App-Launchable Invariant**:
  - `stripNetworkState` defaults to `false` (`UniversalOfflinePatch.kt:110-114`) to prevent fatal `SecurityException` crashes in applications that query `ConnectivityManager` or network status without error handling.
  - Stripping permissions or disabling network connectivity must never prevent application process startup or cause unhandled fatal exceptions.
- **Diagnostic Telemetry**: Every patch must emit standardized, high-signal telemetry with bracketed prefixes (`[Universal Screenshot Protection Bypass]`, `[Universal Privacy Permissions Stripper]`, `[Universal Offline Mode]`), dynamic mutation counts, and explicit reasons when skipping execution.

---

## 2. Analysis Methodology

Audit target APK manifests and bytecode across each privacy axis using the exact detection mechanisms from the universal implementations:

### A. Capture Protection Reconnaissance
1. **Manifest Audio Capture**: Inspect `<application>` for `android:allowAudioPlaybackCapture` (`UniversalScreenshotProtectionBypassPatch.kt:40-54`).
2. **Window & Layout Flags**: Search for invocations of `Landroid/view/Window;->addFlags(I)V` (`INVOKE_VIRTUAL`/`INVOKE_VIRTUAL_RANGE`), `Landroid/view/Window;->setFlags(II)V`, or writes (`iput`) to `Landroid/view/WindowManager$LayoutParams;->flags:I` (`UniversalScreenshotProtectionBypassPatch.kt:184-209`).
3. **SurfaceView Security**: Check for `Landroid/view/SurfaceView;->setSecure(Z)V` calls (`UniversalScreenshotProtectionBypassPatch.kt:211-218`).
4. **Audio Capture Policies**: Identify `Landroid/media/AudioAttributes$Builder;->setAllowedCapturePolicy(I)V` and `Landroid/media/AudioManager;->setAllowedCapturePolicy(I)V` (`UniversalScreenshotProtectionBypassPatch.kt:224-240`).
5. **Detection & Recents Callbacks**: Identify `registerScreenCaptureCallback`, `unregisterScreenCaptureCallback`, `setRecentsScreenshotEnabled`, `addScreenRecordingCallback`, and `removeScreenRecordingCallback` on `Landroid/app/Activity;` (`UniversalScreenshotProtectionBypassPatch.kt:242-293`).

### B. Permission Removal Reconnaissance
1. **Manifest Permission Tags**: Enumerate `<uses-permission>` and `<uses-permission-sdk-23>` tags in `AndroidManifest.xml` (`UniversalPrivacyPermissionsPatch.kt:103-104`, `ManifestXml.kt:12`).
2. **Permission Name Extraction**: Check `android:name`, namespace `name` (`http://schemas.android.com/apk/res/android`), and bare `name` attributes (`UniversalPrivacyPermissionsPatch.kt:89-95`).
3. **Categorized Permission Groups**:
   - Notifications: `android.permission.POST_NOTIFICATIONS` (`UniversalPrivacyPermissionsPatch.kt:10-12`).
   - Camera: `android.permission.CAMERA` (`UniversalPrivacyPermissionsPatch.kt:14-16`).
   - Microphone: `RECORD_AUDIO`, `CAPTURE_AUDIO_OUTPUT` (`UniversalPrivacyPermissionsPatch.kt:18-21`).
   - Media & Storage: `READ_EXTERNAL_STORAGE`, `WRITE_EXTERNAL_STORAGE`, `MANAGE_EXTERNAL_STORAGE`, `READ_MEDIA_IMAGES`, `READ_MEDIA_VIDEO`, `READ_MEDIA_AUDIO`, `READ_MEDIA_VISUAL_USER_SELECTED`, `ACCESS_MEDIA_LOCATION` (`UniversalPrivacyPermissionsPatch.kt:23-32`).
   - Location: `ACCESS_FINE_LOCATION`, `ACCESS_COARSE_LOCATION`, `ACCESS_BACKGROUND_LOCATION` (`UniversalPrivacyPermissionsPatch.kt:34-38`).
   - Contacts: `READ_CONTACTS`, `WRITE_CONTACTS`, `GET_ACCOUNTS` (`UniversalPrivacyPermissionsPatch.kt:40-44`).
   - Calendar: `READ_CALENDAR`, `WRITE_CALENDAR` (`UniversalPrivacyPermissionsPatch.kt:46-49`).
   - Nearby Devices: `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`, `BLUETOOTH_ADVERTISE`, `NEARBY_WIFI_DEVICES`, `UWB_RANGING` (`UniversalPrivacyPermissionsPatch.kt:51-57`).
   - Sensors: `BODY_SENSORS`, `BODY_SENSORS_BACKGROUND`, `ACTIVITY_RECOGNITION` (`UniversalPrivacyPermissionsPatch.kt:59-63`).

### C. Offline Mode Reconnaissance
1. **Network Permissions**: Inspect `android.permission.INTERNET`, network state permissions (`ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE`), Wi-Fi controls (`CHANGE_NETWORK_STATE`, `CHANGE_WIFI_STATE`, `CHANGE_WIFI_MULTICAST_STATE`, `NEARBY_WIFI_DEVICES`, `OVERRIDE_WIFI_CONFIG`), push permissions (`com.google.android.c2dm.permission.RECEIVE`), and Google sync (`com.google.android.providers.gsf.permission.READ_GSERVICES`, `android.permission.GET_ACCOUNTS`) (`UniversalOfflinePatch.kt:10-33`).
2. **Cleartext Traffic Policy**: Inspect `android:usesCleartextTraffic` on `<application>` (`UniversalOfflinePatch.kt:86-99`).
3. **Core-Function Network Dependency**: Classify whether the app's primary features work with network disabled (launch the unpatched APK in airplane mode and exercise the core flow). Apply the Offline Applicability Gate (section 1) before planning any offline patch.

---

## 3. Implementation Patterns per Axis

### A. Capture Protection Bypass
- **Universal Pattern** (`UniversalScreenshotProtectionBypassPatch.kt`):
  - *Manifest*: `screenshotProtectionBypassResourcePatch` sets `android:allowAudioPlaybackCapture="true"` on `<application>` (lines 50-54).
  - *Window Flags*: Prepends `and-int/lit16 v$reg, v$reg, -0x2001` before `addFlags`, `setFlags`, or `iput LayoutParams.flags` to mask out `FLAG_SECURE` (`0x2000`) (lines 20, 306, 313, 321):
    ```smali
    and-int/lit16 v0, v0, -0x2001
    ```
  - *SurfaceView*: Prepends `const/4 v$reg, 0x0` before `SurfaceView.setSecure(Z)` (line 331).
  - *Audio Capture*: Prepends `const/4 v$reg, 0x1` before `setAllowedCapturePolicy(I)` to enforce `ALLOW_CAPTURE_BY_ALL = 1` (line 340).
  - *Detection Suppression*: Replaces `registerScreenCaptureCallback`, `unregisterScreenCaptureCallback`, and `removeScreenRecordingCallback` with `nop` (line 352). Prepends `const/4 v$reg, 0x1` before `setRecentsScreenshotEnabled(Z)` (line 358). Replaces `addScreenRecordingCallback` with `nop` and replaces its `move-result` with `const/4 v$reg, 0x0` (lines 370-372).
  - *Guards*: Skips flag mutation if register `>= 16` (`and-int/lit16` assembler addressing limitation; lines 302, 309, 318). Verifies register `< 256` for `const/4` / `const/16` (lines 329, 339, 357, 367). Applies mutations in descending instruction index order (line 133).
- **Dedicated Per-App Variant Pattern**:
  - Target app-specific activities, layout builders, or media views by `Fingerprint` instead of executing a full-APK `classDefForEach` scan.
  - Apply identical bitmasking (`and-int/lit16` with `-0x2001`) or constant injections directly at targeted call sites.
  - Maintain `default = false`.

### B. Permission Removal
- **Universal Pattern** (`UniversalPrivacyPermissionsPatch.kt`):
  - *Manifest*: Evaluates 9 opt-in boolean options (`default = false`), builds a blocked permission set (lines 75-86), and prunes matching elements from `PERMISSION_TAGS` (`uses-permission`, `uses-permission-sdk-23`) via DOM removal (lines 103-122).
  - *Guards*: Early-exits if `AndroidManifest.xml` is missing or if no options are selected (lines 208-239).
- **Dedicated Per-App Variant Pattern**:
  - Target the specific subset of permissions used by the app under a dedicated patch name.
  - *Guidance*: If an app's bytecode checks stripped permissions via `checkSelfPermission` and crashes when missing, accompany manifest stripping with bytecode hooks returning `PackageManager.PERMISSION_GRANTED` (`0`) or stubbing the dependent feature callers.

### C. Offline Mode
- **Universal Pattern** (`UniversalOfflinePatch.kt`):
  - *Manifest*: Unconditionally strips `android.permission.INTERNET` when the patch is enabled (line 40). Strips optional permission groups based on options: `stripNetworkState` (`default = false`), `stripWifiControls` (`default = true`), `stripPush` (`default = false`), and `stripGoogleServices` (`default = false`) (lines 108-138).
  - *Cleartext Policy*: When `blockCleartext` is enabled (`default = true`), sets `android:usesCleartextTraffic="false"` on `<application>` (lines 97, 140-146).
  - *Guards*: Early-exits if no permissions were removed and cleartext was already blocked (lines 178-181).
- **Dedicated Per-App Variant Pattern**:
  - Combine manifest permission stripping with targeted hooks neutralizing app-specific network engines (e.g. OkHttpClient builders, Cronet initializers, or sync dispatchers).
  - Maintain `default = false` and ensure `stripNetworkState` remains optional to prevent crashes.

---

## 4. When a Dedicated Variant Is Justified

A dedicated per-app privacy patch is justified when the universal patch is insufficient due to structural source limitations:

1. **High Scan Overhead on Large APKs**: `UniversalScreenshotProtectionBypassPatch` walks all classes and methods via `classDefForEach` (`UniversalScreenshotProtectionBypassPatch.kt:76-91`), causing heavy scan times on large codebases. A dedicated patch resolves targets instantly via indexed fingerprints.
2. **Assembler Addressing Limits (Registers >= 16)**: `UniversalScreenshotProtectionBypassPatch` skips flag sites when the target register is `>= 16` (`UniversalScreenshotProtectionBypassPatch.kt:165-167, 302-320`) because `and-int/lit16` only addresses registers `0` through `15`. A dedicated patch can allocate lower registers or use register-copy instructions.
3. **Proprietary Wrappers & JNI**: Apps that apply `FLAG_SECURE` through native JNI, reflection, or internal helper classes bypass framework-level call-site checks. A dedicated patch hooks the app's proprietary entrypoints directly.
4. **Custom Renderers & WebViews**: Secure surfaces managed by custom engines (e.g. Flutter platform views, React Native bridges) require app-specific hooks.
5. **Runtime Permission Checks**: Universal permission stripping removes manifest tags but does not modify bytecode. If an app expects a permission and crashes on missing grants without catch blocks, a dedicated variant must stub the corresponding runtime check.
6. **Graceful Offline Degradation**: Apps that crash when network initialization fails require dedicated hooks to mock offline state and bypass forced network initialization loops.

---

## 5. Verification

Verify applied patches using automated gates, manifest inspections, and runtime checks:

### A. Manifest Verification (`aapt2 dump xmltree`)
Inspect the generated APK to assert manifest transformations:
```bash
# Verify removal of target permissions (e.g. INTERNET, CAMERA, POST_NOTIFICATIONS)
aapt2 dump xmltree --file AndroidManifest.xml build/test-<app>.apk | grep "android:name" | grep -E "INTERNET|CAMERA|POST_NOTIFICATIONS"

# Verify audio playback capture attribute
aapt2 dump xmltree --file AndroidManifest.xml build/test-<app>.apk | grep "android:allowAudioPlaybackCapture"

# Verify cleartext traffic block
aapt2 dump xmltree --file AndroidManifest.xml build/test-<app>.apk | grep "android:usesCleartextTraffic"
```

### B. In-Situ Morphe Patcher Gate
Execute the patching test with all options enabled:
```bash
./gradlew runPatchTest -Papp=<app_id> -Papk=<apk> -PallOptions=true -Pout=build/test-<app_id>.apk
```
The run must complete with exit code `0`, 0 failed patches, 0 fingerprint mismatches, and 0 smali compile errors.

### C. Device Validation per Axis
1. **Capture Protection**: Take a screenshot via `adb shell screencap -p /sdcard/screen.png` or record video while on a protected screen. Confirm the capture is visible and not blacked out. Verify the recent apps overview displays the window content.
2. **Permission Removal**: Check installed package permissions:
   ```bash
   adb shell dumpsys package <package_name> | grep -A 20 "requested permissions:"
   ```
   Assert that stripped permissions are absent from the list.
3. **Offline Mode**: Launch the app without network access (or in airplane mode). Assert that the application launches cleanly, does not throw unhandled `SecurityException` crashes, and functions offline with graceful degradation.
