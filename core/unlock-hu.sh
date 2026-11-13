#!/system/bin/sh
# Based on supplied unlock-hu.sh; host orchestrators handle bounded retries.
V=com.ecarx.xsfinstallverifier
P=/product/build.prop
K=ro.vendor.ecarx.app_verify
MARK=/data/local/tmp/gt-unlock.remount

park() {
    root="$1"
    moved=
    what=
    for u in "$root"/overlay/*/upper; do
        [ -d "$u" ] || continue
        [ -n "$(ls -A "$u" 2>/dev/null)" ] || continue
        [ -n "$moved" ] || moved="$root/old-$(date +%Y%m%d-%H%M%S)-$$"
        name=$(basename "$(dirname "$u")")
        n=$(find "$u" -mindepth 1 2>/dev/null | wc -l | tr -d " ")
        mkdir -p "$moved/$name" || return 1
        for f in "$u"/* "$u"/.[!.]* "$u"/..?*; do
            [ -e "$f" ] || [ -L "$f" ] || continue
            mv "$f" "$moved/$name/" || return 1
        done
        what="$what $name: $n"
    done
    [ -z "$moved" ] || echo "Old firmware layer moved aside (${what# }) - ${moved#$root/} in the scratch partition, not deleted"
    return 0
}

scratch() {
    if mount | grep -q ' on /mnt/scratch '; then
        park /mnt/scratch
        return
    fi
    [ -e /dev/block/mapper/scratch ] || return 0
    M=/data/local/tmp/gt-scratch
    mkdir -p "$M" || return 1
    if ! mount /dev/block/mapper/scratch "$M" 2>/dev/null && ! mount -t f2fs /dev/block/mapper/scratch "$M" 2>/dev/null &&
        ! mount -t ext4 /dev/block/mapper/scratch "$M" 2>/dev/null; then
        rmdir "$M" 2>/dev/null
        echo "ERROR: the scratch partition exists but will not open - not touching system partitions"
        return 1
    fi
    park "$M"
    r=$?
    umount "$M" || return 1
    rmdir "$M" 2>/dev/null
    return $r
}

fail() { echo "ERROR: $*"; echo GT:FAIL; exit 1; }
[ "$(id -u)" = 0 ] || fail 'no root (adb root)'

users=$(pm list users 2>/dev/null) || fail 'could not get head unit users'
users=$(printf '%s\n' "$users" | sed -n 's/.*UserInfo{\([0-9]*\):.*/\1/p')
[ -n "$users" ] || fail 'empty user list'
property=$(getprop "$K") || fail 'could not read app_verify'
case "$property" in true|false|'') ;; *) fail 'unknown app_verify value' ;; esac

check_settings() {
    for setting in package_verifier_enable verifier_verify_adb_installs; do
        [ "$(settings get global "$setting" 2>/dev/null)" = 0 ] || return 1
    done
}

check_packages() {
    for user in $users; do
        packages=$(pm list packages -e --user "$user" 2>/dev/null) || return 1
        if printf '%s\n' "$packages" | grep -qx "package:$V"; then return 1; fi
    done
}

if [ "${1:-}" = verify ]; then
    check_settings || fail 'after reboot the install-check settings are not 0'
    check_packages || fail 'after reboot AutoInstallVerifier is enabled or its state is unavailable'
    [ "$property" != true ] || fail 'after reboot app_verify=true'
    echo GT:OK
    exit 0
fi

disabled=
for user in $users; do
    packages=$(pm list packages -e --user "$user" 2>/dev/null) || fail 'could not check AutoInstallVerifier'
    if printf '%s\n' "$packages" | grep -qx "package:$V"; then
        pm disable-user --user "$user" "$V" || fail "AutoInstallVerifier did not turn off for user $user"
        disabled=1
    fi
done
# As in the supplied helper: give the system time before checking it stayed off.
[ -z "$disabled" ] || sleep 15
check_packages || fail 'AutoInstallVerifier did not turn off'
echo 'AutoInstallVerifier: absent or disabled for all users'

for setting in package_verifier_enable verifier_verify_adb_installs; do
    if [ "$(settings get global "$setting" 2>/dev/null)" != 0 ]; then
        settings put global "$setting" 0 || fail "setting $setting was not written"
    fi
done
check_settings || fail 'could not disable install checks in settings'

# After the verifier and settings, as in the supplied helper: those still help here.
if [ -z "$property" ] && [ -d /system/etc/security/parrot ] && getprop ro.build.product | grep -q e245_eu; then
    echo 'On this firmware Parrot has no supported switch'
    echo GT:PARROT
    exit 0
fi

if [ "$property" != true ]; then
    rm -f "$MARK"
    echo 'Parrot signature check: disabled'
    echo GT:OK
    exit 0
fi

# Literal dots: do not match a different property by accident.
if grep -q '^ro\.vendor\.ecarx\.app_verify=false$' "$P" 2>/dev/null; then
    echo GT:REBOOT
    exit 0
fi

# adb remount may yield either overlayfs or a writable physical filesystem.
# Strictly verify active mount is rw (read-write), not read-only overlay
if mount | grep ' on /product ' | tail -n 1 | grep -q '[(,]rw[,)]'; then
    if sed -i 's/^ro\.vendor\.ecarx\.app_verify=true$/ro.vendor.ecarx.app_verify=false/' "$P" &&
        grep -q '^ro\.vendor\.ecarx\.app_verify=false$' "$P"; then
        echo GT:REBOOT
    else
        fail 'could not modify app_verify in /product/build.prop'
    fi
    exit 0
fi

if [ -f "$MARK" ]; then
    scratch || fail 'old firmware layer was not moved aside'
    # Consume this recovery attempt before reboot so a failed/interrupted
    # remount can be requested again on the next pass.
    rm -f "$MARK" || fail 'could not delete the remount marker'
    echo GT:REBOOT
    exit 0
fi

scratch || fail 'old firmware layer was not moved aside'
touch "$MARK" || fail 'could not save the remount marker'
echo 'Signature check enabled; remount required'
echo GT:REMOUNT
