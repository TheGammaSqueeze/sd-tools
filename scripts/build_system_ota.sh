#!/usr/bin/env bash
# build_system_ota.sh - Assemble and testkey-sign a recovery-flashable zip that
# writes a GSI system image to the CURRENT slot's system logical partition,
# resizing it to fit, with no slot switch and no other partitions touched.
#
# IMPORTANT: this device's GSI build sets target_recovery=false and ships no
# Edify `updater` binary, and the device's stock recovery natively does A/B
# payload OTAs (which switch slots). So this zip needs an Edify `updater` (arm64)
# that you supply via --updater: build it from a recovery-enabled config
# (`m updater`) or take a compatible Lineage 21 arm64 one. If you do not have an
# updater, use scripts/flash_gsi_system.sh (fastbootd), which is the tested path.
#
# The zip layout produced:
#   META-INF/com/google/android/update-binary   (your updater)
#   META-INF/com/google/android/updater-script   (Edify, generated below)
#   dynamic_partitions_op_list                    (resize system to the image size)
#   system.img                                    (your GSI system image)
# then signed with the AOSP testkey via signapk (whole-file OTA signature, -w).
#
# Usage:
#   build_system_ota.sh --img <system.img> --updater <updater> --out <ota.zip> \
#       [--signapk <signapk.jar|bin>] [--key-dir keys]
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
IMG=""; UPD=""; OUT=""; SIGNAPK="${SIGNAPK:-}"; KEYDIR="$HERE/keys"
while [ $# -gt 0 ]; do case "$1" in
  --img) IMG="$2"; shift 2;; --updater) UPD="$2"; shift 2;;
  --out) OUT="$2"; shift 2;; --signapk) SIGNAPK="$2"; shift 2;;
  --key-dir) KEYDIR="$2"; shift 2;; *) echo "unknown arg $1"; exit 2;; esac; done
[ -f "${IMG:?--img required}" ]; [ -f "${OUT:+x}" ] 2>/dev/null || true
[ -n "${OUT:?--out required}" ]
[ -f "$KEYDIR/testkey.pk8" ] || { echo "testkey missing under $KEYDIR"; exit 1; }

SZ=$(stat -c%s "$IMG")
# round the resize target up to a MiB boundary
RSZ=$(( (SZ + 1048575) / 1048576 * 1048576 ))

t="$(mktemp -d)"
mkdir -p "$t/META-INF/com/google/android"
cp "$IMG" "$t/system.img"

# Edify updater-script: resize the current-slot system partition then raw-write
# the image to its mapped device. No set_active / no slot switch is emitted.
cat > "$t/META-INF/com/google/android/updater-script" <<'EDIFY'
ui_print("GammaOS bvN system-only flash");
ui_print("current slot, no slot switch, no other partitions");
show_progress(0.100000, 0);
update_dynamic_partitions(package_extract_file("dynamic_partitions_op_list"));
show_progress(0.800000, 0);
ui_print("Writing system...");
package_extract_file("system.img", "/dev/block/mapper/system");
show_progress(0.100000, 0);
ui_print("Done. Reboot system (do NOT let it switch slots).");
EDIFY

# resize op for the current-slot system logical partition
printf 'resize system %s\n' "$RSZ" > "$t/dynamic_partitions_op_list"

if [ -n "$UPD" ]; then
  cp "$UPD" "$t/META-INF/com/google/android/update-binary"
  chmod 0755 "$t/META-INF/com/google/android/update-binary"
else
  echo "WARNING: no --updater given; the zip will lack update-binary and recovery"
  echo "         will reject it. Supply an arm64 Edify updater to make it flashable."
fi

UNSIGNED="$t/unsigned.zip"
( cd "$t" && zip -qr -X "$UNSIGNED" META-INF dynamic_partitions_op_list system.img )

# whole-file OTA signature with the AOSP testkey (recovery verify_file check).
# Prefer signapk.jar via java with the conscrypt JNI on java.library.path (the
# host wrapper script is unreliable outside a full build env).
HOSTBIN="${HOSTBIN:-/work/GammaOSNextDistribution-A14/out/host/linux-x86}"
JAR="${SIGNAPK:-$(find "$HOSTBIN" -name signapk.jar 2>/dev/null | head -1)}"
LIBDIR="$(dirname "$(find "$HOSTBIN" -name libconscrypt_openjdk_jni.so 2>/dev/null | head -1)")"
[ -f "$JAR" ] || { echo "signapk.jar not found; pass --signapk <path>"; exit 1; }
echo "signing (whole-file -w) with $JAR using $KEYDIR/testkey"
java -Djava.library.path="$LIBDIR" -jar "$JAR" -w \
  "$KEYDIR/testkey.x509.pem" "$KEYDIR/testkey.pk8" "$UNSIGNED" "$OUT"
rm -rf "$t"
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
echo "flash: adb reboot recovery; then Apply update / adb sideload $OUT"
