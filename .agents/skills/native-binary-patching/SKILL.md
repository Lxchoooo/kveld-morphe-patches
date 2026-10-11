---
name: native-binary-patching
description: Byte-level patching of native and binary assets (libchrome.so host redirection per ABI, multi-candidate offsets, companion .so trimming, Hermes HBC prologue patching with SHA-1 footer). Use when writing or updating a rawResourcePatch that edits .so files or bundle assets.
---

<!-- Shared skill: canonical source is kveld-morphe-patches; scripts/sync_shared_skills.sh mirrors it byte-identically into kveld-extra-morphe-patches (.claude/skills is a symlink to .agents/skills in each repo). Edit only in kveld-morphe-patches; the sibling pre-commit hook rejects direct edits. -->

# Native & Binary Asset Patching Guidelines

## 1. In-Situ Binary String Redirection (`libchrome.so`)

Any binary modification executed inside `rawResourcePatch` targeting ELF libraries (such as `lib/arm64-v8a/libchrome.so`) must adhere to strict bounds and fingerprint verification protocols.

### Production Pattern (`BraveBlockTelemetryPatch.kt`, kveld-morphe-patches)
Redirection overwrites domain strings in-place with `0.0.0.0` followed by null bytes (`0x00`). The replacement length must exactly match the original string length to preserve ELF string table boundaries and segment offsets. Each supported ABI carries its own offset because the string tables differ per build:

```kotlin
data class HostEntry(
    val arm64Offset: Long,
    val arm32Offset: Long,
    val hostName: String,
)

// EXAMPLE offsets: version-specific illustration values. Always resolve both ARM64 and ARM32
// offsets for the target APK version via pre-patch fingerprint assertion; never copy these literally.
val hostEntries = listOf(
    HostEntry(0x0020d657L, 0x005a14b4L, "star-randsrv.bsg.brave.com"),
    HostEntry(0x0020d688L, 0x005a14e5L, "collector.bsg.brave.com"),
    HostEntry(0x0020d6bfL, 0x005a151cL, "usage-ping.brave.com"),
)

val targets = listOf(
    "lib/arm64-v8a/libchrome.so" to { entry: HostEntry -> entry.arm64Offset },
    "lib/armeabi-v7a/libchrome.so" to { entry: HostEntry -> entry.arm32Offset },
)

val existingTargets = targets
    .map { (path, offsetSelector) -> Triple(path, get(path), offsetSelector) }
    .filter { (_, file, _) -> file.exists() && file.isFile }

if (existingTargets.isEmpty()) {
    println("[Block Telemetry] Skipped: no arm64-v8a or armeabi-v7a libchrome.so found.")
    return@execute
}

val redirectionIp = "0.0.0.0".toByteArray(Charsets.US_ASCII)

for ((relPath, soFile, offsetSelector) in existingTargets) {
    var writtenHosts = 0

    RandomAccessFile(soFile, "rw").use { raf ->
        for (entry in hostEntries) {
            val offset = offsetSelector(entry)
            val expectedBytes = entry.hostName.toByteArray(Charsets.US_ASCII)
            val len = expectedBytes.size
            if (offset + len > raf.length()) {
                throw PatchException("Host offset 0x${offset.toString(16)} out of bounds in $relPath")
            }
            val buf = ByteArray(len)
            raf.seek(offset)
            raf.readFully(buf)
            if (!buf.contentEquals(expectedBytes)) {
                throw PatchException(
                    "Host fingerprint mismatch at 0x${offset.toString(16)} in $relPath. " +
                        "Expected: ${entry.hostName}, Found: ${String(buf, Charsets.US_ASCII)}",
                )
            }

            // Construct replacement: "0.0.0.0" + null byte + zero padding to original length
            val replacement = ByteArray(len)
            System.arraycopy(redirectionIp, 0, replacement, 0, redirectionIp.size)
            // Remaining bytes default to 0x00 (null padded)

            raf.seek(offset)
            raf.write(replacement)
            writtenHosts++
        }
    }

    println("[Block Telemetry] $relPath: Redirected $writtenHosts / ${hostEntries.size} endpoints to 0.0.0.0 in libchrome.so")
}
```

---

## 2. Multi-Candidate Offset Resolution

When string table offsets shift slightly between release builds or regional variants, resolve the target offset dynamically from a candidate list rather than hardcoding a single fragile pointer.

### Production Pattern (`libchrome.so` Multi-Candidate Resolution)
```kotlin
val syncOffsets = listOf(0x0031b2b2L, 0x0031b2b5L, 0x0031b34fL)
val targetUrl = "https://endpoint.example.com/v1/telemetry"
val expectedBytes = targetUrl.toByteArray(Charsets.US_ASCII)
val len = expectedBytes.size
val redirectionIp = "0.0.0.0".toByteArray(Charsets.US_ASCII)

RandomAccessFile(soFile, "rw").use { raf ->
    val validOffset = syncOffsets.firstOrNull { offset ->
        if (offset + len > raf.length()) return@firstOrNull false
        val buf = ByteArray(len)
        raf.seek(offset)
        raf.readFully(buf)
        buf.contentEquals(expectedBytes)
    } ?: throw PatchException(
        "Sync fingerprint mismatch for $targetUrl in libchrome.so",
    )

    val replacement = ByteArray(len)
    System.arraycopy(redirectionIp, 0, replacement, 0, redirectionIp.size)

    raf.seek(validOffset)
    raf.write(replacement)
}
```

---

## 3. Companion Native Library Bloat Trimming

When applications package unused third-party native binaries (e.g. AI models, XR runtime, or bundled VPN binaries), zeroing them out via `writeBytes(byteArrayOf())` preserves file entries in the ZIP header while drastically reducing APK footprint.

### Production Pattern (`BraveNativeBloatSlimmerPatch.kt`, kveld-morphe-patches)
```kotlin
private val EMPTY_STUB_BYTES = byteArrayOf()

private val BLOAT_NATIVE_LIBS = listOf(
    "libimpress_api_jni.so",
    "libwg-go.so",
    "libandroidx.xr.arcore.openxr.so",
    "libarcore_sdk_c.so",
)

val libDir = get("lib/arm64-v8a")
if (libDir.exists() && libDir.isDirectory) {
    BLOAT_NATIVE_LIBS.forEach { libName ->
        val libFile = get("lib/arm64-v8a/$libName")
        if (libFile.exists() && libFile.isFile) {
            val originalSize = libFile.length()
            if (originalSize > 0) {
                libFile.writeBytes(EMPTY_STUB_BYTES)
                savedBytes += (originalSize - libFile.length())
                strippedLibs.add(libName)
            }
        }
    }
}
```

---

## 4. React Native Hermes Bytecode Asset Patching

For React Native Android applications utilizing the Hermes JavaScript engine, the precompiled bundle is stored as a binary asset (`assets/index.android.bundle`). `rawResourcePatch` can parse and mutate Hermes Bytecode (HBC) directly.

### Production Pattern (`HevyUnlockProPatch.kt`, kveld-morphe-patches)
1. **Magic & Version Verification**: Assert Hermes magic number (`0x1f1903c103bc1fc6L`) and target HBC version (e.g. HBC96 = `96`).
2. **Table Parsing**: Compute 4-byte aligned offsets for function headers, string table, overflow string table, and string storage.
3. **Target Function / Getter Identification**: Locate function index by matching string identifier table entries (e.g. `"isPro"`, `"isPaying"`).
4. **Bytecode Opcode Injection**: Overwrite the target function prologue with forced return instructions:
   - Hermes bytecode opcodes: `LoadConstTrue r0` (`0x78 0x00`) followed by `Ret r0` (`0x5C 0x00`). Getters which must report false use `LoadConstFalse r0` (`0x79 0x00`) followed by `Ret r0`.
   ```kotlin
   private val FORCE_TRUE_PROLOGUE = byteArrayOf(0x78.toByte(), 0x00, 0x5C.toByte(), 0x00)
   private val FORCE_FALSE_PROLOGUE = byteArrayOf(0x79.toByte(), 0x00, 0x5C.toByte(), 0x00)
   ```
5. **Footer Hash Recalculation**: HBC96 bundles end with a 20-byte SHA-1 footer computed over all preceding bytes. After mutating any function, recompute it and write it into the last 20 bytes; skipping this leaves a stale hash in the bundle.
   ```kotlin
   val hash = MessageDigest.getInstance("SHA-1").digest(bundleBytes.copyOfRange(0, bundleBytes.size - 20))
   System.arraycopy(hash, 0, bundleBytes, bundleBytes.size - 20, 20)
   ```
6. **Write Back**: Write modified byte array back to `bundleFile.writeBytes(bundleBytes)`. Write only when at least one function was patched.
