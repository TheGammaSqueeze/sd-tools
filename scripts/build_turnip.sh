#!/usr/bin/env bash
# build_turnip.sh - Cross-build our own Mesa Turnip Vulkan driver for the Parrot
# GPU (Adreno 710 = a702), targeting Android 12 (API 31), packaged for AdrenoTools
# and for the system-wide swap (scripts/swap_vulkan_turnip.sh).
#
# Why build our own: the Anbernic Turnip is fine but declares minApi 34 (Android
# 14); this device is Android 12. Building against API 31 removes that mismatch,
# and lets us pin the Mesa version and tune options for a702/gen7. a702 is a
# first-class Turnip target, so this is a normal Mesa build, not a port.
#
# Produces: gpu/turnip-selfbuilt/vulkan.turnip.so (+ meta.json).
#
# Requires: meson, ninja, python3-mako, cmake, an Android NDK, and glslang. Set
# NDK to your NDK path. glslang is built from source if glslangValidator is not
# on PATH.
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
NDK="${NDK:-/work/android-ndk-r27c}"
API="${API:-31}"
WORK="${WORK:-/work/turnip-build}"
TC="$NDK/toolchains/llvm/prebuilt/linux-x86_64"
[ -x "$TC/bin/aarch64-linux-android$API-clang" ] || { echo "NDK clang for API $API not found under $NDK"; exit 1; }
mkdir -p "$WORK"

# 1. glslangValidator (Mesa needs it to compile the ASTC/BVH meta shaders)
if ! command -v glslangValidator >/dev/null 2>&1; then
  if [ ! -x "$WORK/glslang/bin/glslangValidator" ]; then
    git clone --depth 1 https://github.com/KhronosGroup/glslang.git "$WORK/glslang-src"
    cmake -S "$WORK/glslang-src" -B "$WORK/glslang-src/build" -DCMAKE_BUILD_TYPE=Release \
      -DENABLE_OPT=0 -DGLSLANG_TESTS=OFF -DENABLE_GLSLANG_BINARIES=ON
    cmake --build "$WORK/glslang-src/build" -j"$(nproc)"
    mkdir -p "$WORK/glslang/bin"
    ln -sf "$WORK/glslang-src/build/StandAlone/glslang" "$WORK/glslang/bin/glslangValidator"
  fi
  export PATH="$WORK/glslang/bin:$PATH"
fi

# 2. Mesa source
[ -d "$WORK/mesa" ] || git clone --depth 1 https://gitlab.freedesktop.org/mesa/mesa.git "$WORK/mesa"
cd "$WORK/mesa"
# Fix: the ASTC decoder compute shader uses local_size_x_id (spec-constant
# workgroup size) which requires SPIR-V >= 1.2; the stock rule defaults to 1.0.
if ! grep -q "spirv1.3', '-S', 'comp'" src/vulkan/runtime/meson.build; then
  sed -i "s/prog_glslang, '-V', '-S', 'comp', '-x', '-o', '@OUTPUT@', '@INPUT@',/prog_glslang, '-V', '--target-env', 'spirv1.3', '-S', 'comp', '-x', '-o', '@OUTPUT@', '@INPUT@',/" src/vulkan/runtime/meson.build
fi

# 3. Android aarch64 cross file (static libc++ so the driver is self-contained)
cat > android-aarch64.cross <<EOF
[binaries]
ar = '$TC/bin/llvm-ar'
c = ['$TC/bin/aarch64-linux-android$API-clang']
cpp = ['$TC/bin/aarch64-linux-android$API-clang++']
c_ld = '$TC/bin/ld.lld'
cpp_ld = '$TC/bin/ld.lld'
strip = '$TC/bin/llvm-strip'
pkg-config = ['env', 'PKG_CONFIG_LIBDIR=/dev/null', 'pkg-config']
[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8'
endian = 'little'
[properties]
needs_exe_wrapper = true
[built-in options]
cpp_link_args = ['-static-libstdc++']
c_link_args = ['-static-libstdc++']
EOF

# 4. Configure Vulkan-only Turnip on the KGSL backend
rm -rf build-android
meson setup build-android --cross-file android-aarch64.cross \
  -Dbuildtype=release -Dplatforms=android -Dandroid-stub=true \
  -Dvulkan-drivers=freedreno -Dgallium-drivers= -Dfreedreno-kmds=kgsl -Dvulkan-beta=true \
  -Degl=disabled -Dgles1=disabled -Dgles2=disabled -Dopengl=false -Dglx=disabled \
  -Dgbm=disabled -Dllvm=disabled -Dshared-glapi=disabled -Dvideo-codecs=

# 5. Build + strip + package
ninja -C build-android src/freedreno/vulkan/libvulkan_freedreno.so
OUT="$HERE/gpu/turnip-selfbuilt"
mkdir -p "$OUT"
"$TC/bin/llvm-strip" -o "$OUT/vulkan.turnip.so" build-android/src/freedreno/vulkan/libvulkan_freedreno.so
echo "built $OUT/vulkan.turnip.so ($(stat -c%s "$OUT/vulkan.turnip.so") bytes)"
readelf -sW "$OUT/vulkan.turnip.so" | grep -qw HMI && echo "exports HMI (Android loadable): YES"
