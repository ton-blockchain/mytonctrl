#!/bin/sh
# Run this script in the official TON image with its init.sh entrypoint overridden.
set -eu

artifacts_dir=${TON_ARTIFACTS_DIR:-/ton-artifacts}
bin_dir=${TON_EXPORT_BIN_DIR:-/usr/local/bin}
fift_dir=${TON_EXPORT_FIFT_DIR:-/usr/lib/fift}
smartcont_dir=${TON_EXPORT_SMARTCONT_DIR:-/usr/share/ton/smartcont}
stage_dir=
publish_dir=

fail() {
    printf 'TON artifact export: %s\n' "$*" >&2
    exit 1
}

cleanup() {
    if [ -n "$stage_dir" ]; then
        rm -rf -- "$stage_dir"
    fi
    if [ -n "$publish_dir" ]; then
        rm -rf -- "$publish_dir"
    fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM

for directory in "$bin_dir" "$fift_dir" "$smartcont_dir"; do
    [ -d "$directory" ] || fail "missing source directory: $directory"
done
for binary in validator-engine validator-engine-console lite-client generate-random-id fift func; do
    [ -x "$bin_dir/$binary" ] || fail "missing executable: $bin_dir/$binary"
done
for resource in "$fift_dir/Fift.fif" "$fift_dir/TonUtil.fif" "$smartcont_dir/wallet-v3.fif"; do
    [ -s "$resource" ] || fail "missing resource: $resource"
done

mkdir -p -- "$artifacts_dir/releases"
# flock is supplied by the official image. Holding the descriptor also releases
# the lock if an exporter is killed while it is copying a release.
exec 9>"$artifacts_dir/.export.lock"
flock -x 9

stage_dir=$(mktemp -d "$artifacts_dir/releases/.staging.XXXXXX")
mkdir -p -- "$stage_dir/bin" "$stage_dir/fift" "$stage_dir/smartcont"
# Dereference source symlinks so published files do not depend on image paths.
cp -aL -- "$bin_dir/." "$stage_dir/bin/"
cp -aL -- "$fift_dir/." "$stage_dir/fift/"
cp -aL -- "$smartcont_dir/." "$stage_dir/smartcont/"

# Relative paths, file contents and permissions identify a release. Neither
# timestamps nor the human-readable image reference change its identity.
(
    cd "$stage_dir"
    find bin fift smartcont -type f -print0 > .files.unsorted
    LC_ALL=C sort -z .files.unsorted > .files
    xargs -0 sha256sum -- < .files > content.sha256
    find bin fift smartcont -type f -printf '%m %p\0' > .modes.unsorted
    LC_ALL=C sort -z .modes.unsorted > modes.manifest
    rm -- .files.unsorted .files .modes.unsorted
)
digest=$(cat "$stage_dir/content.sha256" "$stage_dir/modes.manifest" | sha256sum)
digest=${digest%% *}
printf '%s\n' "$digest" > "$stage_dir/release.sha256"
if [ -n "${TON_IMAGE_REF:-}" ]; then
    printf '%s\n' "$TON_IMAGE_REF" > "$stage_dir/image-ref"
fi

release_dir=$artifacts_dir/releases/$digest
if [ -e "$release_dir" ] || [ -L "$release_dir" ]; then
    [ -d "$release_dir" ] && [ ! -L "$release_dir" ] || fail "invalid existing release: $release_dir"
    cmp -s "$stage_dir/content.sha256" "$release_dir/content.sha256" || fail "existing release manifest differs: $release_dir"
    cmp -s "$stage_dir/modes.manifest" "$release_dir/modes.manifest" || fail "existing release permissions manifest differs: $release_dir"
    (cd "$release_dir" && sha256sum --check --quiet content.sha256) || fail "existing release has been modified: $release_dir"
    # Retagging identical artifacts must report the newly exported image. The
    # controller pins this metadata in its private snapshot before execution.
    if [ -f "$stage_dir/image-ref" ]; then
        mv -Tf -- "$stage_dir/image-ref" "$release_dir/image-ref"
    else
        rm -f -- "$release_dir/image-ref"
    fi
    rm -rf -- "$stage_dir"
else
    mv -- "$stage_dir" "$release_dir"
fi
stage_dir=

publish_dir=$(mktemp -d "$artifacts_dir/.publish.XXXXXX")
ln -s "releases/$digest" "$publish_dir/current"
# GNU mv -T replaces the link itself, including an existing dangling link.
mv -Tf -- "$publish_dir/current" "$artifacts_dir/current"
printf 'Published TON artifacts: %s\n' "$digest"
