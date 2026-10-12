---
name: ux-declutter
description: Methodology and patterns for removing first-party ads, promos and rating prompts, onboarding and first-run flows, nag dialogs and popups, and UI clutter in Morphe patches. Use when building per-app declutter patches.
---

<!-- Shared skill: canonical source is kveld-morphe-patches; scripts/sync_shared_skills.sh mirrors it byte-identically into kveld-extra-morphe-patches (.claude/skills is a symlink to .agents/skills in each repo). Edit only in kveld-morphe-patches; the sibling pre-commit hook rejects direct edits. -->

# UX Declutter: Ads, Promos, Onboarding, Nags & UI Clutter

## 1. Scope & Boundaries

UX declutter patches neutralize non-essential client-side visual, promotional, and navigational friction to create a lean, distraction-free user experience.

### A. In-Scope Families & Ownership Boundaries
- **In-Scope (UX Declutter)**:
  1. *First-Party Ads*: Splash/cold-start ads, in-feed sponsored items, internal ad dispatch components.
  2. *Promos & Rating Prompts*: In-app review dialogs, store rating popups, promotional marketing campaigns, tip notifications.
  3. *Onboarding & First-Run Skipping*: Welcome carousels, tutorials, consent/privacy agreements, interest/region pickers, search engine choice screens.
  4. *Nag Dialogs & Popups*: Friend/contact sync prompts, multi-account guides, 2SV upsells, PopLayer sheets, floating live bubbles, streak warnings.
  5. *UI Element Hiding*: Non-essential navigation tabs, bottom buttons, header bars, trending pills, unread badges, promotional cards.
- **Out of Scope (Owned Elsewhere)**:
  - *Ad & Analytics SDKs*: Third-party ad networks, telemetry trackers, crash reporters, and analytics dispatchers are owned by `telemetry-blocking`.
  - *Store-Redirect & Forced-Update Gates*: Involuntary store redirects (`market://`), package updater gates, and orphan store components are owned by `compat-bypass` (Family 2).
  - *Paywalls & Login Gates*: Client-side subscription unlocks and offline guest-mode login bypasses are owned by `compat-bypass` (Families 3-4).
  - *Asset & Binary Slimming*: Unused companion `.so` libraries, non-target locales, and density resource pruning are owned by `app-debloat`.

### B. Preservation Rules & Default Policy Invariants
- **Preserve User-Initiated Access & Settings**: When bypassing first-run screens, gate the bypass on the entry path. `NokoPrintSkipWelcomeDialogPatch.kt:56` injects `if-eqz p1, :show_dialog`: it auto-accepts only when the builder flag `p1` is true and falls through to the original dialog when `p1` is false, so the About menu still opens it. Never remove settings items or about screens.
- **Preserve Deep Links & Core Intents**: Never strip standard browser intent filters (`android.intent.action.VIEW`), OAuth redirects, or deep links (`SkipFirstLaunchOnboardingPatch.kt:44`).
- **Preserve Essential Communication & Billing**: Never disable push notification channels for incoming messages/calls (`BraveNotificationSchedulerOptimizationPatch.kt`), and never disable Google Play Billing (`ProxyBillingActivity` / `ProxyBillingActivityV2`, `compat-bypass:127-130`).
- **Default Policy Invariant**:
  - Pure clutter and intrusive prompt suppressors default to `true` (e.g. `BraveSuppressInAppPromosPatch.kt:13`, `SkipFirstRunPatch.kt:12`, `TikTokFeedAdBlockerPatch.kt:14`, `SkipFirstLaunchOnboardingPatch.kt:14`, `InstantColdStartPatch.kt:15`, `BraveNotificationSchedulerOptimizationPatch.kt:12`, `XiaomiEarbudsDisablePromosAndNagsPatch.kt:12`).
  - Major navigational controls and primary actions default to `false` (opt-in) so standard functionality is never disrupted unexpectedly:
    - Central '+' create/publish button: `hidePublishTab` defaults to `false` (`FeedNavigationDeclutterPatch.kt:60`).
    - Top-left LIVE entry button: `hideTopLiveEntrance` defaults to `false` (`FeedNavigationDeclutterPatch.kt:44`).
    - New tab shortcut tiles: `hideTopSites` defaults to `false` (`BraveCleanNewTabPagePatch.kt:113`).
    - Aggressive ad manifest purges: `nokoPrintAdManifestResourcePatch` defaults to `false` (`NokoPrintAdDispatchGovernorPatch.kt:15`).

---

## 2. The Five Families

### A. First-Party Ads (Splash, In-Feed & Ad Dispatch Components)
- **Recon Signals**:
  - Splash ad tasks and managers: `NormalSplashAdActivity`, `SplashAdManagerPreloadTask`, `TopViewPreloadTask`, `SplashSettingServiceImpl`, `SplashAdServiceImpl`.
  - Ad-free state checks: `m4.g(Z)Z` (`is_no_ads`), `Aweme.isAd()`, `Aweme.isSoftAd()`, `Aweme.getAwemeRawAd()`.
  - Mediation and ad provider tags in `AndroidManifest.xml`: `com.applovin.`, `com.mbridge.msdk.`, `com.facebook.ads.`, `com.unity3d.`.
- **Production Techniques**:
  1. *Splash Preload & Activity Neutralization*:
     In `InstantColdStartPatch.kt:23-65, 151-165`, stub preload tasks (`SplashAdManagerPreloadTask.run()`, `TopViewPreloadTask.run()`, `RealTimeSplashTask.run()`) to `return-void`. Force `SplashSettingServiceImpl.LIZ()` to `true` (`enable_force_skip_topview`), return `null` for TopView Aweme models in `SplashAdServiceImpl.LJIILJJIL()` and `TopViewJsonManager.LIZIZ()`, and inject an immediate finish into `NormalSplashAdActivity.onCreate()`:
     ```kotlin
     normalSplashOnCreate.addInstructions(0, """
         invoke-super {p0, p1}, Lcom/bytedance/ies/foundation/activity/BaseActivity;->onCreate(Landroid/os/Bundle;)V
         invoke-virtual {p0}, Lcom/bytedance/ies/ugc/aweme/commercialize/splash/show/NormalSplashAdActivity;->finish()V
         return-void
     """.trimIndent())
     ```
  2. *Global Ad-Free State Assertion & Ad Loader Short-Circuiting*:
     In `NokoPrintAdDispatchGovernorPatch.kt:124-133, 169-248`, force global ad-free check `m4.g(Z)Z` to return `true` (`0x1`). For interstitial (`h4.b`, `h4.c`) and rewarded (`l4.b`) ad dispatchers, invoke completion callbacks directly and return:
     ```kotlin
     // NokoPrintAdDispatchGovernorPatch.kt:180-191
     addInstructionsWithLabels(0, """
         if-eqz p1, :cond_skip_h
         invoke-virtual {p1}, Lcom/nokoprint/m4;->h()V
         :cond_skip_h
         if-eqz p0, :cond_skip_cb
         const/4 v0, 0x0
         invoke-virtual {p0, v0}, Lcom/google/android/material/carousel/d;->a(Lcom/nokoprint/h4;)V
         :cond_skip_cb
         return-void
     """.trimIndent())
     ```
  3. *In-Feed Model Filtering via Runtime Extension*:
     In `TikTokFeedAdBlockerPatch.kt:34-41`, intercept return points (`RETURN_OBJECT`) of feed response services (`FeedApiService.fetchFeedList`, `FeedItemList.getItems`) and invoke extension sanitizers (`TikTokFeedAdFilter.filterAdsInList()`), which use reflection to evaluate `isAd()`, `isSoftAd()`, and `SHOP_PROMO_MARKER` (`TikTokFeedAdFilter.java:547-659`).
  4. *Manifest Ad Component Disabling*:
     In `NokoPrintAdDispatchGovernorPatch.kt:66-100`, parse `AndroidManifest.xml` via `resourcePatch` and set `android:enabled="false"` on ad activities, services, receivers, and initialization providers.
- **Anti-Patterns Guarded Against**:
  - Never swallow ad loader callbacks without execution; doing so leaves UI progress dialogs hanging indefinitely.
  - Never disable Google Play Billing proxy activities (`ProxyBillingActivity`).

### B. Promos, Rating and Review Prompts, Marketing Notifications
- **Recon Signals**:
  - Review and rating dialog classes: `BraveRateDialogFragment`, `BraveAskPlayStoreRatingDialog`, `InviteReviewManager`.
  - String tags: `"brave_rate_dont_show_again"`, `"qa_force_rate_dialog"`, `"praise_dialog"`, `"showTipsPromo"`.
  - Retention marketing notification publishers: `NotificationSchedulerTask`, `TipsAgent`, `RetentionNotificationPublisher`.
  - Header notice injectors: `TopBannerWidgetContainerInjector`, `AgeGraduationWidgetInjector`.
- **Production Techniques**:
  1. *Rate Eligibility Gate Neutralization*:
     In `BraveSuppressInAppPromosPatch.kt:20-28` and `XiaomiEarbudsDisablePromosAndNagsPatch.kt:42-56`, force eligibility methods (`RateEligibilityGate.d`, `InviteReviewManager.isShowDialog`) to return `false` (`0x0`).
  2. *Dialog Show Method Stubbing & Tag Dropping*:
     In `BraveSuppressInAppPromosPatch.kt:30-58`, stub dialog `.show(FragmentManager, String)` methods with `return-void`. In base dialog wrappers (lines 83-108), inspect string tags and return before showing:
     ```kotlin
     // BraveSuppressInAppPromosPatch.kt:92-106
     const-string v0, "OpenYtInBraveDialogFragment"
     invoke-virtual {v0, p2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
     move-result v0
     if-eqz v0, :not_yt
     return-void
     :not_yt
     const-string v0, "BraveAdFreeCalloutDialogFragment"
     invoke-virtual {v0, p2}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
     move-result v0
     if-eqz v0, :not_adfree
     return-void
     :not_adfree
     ```
  3. *Notification Schedulers & Receivers Neutralization*:
     In `BraveNotificationSchedulerOptimizationPatch.kt:20-45, 91-109`, stub `NotificationSchedulerTask.schedule` to `return-void`, cancel running alarms inside `onStartTask`, and stub broadcast receivers (`onReceive`) with `return-void`.
  4. *Banner Container Injector Disabling*:
     In `HideInboxPromosAndAlertsPatch.kt:52-59`, stub widget injector `enable()` methods to return `false`.
- **Anti-Patterns Guarded Against**:
  - Never disable user-initiated feedback or help menus; suppress only unsolicited background rating prompts.
  - Never disable standard push receivers for user content or direct messages.

### C. Onboarding and First-Run Skipping (Welcome Dialogs, Tutorials, Consent or Interest Pickers, Search Choice)
- **Recon Signals**:
  - First-run engine flags: `"first_run_flow"`, `"disable-fre"`, `"Chrome.FirstRun.SkippedByPolicy"`.
  - Consent shared preferences keys: `"privacy_accepted"`, `getPRIVACY_AGREE()`, `getWelcomeFinish()`.
  - New user onboarding services: `NewUserJourneyService`, `"did_finish_nuj"`, `"new_user_journey"`.
- **Production Techniques**:
  1. *Dual First-Run Engine Status & Sequencer Bypass*:
     In `SkipFirstRunPatch.kt:17-43`, force `FirstRunStatus.getFirstRunFlowComplete()` to return `true` (`0x1`) so app subsystems know onboarding is finished, and force `FirstRunFlowSequencer.checkIfFirstRunIsNecessary()` to return `false` (`0x0`) so `FirstRunActivity` is never started.
  2. *SharedPreferences Auto-Accept Hook*:
     In `NokoPrintSkipWelcomeDialogPatch.kt:53-69`, hook the first-run dialog builder. Auto-write `privacy_accepted = true` to `SharedPreferences`, call post-consent initialization, and return:
     ```kotlin
     // NokoPrintSkipWelcomeDialogPatch.kt:56-67
     if-eqz p1, :show_dialog
     iget-object v0, p0, $fieldRefStr
     invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences${'$'}Editor;
     move-result-object v0
     const-string v1, "$PRIVACY_ACCEPTED_KEY"
     const/4 v2, 0x1
     invoke-interface {v0, v1, v2}, Landroid/content/SharedPreferences${'$'}Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences${'$'}Editor;
     move-result-object v0
     invoke-interface {v0}, Landroid/content/SharedPreferences${'$'}Editor;->apply()V
     invoke-virtual {p0}, $methodRefStr
     return-void
     ```
  3. *Consent Preference Spoofing with Non-Zero Timestamp*:
     In `XiaomiEarbudsDisablePromosAndNagsPatch.kt:59-140`, force `getPRIVACY_AGREE() -> true`, `getPrivacyDialogFinished() -> true`, `getWelcomeFinish() -> true`, provide a valid non-zero epoch timestamp (`const-wide v0, 0x18bdc6d2000L`) for `getPrivacyAgreeTime()`, and default region to `"us"`.
  4. *Onboarding Funnel Bypass*:
     In `SkipFirstLaunchOnboardingPatch.kt:21-73`, force `NewUserJourneyService.LIZJ()` to `true` (reports `did_finish_nuj = true`), and stub container launchers (`LJJJI`, `LJIJI`, `LJIJJLI`) to return `false` or `return-void`.
- **Anti-Patterns Guarded Against**:
  - Never return `0L` or `null` for consent timestamps or regions if subsequent logic parses them; return safe non-zero defaults to prevent `NullPointerException` crashes.

### D. Nag Dialogs and Popups
- **Recon Signals**:
  - Relationship and contact nag controllers: `RecUserPopupInMainActivityController`, `RelationAuthDialogControl`, `PushPermissionPopupManager`.
  - Semantic PopLayer prompts: `PopSuiteManagerService`, `LX/07Q5.canShow()`.
  - Floating teaser overlays: `LiveBubbleUtil`.
  - Direct message inline nags: `"has_streak_reminder_inline_msg"`.
- **Production Techniques**:
  1. *Targeted Method Stubbing*:
     In `PopupsAndPromptsSuppressorPatch.kt:94-201`, stub dialog triggers (`RecUserPopupInMainActivityController.LIZLLL`, `RelationAuthDialogControl.LJFF`, `PushPermissionPopupManager.LJI`) with `replaceWithReturnVoid()` or `replaceWithReturnBoolean(false)`.
  2. *Semantic PopLayer Filter Hook*:
     In `PopupsAndPromptsSuppressorPatch.kt:272-282`, hook `canShow()` and delegate to an extension hook (`TikTokPopupHook.shouldSuppressPopLayer()`), which uses reflection to inspect `getElementLabel()`, `getTriggerId()`, and class names against a blacklisted set (`TikTokPopupHook.java:14-108`).
  3. *Floating Live Bubble Suppression*:
     In `PopupsAndPromptsSuppressorPatch.kt:310-327`, stub `LiveBubbleUtil.LIZ` to `return-void` and force `LiveBubbleUtil.LJIIIIZZ` to `false`.
  4. *Direct System Permission Request (Nag Bypass)*:
     In `XiaomiEarbudsDisablePromosAndNagsPatch.kt:247-260`, replace custom pre-permission dialog prompts with an immediate system `ActivityResultLauncher.launch()` call:
     ```kotlin
     invoke-static {}, Lcom/mi/earphone/bluetoothsdk/util/CheckPermissionUtilKt;->isBluetoothPermissionGrantedForS()Z
     move-result v0
     if-nez v0, :cond_skip
     invoke-static {p0}, Lcom/mi/earphone/settings/ui/DeviceSettingsFragment;->access${'$'}getMPermissionRequestLauncher${'$'}p(...)Landroidx/activity/result/ActivityResultLauncher;
     move-result-object v0
     if-eqz v0, :cond_skip
     invoke-static {}, Lcom/mi/earphone/bluetoothsdk/util/CheckPermissionUtilKt;->getBluetoothPermissionsForAndroidS()[Ljava/lang/String;
     move-result-object v1
     invoke-virtual {v0, v1}, Landroidx/activity/result/ActivityResultLauncher;->launch(Ljava/lang/Object;)V
     :cond_skip
     return-void
     ```
  5. *Parameter-Guarded Inline Reminder Filtering*:
     In `PopupsAndPromptsSuppressorPatch.kt:339-349`, match key `"has_streak_reminder_inline_msg"` in `p1` and return `Boolean.FALSE`, falling through to original logic for other messages.
- **Anti-Patterns Guarded Against**:
  - Never suppress Android OS runtime permission dialogs; bypass only the app's internal pre-permission nag screens.

### E. UI Element Hiding (Tabs, Buttons, Banners, Overlays)
- **Recon Signals**:
  - Start page preferences: `"show_background_images"`, `"show_sponsored_images"`, `"brave_news_switch"`, `"show_brave_stats"`.
  - Tab protocols: `NearbyTabProtocol`, `ExploreXTabProtocol`, `ExploreBottomTabProtocol`, `PublishTabProtocol`, `LiveTabProtocol`.
  - Assem cell triggers: `FeedSearchBottomBarAssemTrigger`, `TrendingBottomBarAssem`.
  - Bottom navigation tab manager methods: `tabManagerClasses` (`"LJIIL"`, `"LJJL"`).
- **Production Techniques**:
  1. *Resource Default Flipping & PrefService Interception*:
     In `BraveCleanNewTabPagePatch.kt:20-67`, use `resourcePatch` to set `android:defaultValue="false"` on XML preferences. In `bytecodePatch` (lines 124-154), hook `PrefService` return points to filter values via `BraveExtension.filterNtpPref()` (`BraveExtension.java:25-41`).
  2. *Protocol Disabling & Provider Nulling*:
     In `FeedNavigationDeclutterPatch.kt:98-260`, stub tab protocol `.enable()Z` to `false` and stub tab provider factories (`LJ()`, `LIZ()`) to return `null`.
  3. *View Hierarchy Visibility Override (`View.GONE`)*:
     In `FeedNavigationDeclutterPatch.kt:400-421`, capture the view register in `PublishBottomTabViewFactory.LIZ()` after `move-result-object` and inject `setVisibility(0x8)` (`View.GONE`):
     ```kotlin
     // FeedNavigationDeclutterPatch.kt:412-417
     const/16 v$constReg, 0x8
     invoke-virtual {v$viewReg, v$constReg}, Landroid/view/View;->setVisibility(I)V
     ```
  4. *Tab Badge Parameter Guarding*:
     In `FeedNavigationDeclutterPatch.kt:582-592`, inspect tab manager methods, match tab key `"NOTIFICATION"` in register `p$pString`, and short-circuit return to suppress unread badges while keeping badge logic operational for other tabs.
  5. *Aweme Feed Bar Property Stubbing*:
     In `FeedNavigationDeclutterPatch.kt:346-386`, force `isDisableSearchTrendingBar` to `true`, and return `null` for `getTrendingBar` and `getHotSearchInfo`.
- **Anti-Patterns Guarded Against**:
  - Never return `null` from view factories unless caller methods are verified to handle nulls safely without crashing. If in doubt, use `View.setVisibility(View.GONE)`.
  - Avoid removing primary action controls by default (e.g. create '+' button).

---

## 3. Engineering Contracts

Every UX declutter patch must adhere to the following contracts:

### A. Zero-Zombie Fingerprint Contract
- Every required fingerprint must resolve cleanly against the target APK. Catch-and-log is acceptable only for best-effort hooks over a list of optional methods, as in `BraveCleanNewTabPagePatch.kt:151-153`; a required anchor that fails must fail the patch.
- On ambiguous methods, scope the fingerprint explicitly and assert uniqueness (e.g. `SkipFirstLaunchOnboardingPatch.kt:62-69` using `require(candidates.size == 1)`).

### B. Option Naming, Typing, and One-Axis-Per-Toggle Standards
- **Naming & Type**: Use camelCase keys with descriptive titles and descriptions via `by booleanOption(...)` (`required = false`).
- **One Axis per Toggle**: Separate independent visual surfaces into distinct options:
  - `PopupsAndPromptsSuppressorPatch.kt:23-61`: `suppressAccountPrompts`, `suppressStickerRecommendations`, `filterPopLayerPrompts`, `suppressLiveTeaserBubble`, `suppressStreakReminders`.
  - `FeedNavigationDeclutterPatch.kt:26-80`: `hideNearbyTab`, `hideCommunityTab`, `hideTopLiveEntrance`, `hideFeedSearchBar`, `hidePublishTab`, `hideFriendsAvatarPreview`, `hideInboxBadge`.
  - `HideInboxPromosAndAlertsPatch.kt:18-37`: `hideTopPromosAndBanners`, `hideContactRecommendations`, `hideNavigationNoticesAndTooltips`.
- **Skip Guard**: When all options are disabled, log and exit early (`FeedNavigationDeclutterPatch.kt:83-93`).

### C. Surgical Diagnostic Telemetry Standard
- **Prefix**: Prefix all log lines with the bracketed patch name: `println("[<Patch Name>] ...")`.
- **Aggregation**: Track applied mutations locally (`var patched = 0`) and emit a single summary line:
  `println("[<Patch Name>] Applied $patched hooks -> ...")` (`FeedNavigationDeclutterPatch.kt:610`, `InstantColdStartPatch.kt:168`).
- **Guard Transparency**: Log explicit reasons when skipping execution (`println("[<Patch Name>] Skipped: ...")`).
- **Plain ASCII Only**: Never use emojis or non-ASCII pictographs.

### D. Runtime Extension Payloads & Reflection Bridges
- For multi-parameter filtering or reflection-heavy tasks, declare `dependsOn(sharedExtensionPatch)` and invoke extension classes (`Constants.BRAVE_EXTENSION_CLASS`, `Constants.TIKTOK_EXTENSION_FILTER_CLASS`, `Constants.TIKTOK_EXTENSION_POPUP_HOOK`).
- Extension methods must wrap reflective calls in `try-catch (Throwable ignored)` to guarantee crash safety across obfuscation boundaries.

---

## 4. Verification & Testing Protocol

### A. Morphe Patcher In-Situ Verification Gates
Execute the patcher pipeline against the target application APK:
```bash
# Pass 1: Default configuration
./gradlew runPatchTest -Papp=<app_id> -Papk=<apk> -Pout=build/test-<app_id>.apk

# Pass 2: All options forced on
./gradlew runPatchTest -Papp=<app_id> -Papk=<apk> -PallOptions=true -Pout=build/test-<app_id>.apk
```
The patching run MUST complete with:
- Exit code: `0`
- Failed patches: `0`
- Detected Fingerprint Failures: `0`
- Detected Smali Compile Errors: `0`

### B. Output APK Manifest Dump Verification
For patches disabling manifest components (`NokoPrintAdDispatchGovernorPatch.kt`), verify disabling in `build/test-<app_id>.apk`:
```bash
aapt2 dump xmltree --file AndroidManifest.xml build/test-<app_id>.apk | grep -B 2 -A 5 "android:enabled"
```
Assert that target ad activities, providers, and receivers have `android:enabled=0x0`.

### C. Physical Device Smoke & Clean-Install Verification
1. **Fresh Install Verification (Onboarding & Nags)**:
   Clear app data (`adb shell pm clear <package>`) and launch:
   - Verify the app launches directly into the main activity / feed without welcome modals, consent wizards, or interest pickers.
   - Verify that the app reaches its operational state without crashing.
   - Verify that in-app settings and the About menu remain accessible.
2. **Surfaces & Declutter Verification (Ads & UI Elements)**:
   - *Cold Start*: Relaunch from launcher -> zero splash ad displays and zero resume delay.
   - *Feed & Content*: Scroll feeds -> zero sponsored cards, zero search trending bars.
   - *Navigation*: Inspect tabs and headers -> configured elements (Nearby tab, Explore tab, badges) are hidden without blank gaps or layout collapse.
