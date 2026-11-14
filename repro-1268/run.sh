#!/usr/bin/env bash
# Usage: repro-1268/run.sh <path-to-quickshell>
# Needs a running Wayland session. Hyprland IPC goes to a fake server, not the real compositor.
set -euo pipefail

qs=$(realpath "$1")
here=$(cd "$(dirname "$0")" && pwd)
: "${XDG_RUNTIME_DIR:?needs a Wayland session}"
: "${WAYLAND_DISPLAY:?needs a Wayland session}"
case "$WAYLAND_DISPLAY" in /*) display=$WAYLAND_DISPLAY ;; *) display=$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY ;; esac

runtime=$(mktemp -d)
trap 'kill "${qs_pid:-}" "${fake_pid:-}" 2>/dev/null || true; rm -rf "$runtime"' EXIT
signature=repro1268

python3 -I "$here/fake_hyprland.py" "$runtime/hypr/$signature" > "$runtime/fake.log" 2>&1 &
fake_pid=$!
while [ ! -S "$runtime/hypr/$signature/.socket2.sock" ]; do sleep 0.05; done

XDG_RUNTIME_DIR=$runtime WAYLAND_DISPLAY=$display HYPRLAND_INSTANCE_SIGNATURE=$signature \
	"$qs" -p "$here/probe" > "$runtime/qs.log" 2>&1 &
qs_pid=$!

if ! wait "$fake_pid"; then
	cat "$runtime/fake.log" "$runtime/qs.log" >&2
	echo "ERROR: fake Hyprland scenario did not finish" >&2
	exit 2
fi

last=$(grep -a REPRO_TOPLEVELS "$runtime/qs.log" | tail -1 | sed 's/.*REPRO_TOPLEVELS //')
echo "quickshell: $("$qs" --version | head -1)"
echo "toplevels after close: $last"
if [[ $last == *abc1268* ]]; then
	echo "GHOST: the closed window was recreated from the stale j/clients response"
	exit 1
fi
echo "CLEAN: the closed window stayed closed"
