#!/usr/bin/env bash
# build_flash_ota.sh - Build a testkey-signed, recovery-flashable zip that writes
# ANY set of partitions on the CURRENT slot, with no slot switch. Self-contained:
# uses the vendored updater (prebuilt/update-binary-arm64), vendored signapk, and
# the AOSP testkey in keys/.
#
# Handles both partition types:
#   logical  - dynamic partitions inside super (system, vendor, product,
#              system_ext, odm, vendor_dlkm, odm_dlkm). Resized to fit and written
#              via /dev/block/mapper/<name> (current slot).
#   physical - real partitions (boot, vendor_boot, dtbo, vbmeta, recovery, abl,
#              xbl, tz, aop, devcfg, ...). Written via
#              /dev/block/bootdevice/by-name/<name><slot_suffix> (current slot,
#              resolved at flash time with getprop ro.boot.slot_suffix).
#
# No set_active is emitted, so the active slot never changes.
#
# Usage:
#   build_flash_ota.sh --out flash.zip \
#       --part <name>:<image>[:logical|physical] [--part ...] \
#       [--updater <path>] [--signapk <signapk.jar>]
# Examples:
#   # system GSI only (logical):
#   build_flash_ota.sh --out sys.zip --part system:lineage-...-arm64_bvN.img
#   # boot + dtbo (physical) together:
#   build_flash_ota.sh --out bootset.zip --part boot:boot.img:physical --part dtbo:dtbo.img:physical
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT=""; UPD="${UPDATER:-$HERE/prebuilt/update-binary-arm64}"; KEYDIR="$HERE/keys"
SIGNAPK="${SIGNAPK:-$HERE/tools/signing/signapk/signapk.jar}"
LIBDIR="$(dirname "$SIGNAPK")"
SLOT="${SLOT:-_a}"    # slot suffix for PHYSICAL A/B partitions (this updater has
                      # no getprop, so the slot is fixed at build time; the device
                      # is on _a per recon). Set --slot _b to target the b slot.
declare -a PARTS=()
while [ $# -gt 0 ]; do case "$1" in
  --out) OUT="$2"; shift 2;;
  --part) PARTS+=("$2"); shift 2;;
  --updater) UPD="$2"; shift 2;;
  --slot) SLOT="$2"; shift 2;;
  --signapk) SIGNAPK="$2"; LIBDIR="$(dirname "$2")"; shift 2;;
  --key-dir) KEYDIR="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 2;; esac; done
[ -n "${OUT:?--out required}" ]
[ "${#PARTS[@]}" -gt 0 ] || { echo "need at least one --part name:image[:type]"; exit 2; }
[ -f "$KEYDIR/testkey.pk8" ] || { echo "testkey missing under $KEYDIR"; exit 1; }

# default type guess by name if not given
LOGICAL_RE='^(system|system_ext|product|vendor|odm|vendor_dlkm|odm_dlkm)$'
t="$(mktemp -d)"; mkdir -p "$t/META-INF/com/google/android"
SCRIPT="$t/META-INF/com/google/android/updater-script"
OPLIST="$t/dynamic_partitions_op_list"; : > "$OPLIST"
{
  echo 'ui_print("GammaOS flash: current slot, no slot switch");'
  echo 'show_progress(0.050000, 0);'
} > "$SCRIPT"

have_logical=0
for spec in "${PARTS[@]}"; do
  name="${spec%%:*}"; rest="${spec#*:}"; img="${rest%%:*}"; typ="${rest#*:}"
  [ "$typ" = "$rest" ] && typ=""    # no explicit type
  [ -f "$img" ] || { echo "image not found: $img"; exit 1; }
  if [ -z "$typ" ]; then [[ "$name" =~ $LOGICAL_RE ]] && typ=logical || typ=physical; fi
  cp "$img" "$t/$name.img"
  if [ "$typ" = logical ]; then
    have_logical=1
    sz=$(stat -c%s "$img"); rsz=$(( (sz + 1048575) / 1048576 * 1048576 ))
    echo "resize $name $rsz" >> "$OPLIST"
    # map_partition resolves the current-slot dm device for the logical partition
    # (no getprop needed; this updater registers map_partition).
    {
      echo "ui_print(\"writing logical $name...\");"
      echo "package_extract_file(\"$name.img\", map_partition(\"$name\"));"
    } >> "$SCRIPT"
  else
    # physical A/B partition: this updater has no getprop, so the slot suffix is
    # baked at build time (--slot, default _a).
    {
      echo "ui_print(\"writing $name (slot $SLOT)...\");"
      echo "package_extract_file(\"$name.img\", \"/dev/block/bootdevice/by-name/$name$SLOT\");"
    } >> "$SCRIPT"
  fi
  echo "  + $name ($typ) <- $img"
done

# emit update_dynamic_partitions at the top if any logical part needs a resize
if [ "$have_logical" = 1 ]; then
  sed -i '/show_progress(0.050000, 0);/a update_dynamic_partitions(package_extract_file("dynamic_partitions_op_list"));' "$SCRIPT"
fi
echo 'ui_print("Done. Reboot; the active slot is unchanged.");' >> "$SCRIPT"

# update-binary
[ -f "$UPD" ] || { echo "updater not found at $UPD (build with scripts/build_updater.sh)"; exit 1; }
cp "$UPD" "$t/META-INF/com/google/android/update-binary"; chmod 0755 "$t/META-INF/com/google/android/update-binary"

UNSIGNED="$t/unsigned.zip"
( cd "$t" && zip -qr -X "$UNSIGNED" META-INF dynamic_partitions_op_list *.img )
[ -f "$SIGNAPK" ] || { echo "signapk not found at $SIGNAPK"; exit 1; }
java -Djava.library.path="$LIBDIR" -jar "$SIGNAPK" -w \
  "$KEYDIR/testkey.x509.pem" "$KEYDIR/testkey.pk8" "$UNSIGNED" "$OUT"
rm -rf "$t"
echo "wrote $OUT ($(du -h "$OUT" | cut -f1))"
echo "flash: adb reboot recovery ; adb sideload $OUT"
