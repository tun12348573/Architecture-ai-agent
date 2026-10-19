#!/usr/bin/env bash
# Download the pinned Blender LTS for Linux CI, verify its SHA256 and extract it.
# Usage: scripts/install_blender_ci.sh DEST_DIR   -> DEST_DIR/blender-5.2.2-linux-x64/blender
set -euo pipefail
dest="${1:?usage: install_blender_ci.sh DEST_DIR}"
version="5.2.2"
name="blender-${version}-linux-x64"
sha256="84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168"
if [ -x "${dest}/${name}/blender" ]; then
  echo "Blender ${version} already present in ${dest}"
  exit 0
fi
mkdir -p "${dest}"
archive="${dest}/${name}.tar.xz"
curl -fsSL --retry 3 -o "${archive}" "https://download.blender.org/release/Blender5.2/${name}.tar.xz"
echo "${sha256}  ${archive}" | sha256sum -c -
tar -xJf "${archive}" -C "${dest}"
rm -f "${archive}"
"${dest}/${name}/blender" --version | head -n 1
