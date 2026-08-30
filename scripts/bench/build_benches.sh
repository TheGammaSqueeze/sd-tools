#!/usr/bin/env bash
# Build the on-device microbench suite (aarch64 Android) with the NDK.
# Covers the GPU/CPU/MEM benches plus the driver-CPU tools built during the
# Turnip safe-optimization work: drawbench (per-draw recording cost), descbench
# (per-draw descriptor-set-bind cost), occbench (high-register-pressure fragment
# for wave-occupancy). Graphics benches embed their SPIR-V via committed
# *_spv.h headers, so glslang is only needed if you regenerate a shader.
#
# Usage: ./build_benches.sh            # build everything into scripts/bench/
#        NDK=/path ./build_benches.sh  # override NDK location
# Then: adb push <bench> /data/local/tmp/ ; bind-mount a driver over
#       /vendor/lib64/hw/vulkan.adreno.so ; run ; umount (see device_run_bench.sh).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/src"
NDK="${NDK:-/work/android-ndk-r27c}"
API="${API:-30}"
CC="$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android${API}-clang"
[ -x "$CC" ] || { echo "NDK clang not found: $CC (set NDK=...)"; exit 1; }

ok=0; fail=0
for c in "$SRC"/*.c; do
  name="$(basename "$c" .c)"
  # vkdump is a diagnostic helper, skip if you only want benches; kept here.
  if grep -q "vulkan/vulkan.h" "$c"; then libs="-lvulkan"; else libs="-lm"; fi
  if "$CC" -O2 -I"$SRC" "$c" -o "$HERE/$name" $libs 2>/tmp/bench_build_err; then
    ok=$((ok+1)); echo "built  $name"
  else
    fail=$((fail+1)); echo "FAILED $name:"; sed 's/^/    /' /tmp/bench_build_err | head -3
  fi
done
echo "done: $ok built, $fail failed -> binaries in $HERE"
