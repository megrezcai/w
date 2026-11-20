#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
sdk=${ANDROID_SDK_ROOT:-${ANDROID_HOME:-}}
: "${sdk:?请设置 ANDROID_SDK_ROOT}"
tools="$sdk/build-tools/35.0.0"
platform="$sdk/platforms/android-35/android.jar"
build="$PWD/build"
mkdir -p "$build/classes" "$build/dex"
"$tools/aapt2" compile --dir res -o "$build/resources.zip"
"$tools/aapt2" link -I "$platform" --manifest AndroidManifest.xml -o "$build/unsigned.apk" "$build/resources.zip"
mapfile -t sources < <(find src -name '*.java')
javac -encoding UTF-8 -source 8 -target 8 -classpath "$platform" -d "$build/classes" "${sources[@]}"
jar cf "$build/classes.jar" -C "$build/classes" .
"$tools/d8" --lib "$platform" --min-api 26 --output "$build/dex" "$build/classes.jar"
(cd "$build/dex" && zip -q "$build/unsigned.apk" classes.dex)
"$tools/zipalign" -f 4 "$build/unsigned.apk" "$build/aligned.apk"
if [[ -n "${QUICKMIX_KEYSTORE:-}" ]]; then
  : "${QUICKMIX_KEY_ALIAS:?请设置 QUICKMIX_KEY_ALIAS}"
  : "${QUICKMIX_KEY_PASSWORD:?请设置 QUICKMIX_KEY_PASSWORD}"
  "$tools/apksigner" sign --ks "$QUICKMIX_KEYSTORE" --ks-key-alias "$QUICKMIX_KEY_ALIAS" \
    --ks-pass env:QUICKMIX_KEY_PASSWORD --out "$build/QuickMix.apk" "$build/aligned.apk"
else
  if [[ ! -f "$build/local-signing.p12" ]]; then
    keytool -genkeypair -keystore "$build/local-signing.p12" -storepass android -keypass android \
      -alias local -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=QuickMix Local"
  fi
  "$tools/apksigner" sign --ks "$build/local-signing.p12" --ks-key-alias local \
    --ks-pass pass:android --out "$build/QuickMix.apk" "$build/aligned.apk"
fi
"$tools/apksigner" verify "$build/QuickMix.apk"
