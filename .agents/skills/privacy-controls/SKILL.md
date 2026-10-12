---
name: privacy-controls
description: Methodology and patterns for user-controlled privacy axes in Morphe patches: screen and audio capture protection bypass (FLAG_SECURE, allowAudioPlaybackCapture), user-selected permission removal, opt-in offline mode, network security hardening, share-link tracking stripping, and runtime device-data access neutralization. Use when building dedicated per-app privacy-control patches.
---

<!-- Shared skill: canonical source is kveld-morphe-patches; scripts/sync_shared_skills.sh mirrors it byte-identically into kveld-extra-morphe-patches (.claude/skills is a symlink to .agents/skills in each repo). Edit only in kveld-morphe-patches; the sibling pre-commit hook rejects direct edits. -->

# Privacy Controls: Capture, Permissions, Offline, Network, Links & Device Data Guidelines

## 1. Scope & Preservation Rules

This skill governs three user-controlled privacy axes implemented as universal patches in the Morphe ecosystem:
1. **Screen and audio capture protection bypass**: neutralizing `FLAG_SECURE`, enabling `allowAudioPlaybackCapture`, and suppressing screenshot/recording detection callbacks.
2. **User-selected permission removal**: stripping sensitive hardware, location, contact, and sensor permissions from `AndroidManifest.xml`.
3. **Opt-in offline mode**: removing network access permissions and enforcing cleartext traffic blocks.
4. **Network security hardening**: configuring `res/xml/network_security_config.xml`, user/system certificate trust anchors, cleartext policies, and OkHttp `CertificatePinner` neutralization (per-app only).
5. **Share-link tracking stripping and in-app browser privacy**: sanitizing share intents, clipboard data, and share URLs, and redirecting web links to the system browser while suppressing in-app WebView scripts (per-app only).
6. **Runtime device-data access neutralization**: intercepting runtime queries and listeners for contacts, package inventory, location, sensors, battery status, content capture, and advertising IDs (per-app only).

### Mandatory Preservation Invariants

- **Strict Opt-In Invariant**: Every privacy-control axis and configurable option must remain an explicit user opt-in (`default = false`) for universal patches. Per-app sources default to `true` in production (with companion setup resource patches defaulting to `false`):
  - Screen capture bypass (`UniversalScreenshotProtectionBypassPatch.kt:28-32,61-65`): `screenshotProtectionBypassResourcePatch` ("Allow Screen Capture (Setup)") has `default = false`; `universalScreenshotProtectionBypassPatch` ("Allow Screenshots") has `default = false`.
  - Privacy permissions stripper (`UniversalPrivacyPermissionsPatch.kt:128-132,135-205`): `universalPrivacyPermissionsPatch` ("Remove Permissions") has `default = false`; all 9 boolean options (`stripNotifications`, `stripCamera`, `stripMicrophone`, `stripMediaAndStorage`, `stripLocation`, `stripContacts`, `stripCalendar`, `stripNearbyDevices`, `stripSensors`) have `default = false`.
  - Offline mode (`UniversalOfflinePatch.kt:102-106,108-146`): `universalOfflinePatch` ("Go Fully Offline") has `default = false`; `stripNetworkState` has `default = false`. Secondary options (`stripWifiControls = true`, `stripPush = false`, `stripGoogleServices = false`, `blockCleartext = true`) execute only when the parent patch is explicitly enabled by the user.
  - NokoPrint network security hardening (`NokoPrintNetworkSecurityHardeningPatch.kt:10`): `nokoPrintNetworkSecurityHardeningPatch` ("Safer Connections") has `default = true`.
  - Xiaomi Earbuds network security (`XiaomiEarbudsNetworkSecurityPatch.kt:13,68`): `xiaomiEarbudsNetworkSecurityConfigResourcePatch` ("Safer Connections (Setup)") has `default = false`; parent `xiaomiEarbudsNetworkSecurityPatch` ("Safer Connections") has `default = true`.
  - Chromium clean share URL (`CleanShareUrlPatch.kt:16`): `cleanShareUrlPatch` ("Clean Shared Links") has `default = true`.
  - TikTok clean share URL (`CleanShareUrlPatch.kt:15,24`): `cleanShareUrlPatch` ("Clean Share URL") has `default = true`; `shareHost` stringOption has `default = ""`.
  - TikTok in-app browser privacy guard (`InAppBrowserPrivacyGuardPatch.kt:13`): `inAppBrowserPrivacyGuardPatch` ("In-App Browser Privacy Guard") has `default = true`.
  - TikTok device privacy guard (`DevicePrivacyGuardPatch.kt:44`): `devicePrivacyGuardPatch` ("Device Privacy Guard") has `default = true`.
  - Chromium sensor privacy (`SensorPrivacyPatch.kt:13`): `sensorPrivacyPatch` ("Block Motion Sensors") has `default = true`.
  - Chromium battery optimization (`BatteryOptimizationPatch.kt:12`): `batteryOptimizationPatch` ("Hide Battery Status") has `default = true`.
  - Chromium content capture disable (`DisableContentCapturePatch.kt:12`): `disableContentCapturePatch` ("Stop Text Sharing with System") has `default = true`.
  - Xiaomi Earbuds device privacy guard (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:13,54`): `xiaomiEarbudsDevicePrivacyGuardResourcePatch` ("Location Privacy (Setup)") has `default = false`; parent `xiaomiEarbudsDevicePrivacyGuardPatch` ("Hide Device ID") has `default = true`.
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

### D. Network Security Reconnaissance
1. **Network Security Config File**: Check for existence of `res/xml/network_security_config.xml` (`NokoPrintNetworkSecurityHardeningPatch.kt:15-19`, `XiaomiEarbudsNetworkSecurityPatch.kt:18-22`).
2. **Base Config & Cleartext Policy**: Inspect `<base-config>` elements in `network_security_config.xml` for `cleartextTrafficPermitted` (`"true"` to maintain local device or printer access, `"false"` to block unencrypted transport) (`NokoPrintNetworkSecurityHardeningPatch.kt:23`, `XiaomiEarbudsNetworkSecurityPatch.kt:25-33`).
3. **Trust Anchors & Certificates**: Check `<trust-anchors>` inside `<base-config>` for `<certificates src="system" />` and `<certificates src="user" />` tags (`NokoPrintNetworkSecurityHardeningPatch.kt:24-27`, `XiaomiEarbudsNetworkSecurityPatch.kt:35-57`).
4. **OkHttp Certificate Pinner**: Scan bytecode for `Lokhttp3/CertificatePinner;` and its pinning verification methods: `check(Ljava/lang/String;Ljava/util/List;)V`, `check(Ljava/lang/String;[Ljava/security/cert/Certificate;)V`, and `check$okhttp(Ljava/lang/String;Lkotlin/jvm/functions/Function0;)V` (`XiaomiEarbudsNetworkSecurityPatch.kt:75-105`).

### E. Share-Link & In-App Browser Reconnaissance
1. **Share Intent Builders**: Search for methods returning `Landroid/content/Intent;` that reference `"android.intent.extra.TEXT"` and share origins like `"org.chromium.chrome.browser.share_origin"` (`CleanShareUrlPatch.kt:27-30` in Chromium).
2. **System Clipboard Sanitization Sites**: Search for methods accepting `Landroid/content/ClipData;` (e.g. `ClipboardImpl.setPrimaryClip` matching `"google"`) or `Lorg/chromium/ui/base/Clipboard;->setText(Ljava/lang/String;)V` (`CleanShareUrlPatch.kt:57-60,79-83` in Chromium).
3. **Model Share URL Getters**: Search for model getters returning share URLs, such as `Lcom/ss/android/ugc/aweme/feed/model/Aweme;->getShareUrl()Ljava/lang/String;` (`CleanShareUrlPatch.kt:56-60` in TikTok).
4. **WebView JavaScript Injection Predicates**: Inspect predicates returning boolean that gate inline JS injection, such as methods matching `"webview_inline_inject_js"` with parameter `Landroid/webkit/WebView;` (`InAppBrowserPrivacyGuardPatch.kt:23-27`).
5. **WebView AJAX / DOM Hookers**: Inspect `Lcom/ss/android/ugc/aweme/compliance/sandbox/webview/WebViewAjaxHooker;->onPageStarted(Landroid/webkit/WebView;Ljava/lang/String;Landroid/graphics/Bitmap;)V` (`InAppBrowserPrivacyGuardPatch.kt:42-47`).
6. **In-App Router / Dispatcher & System Browser Openers**: Identify external web routers such as `SparkThirdContext` dispatchers matching `"ContainerId"`, `"Context_startActivity_1"`, or popup dispatchers (`InAppBrowserPrivacyGuardPatch.kt:70-86`), and check commercial/anchor models for `getOpenSystemBrowser()Z` (e.g. `AnchorInfoStruct`) (`InAppBrowserPrivacyGuardPatch.kt:92-106`).

### F. Device-Data Access Reconnaissance
1. **Runtime Permission Dispatchers & Cache**: Inspect permission dispatcher fragments (e.g. `FakeFragment` handling `HashSet` in PowerPermissions), denial cache checkers (e.g. `LX/04CR;->LIZ(Ljava/lang/String;)Z`), and settings redirectors (e.g. `LX/06WZ;->LJI(Activity, String, Z)Z`) (`DevicePrivacyGuardPatch.kt:58-114`).
2. **Location Managers & Scopes**:
   - Manifest permissions: inspect `ACCESS_FINE_LOCATION` and `ACCESS_COARSE_LOCATION` (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:24-27`).
   - Call sites on `Landroid/location/LocationManager;`: `getLastKnownLocation(Ljava/lang/String;)Landroid/location/Location;`, `requestSingleUpdate(...)`, `isProviderEnabled(Ljava/lang/String;)Z`, and `isLocationEnabled()Z` (`DevicePrivacyGuardPatch.kt:19-39,701-838`).
   - App-level location services and startup tasks: `LocationServiceImpl`, location init tasks (`InitLocationTask`), and scene permission check methods (`LX/0AwX`) (`DevicePrivacyGuardPatch.kt:120-217`).
   - Bluetooth BLE location gating: check methods like `isLocationEnable(Context)Z`, `isGpsEnable(Context)Z`, `getLocationPermissions()[String`, and `hasScanCondition()Z` (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:199-296`).
3. **Contacts Queries & Prompts**:
   - In-app auth dialogs and sync tasks: `RelationAuthDialogControl`, `ContactsUploadRequest`, `PermissionRequestAndUploadLegoTask`, and onboarding triggers (`DevicePrivacyGuardPatch.kt:223-329`).
   - Call sites on `Landroid/content/ContentResolver;`: `query(...)` with 4, 5, or 6 arguments returning `Landroid/database/Cursor;` querying contacts URIs (`DevicePrivacyGuardPatch.kt:448-624`).
4. **Package Inventory Inspection**: Call sites on `Landroid/content/pm/PackageManager;`: `queryIntentActivities(Landroid/content/Intent;I)Ljava/util/List;` querying external packages (`DevicePrivacyGuardPatch.kt:637-688`).
5. **Advertising ID & Hardware Identifiers**:
   - Google Play Services AdvertisingIdClient: `AdvertisingIdClient$Info` getters (`LLLLIILL`) and ID strings (`LLLLIIL`) (`DevicePrivacyGuardPatch.kt:335-361`).
   - Vendor privacy/hardware ID managers: `PrivacyDataMaster` (`get`, `forceGet`), `AccountDeviceIdManager` (`getDeviceId`, `getHashedDeviceId`, `syncGetDeviceId`), and environment info arrays (`PassportUserEnvironment->getEnvInfoArray`) (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:63-196`).
6. **Clipboard Snooping**: In-app messenger clipboard services (`IMMessageListClipboardServiceImpl`) and BPEA clipboard read wrappers (`ClipboardManager`, `Cert`) returning `ClipData` (`DevicePrivacyGuardPatch.kt:367-394`).
7. **Motion Sensors, HAR & Battery**:
   - Human Activity Recognition services (`SmartHARServiceImpl->enable()Z`, `checkAndInit()V`) (`DevicePrivacyGuardPatch.kt:401-427`).
   - Chromium sensor providers: `PlatformSensorProvider->hasSensorType(I)Z` and `PlatformSensor->create(PlatformSensorProvider, I, J)` (`SensorPrivacyPatch.kt:21-52`).
   - Battery broadcast receivers: `BATTERY_CHANGED` intent filters and `cr_BatteryStatusManager` receivers (`BatteryOptimizationPatch.kt:17-31`).
8. **System Content Capture**: Onscreen text capture providers dispatching to Android ContentCapture service: `OnscreenContentProvider->shouldCapture(String)Z` (`DisableContentCapturePatch.kt:18-26`).

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

### D. Network Security Hardening
- **Production Techniques**:
  - *Network Security Config Rewrite or DOM Injection*: Modify `res/xml/network_security_config.xml` directly or via DOM document. Inject `<trust-anchors>` with `<certificates src="system" />` and `<certificates src="user" />` inside `<base-config>` to enable user CA certificate trust for TLS inspection (`NokoPrintNetworkSecurityHardeningPatch.kt:21-32`, `XiaomiEarbudsNetworkSecurityPatch.kt:24-58`).
  - *Cleartext Policy Configuration*: Configure `cleartextTrafficPermitted` on `<base-config>`:
    - Set `cleartextTrafficPermitted="true"` when local unencrypted network transport is required for hardware discovery or printer downloads (`NokoPrintNetworkSecurityHardeningPatch.kt:23`).
    - Set `cleartextTrafficPermitted="false"` when enforcing end-to-end encrypted HTTPS traffic (`XiaomiEarbudsNetworkSecurityPatch.kt:33`).
  - *OkHttp Certificate Pinner Neutralization*: Stub all `check` overloads in `Lokhttp3/CertificatePinner;` with `return-void` at instruction index 0 (`XiaomiEarbudsNetworkSecurityPatch.kt:77-105`):
    ```smali
    return-void
    ```
    Hooks cover `check(String, List)` (`XiaomiEarbudsNetworkSecurityPatch.kt:77-85`), `check(String, Certificate[])` (`XiaomiEarbudsNetworkSecurityPatch.kt:87-95`), and Kotlin-mangled `check$okhttp(String, Function0)` (`XiaomiEarbudsNetworkSecurityPatch.kt:97-105`).
- **Preservation Rules Guarded in Sources**:
  - *Local Hardware and Printer Preservation*: Never force `cleartextTrafficPermitted="false"` on applications that communicate with local network hardware, local printers, or embedded device HTTP servers (`NokoPrintNetworkSecurityHardeningPatch.kt:9,23`).
  - *Companion Setup Isolation*: Keep XML configuration in a companion `resourcePatch` (`default = false`) chained to the main bytecode patch (`default = true`) via `dependsOn(...)` (`XiaomiEarbudsNetworkSecurityPatch.kt:10-15,65-71`).
- **Anti-Patterns**:
  - Enforcing blanket cleartext traffic blocks on apps requiring plain HTTP for local hardware discovery, breaking local device functionality.
  - Neutralizing only public Java `check` methods while omitting Kotlin-mangled overloads like `check$okhttp`, leaving coroutine or Kotlin-based network calls pinned and failing under TLS proxies.

### E. Share-Link Tracking Stripping & In-App Browser Privacy
- **Production Techniques**:
  - *Share Intent Sanitization*: Intercept return points (`Opcode.RETURN_OBJECT`) in Share Intent builders matching `"android.intent.extra.TEXT"` and `"share_origin"` strings. Traverse return points in reverse order (`returnIndices.asReversed()`) and inject sanitizers at control flow labels (`CleanShareUrlPatch.kt:37-45` in Chromium):
    ```smali
    invoke-static {v$reg}, Lcom/kveld9/morphe/extension/ChromiumExtension;->cleanShareIntent(Landroid/content/Intent;)Landroid/content/Intent;
    move-result-object v$reg
    ```
  - *System Clipboard Sanitization*: Hook `ClipboardImpl.setPrimaryClip(ClipData)` prepending sanitizer at index 0 (`CleanShareUrlPatch.kt:61-68` in Chromium):
    ```smali
    invoke-static {p1}, Lcom/kveld9/morphe/extension/ChromiumExtension;->cleanClipData(Landroid/content/ClipData;)Landroid/content/ClipData;
    move-result-object p1
    ```
    Hook fallback `Clipboard.setText(String)` to pass text through `cleanShareUrl(String)` (`CleanShareUrlPatch.kt:83-90` in Chromium).
  - *App-Level Share URL Sanitization with Host Redirection*: Hook model share URL getters (e.g. `Aweme.getShareUrl()`) at all `RETURN_OBJECT` points using `invoke-static/range` (`CleanShareUrlPatch.kt:67-75` in TikTok):
    ```smali
    invoke-static/range {v$reg .. v$reg}, Lcom/kveld9/morphe/extension/tiktok/TikTokShareHostHook;->sanitizeShareUrlWithHost(Ljava/lang/String;)Ljava/lang/String;
    move-result-object v$reg
    ```
    Support custom share host substitution via `stringOption` by injecting `sput-object` into `<clinit>` (`CleanShareUrlPatch.kt:35-49` in TikTok).
  - *In-App Browser Neutralization & External Redirection*:
    - Suppress inline JS injection by forcing predicate to return false (`const/4 v0, 0` / `return v0`) (`InAppBrowserPrivacyGuardPatch.kt:28-34`).
    - Suppress AJAX/DOM tracking hooks by stubbing `WebViewAjaxHooker.onPageStarted` with `return-void` (`InAppBrowserPrivacyGuardPatch.kt:48-53`).
    - Redirect external web routers (e.g. `SparkThirdContext` dispatchers) to the system browser (`InAppBrowserPrivacyGuardPatch.kt:60-67,75-85`):
      ```smali
      invoke-static {p0, p1}, Lcom/kveld9/morphe/extension/tiktok/TikTokBrowserHook;->redirectSparkThird(Ljava/lang/Object;Ljava/lang/Object;)Z
      move-result v0
      if-eqz v0, :cond_skip
      return-void
      :cond_skip
      nop
      ```
    - Force commercial/anchor model `getOpenSystemBrowser()` to return `true` (`const/4 v0, 0x1` / `return v0`) (`InAppBrowserPrivacyGuardPatch.kt:101-106`).
- **Preservation Rules Guarded in Sources**:
  - *Domain-Scoped Parameter Stripping*: Distinguish between global adtech tracking parameters (`fbclid`, `gclid`, `mc_cid`) and domain-scoped tokens (e.g. `si` on YouTube/Spotify) to prevent stripping functional query parameters (`ChromiumExtension.java:34-80`).
  - *External Redirection Fallback*: Check whether the external browser intent dispatch succeeded before aborting internal navigation (`if-eqz v0, :cond_skip`) (`InAppBrowserPrivacyGuardPatch.kt:63-66`).
- **Anti-Patterns**:
  - Running complex regular expression matching in main thread share/clipboard paths; use deterministic O(1) hash set lookups on parsed query parameters (`ChromiumExtension.java:23-28`).
  - Indiscriminately intercepting internal WebViews required for authentication, payments, or core account flows.

### F. Runtime Device-Data Access Neutralization
- **Production Techniques**:
  - *Permission Framework & Denial Interception*:
    - Intercept runtime permission dispatchers (e.g. `FakeFragment` HashSet dispatcher) and simulate asynchronous denial callbacks without prompting the user (`DevicePrivacyGuardPatch.kt:63-72`, `TikTokPrivacyHook.java:77-87,112-123`).
    - Neutralize denial cache flags (e.g. `LX/04CR->LIZ` -> return false) and settings redirection handlers (`LX/06WZ->LJI` -> return false) to prevent repetitive open-settings prompts (`DevicePrivacyGuardPatch.kt:82-91,102-111`).
    - Suppress relation onboarding dialogs, Facebook sync prompts, and background upload tasks (`RelationAuthDialogControl`, `ContactsUploadRequest`) by returning `Boolean.FALSE` or `return-void` (`DevicePrivacyGuardPatch.kt:227-286`).
  - *ContentResolver Contacts Query Interception*:
    - Pre-scan candidate methods with call-site filters (`DevicePrivacyGuardPatch.kt:19-39,431`).
    - **Insert-Only Register Safety**: Avoid instruction removal or `ensureRegisterCount` (which shifts parameter registers and causes `VerifyError`). Inject range-singletons immediately after `MOVE_RESULT_OBJECT` (`DevicePrivacyGuardPatch.kt:436-445,494-501`):
      ```smali
      invoke-static/range {v$uriReg .. v$uriReg}, Lcom/kveld9/morphe/extension/tiktok/TikTokPrivacyHook;->noteUri(Landroid/net/Uri;)V
      invoke-static/range {v$resultReg .. v$resultReg}, Lcom/kveld9/morphe/extension/tiktok/TikTokPrivacyHook;->filterNotedResult(Landroid/database/Cursor;)Landroid/database/Cursor;
      move-result-object v$resultReg
      ```
    - In extension helper, if URI targets contacts authorities (`contacts`, `call_log`), close the original cursor and return `new MatrixCursor(new String[0])` (`TikTokPrivacyHook.java:26-31,182-190`).
  - *PackageManager Inventory Inspection Filtering*: Intercept `PackageManager.queryIntentActivities(Intent, int)` call sites. Note intent and filter results: return full activities for targeted intents (package/component set), but return `Collections.emptyList()` for broad queries (`DevicePrivacyGuardPatch.kt:638-681`, `TikTokPrivacyHook.java:198-206`).
  - *Hardware Location Neutralization & Bluetooth Decoupling*:
    - Neutralize `LocationManager.getLastKnownLocation` by overwriting the result with `const/4 v$reg, 0x0` (`DevicePrivacyGuardPatch.kt:728-735`). Cancel single updates by injecting `LocationManager.removeUpdates` (`DevicePrivacyGuardPatch.kt:776-787`). Force `isProviderEnabled` and `isLocationEnabled` results to `0x0` (`DevicePrivacyGuardPatch.kt:831-836`).
    - Neutralize startup location Lego tasks (`InitLocationTask`) with `return-void` (`DevicePrivacyGuardPatch.kt:209-214`).
    - *Bluetooth Hardware Decoupling*: Strip manifest location permissions (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:24-44`), and hook BLE scanning preconditions (`isLocationEnable`, `isGpsEnable`, `hasScanCondition`) to return `true` (`const/4 v0, 1` / `return v0`) and `getLocationPermissions` to return an empty array (`new-array v0, v0, [Ljava/lang/String;`) (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:200-296`).
  - *Identifiers, Clipboard & Sensor Neutralization*:
    - Return `null` for `AdvertisingIdClient$Info` and zeroed UUID (`"00000000-0000-0000-0000-000000000000"`) for ad ID string (`DevicePrivacyGuardPatch.kt:340-360`).
    - Return `null` for proprietary privacy getters (`PrivacyDataMaster.get/forceGet`) and dummy strings (`"0000000000000000"`) for device ID managers (`AccountDeviceIdManager`) (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:70-178`).
    - Return empty string arrays (`new-array v0, v0, [Ljava/lang/String;`) for user environment info (Wi-Fi SSID, SIM serials) (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:187-193`).
    - Intercept clipboard readers returning `null` (`DevicePrivacyGuardPatch.kt:387-392`).
    - Motion sensors: force `PlatformSensorProvider.hasSensorType` -> `false` via `replaceWithReturnBoolean(false)` (`SensorPrivacyPatch.kt:28-31`) and `PlatformSensor.create` -> `null` via `replaceWithReturnNull()` (`SensorPrivacyPatch.kt:45-48`). (Note: `PlatformSensorProvider.create` must NOT return null as C++ binds its JNI receiver to it; `SensorPrivacyPatch.kt:38-39`). Stub Human Activity Recognition (`SmartHARServiceImpl.enable` -> false, `checkAndInit` -> return-void) (`DevicePrivacyGuardPatch.kt:406-425`).
    - Battery: drop `BATTERY_CHANGED` broadcast events by injecting `return-void` at index 0 of `onReceive` (`BatteryOptimizationPatch.kt:22-27`).
    - Content capture: force `OnscreenContentProvider.shouldCapture(String)` -> `false` to stop dispatching page text to system ContentCapture (`DisableContentCapturePatch.kt:23`).
- **Preservation Rules Guarded in Sources**:
  - *Bluetooth BLE Pairing Preserved Without Location*: When stripping location permissions from accessory companions, BLE discovery will fail unless SDK location prerequisites (`isLocationEnable`, `hasScanCondition`, `getLocationPermissions`) are mocked to return true/empty (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:53,198-296`).
  - *JNI / Native Crash Avoidance*: In Chromium sensor hooks, `PlatformSensorProvider.create()` must NOT return null because native C++ `PlatformSensorProviderAndroid` binds its JNI receiver to it; returning null triggers SIGSEGV / JNI abort (`SensorPrivacyPatch.kt:38-39`). Only `PlatformSensor.create` returns null and `hasSensorType` returns false.
  - *Non-Breaking Empty Collections & MatrixCursor*: Return empty `MatrixCursor` rather than `null` for contacts queries to prevent `NullPointerException` in callers expecting valid Cursor instances (`TikTokPrivacyHook.java:189`). Return empty list for broad package queries, but preserve targeted intent queries (`TikTokPrivacyHook.java:201-205`).
- **Anti-Patterns**:
  - Instruction replacement or register frame expansion (`ensureRegisterCount`) around `move-result-object`, which corrupts ART branch targets and shifts parameter registers, causing device-only `VerifyError` crashes (`DevicePrivacyGuardPatch.kt:436-444`).
  - Returning `null` where native C++ JNI bindings expect non-null Java peer objects, triggering immediate native crashes (`SIGSEGV`).
  - Returning `null` instead of an empty `Cursor` or `List`, crashing app adapters with `NullPointerException`.

---

## 4. When a Dedicated Variant Is Justified

A dedicated per-app privacy patch is justified when the universal patch is insufficient due to structural source limitations:

1. **High Scan Overhead on Large APKs**: `UniversalScreenshotProtectionBypassPatch` walks all classes and methods via `classDefForEach` (`UniversalScreenshotProtectionBypassPatch.kt:76-91`), causing heavy scan times on large codebases. A dedicated patch resolves targets instantly via indexed fingerprints.
2. **Assembler Addressing Limits (Registers >= 16)**: `UniversalScreenshotProtectionBypassPatch` skips flag sites when the target register is `>= 16` (`UniversalScreenshotProtectionBypassPatch.kt:165-167, 302-320`) because `and-int/lit16` only addresses registers `0` through `15`. A dedicated patch can allocate lower registers or use register-copy instructions.
3. **Proprietary Wrappers & JNI**: Apps that apply `FLAG_SECURE` through native JNI, reflection, or internal helper classes bypass framework-level call-site checks. A dedicated patch hooks the app's proprietary entrypoints directly.
4. **Custom Renderers & WebViews**: Secure surfaces managed by custom engines (e.g. Flutter platform views, React Native bridges) require app-specific hooks.
5. **Runtime Permission Checks**: Universal permission stripping removes manifest tags but does not modify bytecode. If an app expects a permission and crashes on missing grants without catch blocks, a dedicated variant must stub the corresponding runtime check.
6. **Graceful Offline Degradation**: Apps that crash when network initialization fails require dedicated hooks to mock offline state and bypass forced network initialization loops.
7. **Network Security & Certificate Pinning Hardening**: Justified when an APK bundles `res/xml/network_security_config.xml` without user CA trust anchors (`<certificates src="user" />`) or contains OkHttp `CertificatePinner` bytecode (`Lokhttp3/CertificatePinner;`), preventing network inspection, or when cleartext traffic must be explicitly constrained while keeping local network/printer communication intact (`NokoPrintNetworkSecurityHardeningPatch.kt:15-28`, `XiaomiEarbudsNetworkSecurityPatch.kt:18-58,75-105`).
8. **Share Link Tracking & In-App WebView Snooping**: Justified when an app appends tracking parameters to shared links or clipboard contents (`ShareOrigin`, `Aweme.getShareUrl`, `Clipboard.setText`), intercepts outbound navigation via internal WebViews (`SparkThirdContext`), or injects inline JavaScript / DOM hooks (`webview_inline_inject_js`, `WebViewAjaxHooker`) rather than routing external links to the default system browser (`CleanShareUrlPatch.kt:27-30`, `CleanShareUrlPatch.kt:56-60`, `InAppBrowserPrivacyGuardPatch.kt:23-27,59-86`).
9. **Runtime Device Data Harvesting & Sensor Profiling**: Justified when an app circumvents manifest permission removal via internal permission dispatchers (`FakeFragment`), queries device databases directly via `ContentResolver.query` (contacts), inspects installed apps via `PackageManager.queryIntentActivities`, polls hardware location (`LocationManager`), queries motion/battery sensors (`PlatformSensorProvider`, `BATTERY_CHANGED`), reads advertising IDs (`AdvertisingIdClient`), or blocks Bluetooth BLE scanning unless location is granted (`DevicePrivacyGuardPatch.kt:19-39,58-74,335-361`, `SensorPrivacyPatch.kt:21-52`, `BatteryOptimizationPatch.kt:17-31`, `XiaomiEarbudsDevicePrivacyGuardPatch.kt:198-296`).

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
4. **Network Security Hardening**:
   - Inspect network traffic through a local proxy with a user CA certificate installed. Confirm HTTPS connections succeed without certificate errors or OkHttp `SSLPeerUnverifiedException` (`XiaomiEarbudsNetworkSecurityPatch.kt:75-105`).
   - For apps with local hardware communication (e.g. NokoPrint), verify that local cleartext communication (printer discovery and print jobs) remains functional while user CA trust is active (`NokoPrintNetworkSecurityHardeningPatch.kt:9,23`).
5. **Share Links & In-App Browser**:
   - Copy a link or share content to the Android share sheet. Verify that the copied or shared URL has tracking parameters stripped (e.g. no `fbclid`, `gclid`, or tracking query tokens) and uses the configured custom share host if set (`CleanShareUrlPatch.kt:20-26`, `ChromiumExtension.java:34-68`).
   - Click an external or third-party web link in the app. Verify that the link opens in the default system browser rather than an in-app WebView, and that residual WebViews do not execute injected tracking scripts (`InAppBrowserPrivacyGuardPatch.kt:59-86`).
6. **Runtime Device-Data Neutralization**:
   - Trigger contact sync, location prompts, or companion device pairing flows. Confirm the app does not prompt for blocked permissions or loop into settings redirect screens (`DevicePrivacyGuardPatch.kt:58-114`).
   - In accessory apps (e.g. Xiaomi Earbuds), verify Bluetooth BLE scanning and earbuds pairing succeed without granting location permissions (`XiaomiEarbudsDevicePrivacyGuardPatch.kt:53,198-296`).
   - Verify motion sensor APIs (`PlatformSensorProvider`), battery broadcasts (`BATTERY_CHANGED`), and content capture do not dispatch data, and that runtime queries (contacts `ContentResolver.query`, package inventory `queryIntentActivities`, `AdvertisingIdClient`) return empty/neutralized values without `VerifyError` or `NullPointerException` crashes (`DevicePrivacyGuardPatch.kt:436-504,638-688`, `SensorPrivacyPatch.kt:21-52`, `BatteryOptimizationPatch.kt:17-31`, `DisableContentCapturePatch.kt:18-26`).
