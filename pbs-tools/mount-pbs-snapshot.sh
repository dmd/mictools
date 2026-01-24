#!/usr/bin/env bash
set -eEuo pipefail

AUTH_FILE="/home/ddrucker/PBS-auth"
PBS_REPOSITORY="${PBS_REPOSITORY:-}"
ARCHIVES=()
DEBUG=0
CLEANING_UP=0
ALLOW_RENAME=1
MOUNT_UNKNOWN=1
CLEANUP=0
REUSE_MAPPED=1

usage() {
  cat <<'USAGE'
Usage:
  mount-pbs-snapshot.sh [options] <snapshot> <mount_path>

Options:
  --auth-file <path>     Path to PBS auth env file (default: /home/ddrucker/PBS-auth)
  --cleanup              Unmount/deactivate/unmap resources under mount_path
  --debug                Print diagnostic output
  -h, --help             Show help

Example:
  ./mount-pbs-snapshot.sh host/vm/2024-01-01T00:00:00Z /mnt/pbs-snap
  ./mount-pbs-snapshot.sh --cleanup /mnt/pbs-snap
USAGE
}

log() { printf '[%s] %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*"; }
warn() { printf '[%s] WARN: %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2; }
err() { printf '[%s] ERROR: %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2; }
debug() {
  if [ "$DEBUG" -eq 1 ]; then
    printf '[%s] DEBUG: %s\n' "$(date +'%Y-%m-%d %H:%M:%S')" "$*" >&2
  fi
  return 0
}

sanitize_name() {
  printf '%s' "$1" | tr '/:@ ' '____' | tr -cd 'A-Za-z0-9._-'
}

need_cmd() {
  local cmd=$1
  if [[ "$cmd" == /* ]]; then
    if [ ! -x "$cmd" ]; then
      err "Missing required command: $cmd"
      exit 1
    fi
    return
  fi
  if ! command -v "$cmd" >/dev/null 2>&1; then
    err "Missing required command: $cmd"
    exit 1
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --auth-file)
      AUTH_FILE="$2"; shift 2 ;;
    --debug)
      DEBUG=1; shift ;;
    --cleanup)
      CLEANUP=1; shift ;;
    -h|--help)
      usage; exit 0 ;;
    --)
      shift; break ;;
    -*)
      err "Unknown option: $1"; usage; exit 1 ;;
    *)
      break ;;
  esac
done

if [ "$CLEANUP" -eq 1 ]; then
  if [ $# -lt 1 ]; then
    usage
    exit 1
  fi
  MOUNT_ROOT="$1"
else
  if [ $# -lt 2 ]; then
    usage
    exit 1
  fi
  SNAPSHOT="$1"
  MOUNT_ROOT="$2"
fi

if [ "$(id -u)" -ne 0 ]; then
  err "Run as root (mapping and mounting require privileges)."
  exit 1
fi

need_cmd proxmox-backup-client
need_cmd mount
need_cmd lsblk
need_cmd blkid
need_cmd losetup
need_cmd python3
need_cmd /sbin/lvm
need_cmd /sbin/dmsetup
need_cmd /sbin/blockdev
need_cmd truncate
need_cmd findmnt

cleanup_all() {
  local mp vgs dm loops files loopdevs
  set +e
  if [ -d "$MOUNT_ROOT" ]; then
    findmnt -rn -o TARGET | awk -v root="$MOUNT_ROOT" '$0==root || index($0, root"/")==1{print}' | sort -r | while read -r mp; do
      umount "$mp" 2>/dev/null || true
    done
    umount -R "$MOUNT_ROOT" 2>/dev/null || true
  fi

  vgs=$(/sbin/lvm vgs --noheadings -o vg_name --select 'vg_name=~^pbs_' 2>/dev/null | awk '{$1=$1};1')
  if [ -n "$vgs" ]; then
    printf '%s\n' "$vgs" | while read -r vg; do
      [ -n "$vg" ] || continue
      /sbin/lvm vgchange -an --nolocking "$vg" >/dev/null 2>&1 || true
    done
  fi

  dm=$(/sbin/dmsetup ls --target snapshot 2>/dev/null | awk '$1 ~ /^pbs_cow_/ {print $1}')
  if [ -n "$dm" ]; then
    printf '%s\n' "$dm" | while read -r name; do
      [ -n "$name" ] || continue
      /sbin/dmsetup remove "$name" 2>/dev/null || true
    done
  fi

  loops=$(losetup -a | grep '/tmp/pbs-cow-' | cut -d: -f1)
  if [ -n "$loops" ]; then
    printf '%s\n' "$loops" | while read -r loopdev; do
      [ -n "$loopdev" ] || continue
      losetup -d "$loopdev" 2>/dev/null || true
    done
  fi

  files=$(ls /tmp/pbs-cow-* 2>/dev/null || true)
  if [ -n "$files" ]; then
    printf '%s\n' "$files" | while read -r f; do
      [ -n "$f" ] || continue
      rm -f "$f" 2>/dev/null || true
    done
  fi

  loopdevs=$(lsblk -rno NAME,TYPE,MOUNTPOINT,PKNAME 2>/dev/null | awk -v root="$MOUNT_ROOT" '
    $2=="part" && index($3, root)==1 && $4!="" {print $4}
    $2=="loop" && index($3, root)==1 {print $1}
  ' | sort -u)
  if [ -n "$loopdevs" ]; then
    printf '%s\n' "$loopdevs" | while read -r name; do
      [ -n "$name" ] || continue
      losetup -d "/dev/${name}" 2>/dev/null || true
    done
  fi

  map_out=$(proxmox-backup-client unmap 2>&1 || true)
  debug "cleanup unmap output (initial):\n$map_out"
  for _ in 1 2 3; do
    map_out=$(proxmox-backup-client unmap 2>&1 || true)
    debug "cleanup unmap output (loop):\n$map_out"
    mapped=$(printf '%s\n' "$map_out" | grep -o '/dev/[^: ]*' | sort -u)
    [ -z "$mapped" ] && break
    printf '%s\n' "$mapped" | while read -r dev; do
      [ -n "$dev" ] || continue
      debug "cleanup unmap device: $dev"
      proxmox-backup-client unmap "$dev" >/dev/null 2>&1 || true
      if printf '%s\n' "$dev" | grep -q '^/dev/loop'; then
        losetup -d "$dev" 2>/dev/null || true
      fi
    done
  done
  map_out=$(proxmox-backup-client unmap 2>&1 || true)
  debug "cleanup unmap output (final):\n$map_out"
  mapped=$(printf '%s\n' "$map_out" | grep -o '/dev/loop[^: ]*' | sort -u)
  if [ -n "$mapped" ]; then
    printf '%s\n' "$mapped" | while read -r dev; do
      [ -n "$dev" ] || continue
      debug "cleanup unmap device (final): $dev"
      proxmox-backup-client unmap "$dev" >/dev/null 2>&1 || true
      losetup -d "$dev" 2>/dev/null || true
    done
  fi

  if [ -d "$MOUNT_ROOT" ]; then
    find "$MOUNT_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
    (
      shopt -s nullglob dotglob
      for entry in "$MOUNT_ROOT"/*; do
        rm -rf "$entry" 2>/dev/null || true
      done
    )
    find "$MOUNT_ROOT" -depth -mindepth 1 -type d -empty -exec rmdir {} + 2>/dev/null || true
  fi

  if [ -d "$MOUNT_ROOT" ]; then
    find "$MOUNT_ROOT" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
    find "$MOUNT_ROOT" -depth -mindepth 1 -type d -empty -exec rmdir {} + 2>/dev/null || true
  fi

  debug "cleanup removing mount root: $MOUNT_ROOT"
  rm -rf "$MOUNT_ROOT" 2>/dev/null || true
  if [ -e "$MOUNT_ROOT" ]; then
    warn "Cleanup could not remove mount root: $MOUNT_ROOT"
    ls -la "$MOUNT_ROOT" 2>/dev/null || true
  fi
  set -e
}

if [ "$CLEANUP" -eq 1 ]; then
  cleanup_all
  log "Cleanup complete."
  exit 0
fi

if [ -f "$AUTH_FILE" ]; then
  # shellcheck source=/dev/null
  . "$AUTH_FILE"
else
  warn "Auth file not found: $AUTH_FILE"
fi

if [ -z "${PBS_REPOSITORY:-}" ]; then
  err "PBS_REPOSITORY not set. Set in auth file/env."
  exit 1
fi

if [ ! -d "$MOUNT_ROOT" ]; then
  mkdir -p "$MOUNT_ROOT"
fi

if mountpoint -q "$MOUNT_ROOT"; then
  err "Mount path is already a mountpoint: $MOUNT_ROOT"
  exit 1
fi

if [ -n "$(find "$MOUNT_ROOT" -mindepth 1 -maxdepth 1 2>/dev/null)" ]; then
  err "Mount path not empty: $MOUNT_ROOT"
  exit 1
fi

PBS_EXTRA=(--repository "$PBS_REPOSITORY")

list_archives() {
  local out code json_names stderr_file attempt
  stderr_file=$(mktemp)
  for attempt in 1 2; do
    if out=$(proxmox-backup-client snapshot files "$SNAPSHOT" "${PBS_EXTRA[@]}" --output-format json 2>"$stderr_file"); then
      if [ -s "$stderr_file" ]; then
        debug "snapshot files (json) stderr:\n$(cat "$stderr_file")"
      fi
      debug "snapshot files (json) output:\n$out"
      if [ -z "$out" ]; then
        err "Empty response from snapshot files for: $SNAPSHOT"
        rm -f "$stderr_file"
        return 1
      fi
      if json_names=$(printf '%s\n' "$out" | python3 -c '
import json,sys
text=sys.stdin.read()
if not text:
    sys.exit(3)
start=min([i for i in [text.find("{"), text.find("[")] if i != -1], default=-1)
if start == -1:
    sys.exit(3)
text=text[start:].strip()
try:
    raw=json.loads(text)
except json.JSONDecodeError:
    sys.exit(3)
if isinstance(raw, dict):
    if isinstance(raw.get("files"), list):
        data = raw["files"]
    elif isinstance(raw.get("data"), list):
        data = raw["data"]
    else:
        data = []
else:
    data = raw
names=[]
for entry in data:
    if isinstance(entry, str):
        name = entry
    elif isinstance(entry, dict):
        name = entry.get("filename") or entry.get("file") or entry.get("path") or entry.get("name")
    else:
        name = None
    if not name:
        continue
    if name.endswith(".img") and not name.endswith(".img.fidx"):
        names.append(name)
if not names:
    for entry in data:
        if isinstance(entry, dict):
            name = entry.get("filename") or entry.get("file") or entry.get("path") or entry.get("name")
            if name and name.endswith(".img.fidx"):
                names.append(name[:-5])
if not names:
    sys.exit(2)
print("\\n".join(names))
'); then
        debug "json parse exit=0 names=[$json_names]"
        rm -f "$stderr_file"
        printf '%s\n' "$json_names"
        return 0
      else
        code=$?
        debug "json parse exit=$code names=[]"
      fi
      if [ $code -eq 3 ]; then
        err "Snapshot files output was not valid JSON."
      fi
    else
      err "Failed to list snapshot files for: $SNAPSHOT"
      if [ -s "$stderr_file" ]; then
        err "Output: $(cat "$stderr_file")"
      else
        err "Output: $out"
      fi
    fi
    if [ $attempt -eq 1 ]; then
      sleep 1
    fi
  done
  if [ "$DEBUG" -eq 0 ]; then
    err "Snapshot files JSON output (last attempt): $out"
  fi
  rm -f "$stderr_file"
  return 1
}

map_archive() {
  local archive=$1
  local before after output dev
  before=$(losetup -a | awk -F: '{print $1}' | sort || true)
  output=$(proxmox-backup-client map "$SNAPSHOT" "$archive" "${PBS_EXTRA[@]}" 2>&1 || true)
  if printf '%s\n' "$output" | grep -qi 'already mapped'; then
    if [ "$REUSE_MAPPED" -eq 0 ]; then
      err "Archive already mapped. Run cleanup first: --cleanup <mount_path>"
      err "map output: $output"
      return 1
    fi
    dev=$(losetup -a | grep "$archive" | awk -F: '{print $1}' | head -n1)
    if [ -n "$dev" ]; then
      printf '%s\n' "$dev"
      return 0
    fi
  fi
  dev=$(printf '%s\n' "$output" | grep -Eo '/dev/(loop|nbd|mapper)/[^[:space:]]+' | head -n1 || true)
  if [ -z "$dev" ]; then
    after=$(losetup -a | awk -F: '{print $1}' | sort || true)
    dev=$(comm -13 <(printf '%s\n' "$before") <(printf '%s\n' "$after") | head -n1 || true)
  fi
  if [ -z "$dev" ]; then
    err "Failed to determine mapped device for $archive"
    err "map output: $output"
    return 1
  fi
  printf '%s\n' "$dev"
}

mount_lv() {
  local lv_path=$1
  local target=$2
  mkdir -p "$target"
  mount -o ro,nosuid,nodev "$lv_path" "$target"
}

detect_fstype() {
  local dev=$1
  local fstype
  fstype=$(blkid -p -o value -s TYPE "$dev" 2>/dev/null | head -n1 || true)
  if [ -z "$fstype" ]; then
    fstype=$(lsblk -no FSTYPE "$dev" 2>/dev/null | head -n1 || true)
  fi
  printf '%s\n' "$fstype"
}

create_cow_snapshot() {
  local origin_dev=$1
  local archive=$2
  local size_sectors cow_file cow_loop dm_name dm_dev

  size_sectors=$(/sbin/blockdev --getsz "$origin_dev" 2>/dev/null || true)
  if [ -z "$size_sectors" ]; then
    err "Failed to read size for PV: $origin_dev"
    return 1
  fi

  cow_file=$(mktemp -p /tmp "pbs-cow-XXXXXX")
  truncate -s 256M "$cow_file"
  cow_loop=$(losetup --find --show "$cow_file")

  dm_name="pbs_cow_$(sanitize_name "${archive}_${RANDOM}_$$")"
  if ! /sbin/dmsetup create "$dm_name" --table "0 $size_sectors snapshot $origin_dev $cow_loop N 8"; then
    losetup -d "$cow_loop" 2>/dev/null || true
    rm -f "$cow_file" 2>/dev/null || true
    err "Failed to create dm snapshot for $origin_dev"
    return 1
  fi

  dm_dev="/dev/mapper/$dm_name"
  cow_files+=("$cow_file")
  cow_loops+=("$cow_loop")
  cow_dms+=("$dm_name")
  printf '%s\n' "$dm_dev"
}

handle_lvm_pv() {
  local pv_dev=$1
  local archive=$2
  local vg_name lv fstype lv_path mp_subdir mount_point dm_name lvm_cfg lvm_cfg_rw
  lvm_cfg="devices { filter=[\"a|${pv_dev}|\",\"r|.*|\"] write_cache_state=0 } global { metadata_read_only=1 locking_type=0 }"
  lvm_cfg_rw="devices { filter=[\"a|${pv_dev}|\",\"r|.*|\"] write_cache_state=0 } global { metadata_read_only=0 locking_type=0 }"

  vg_name=$(/sbin/lvm vgs --noheadings -o vg_name --config "$lvm_cfg" --readonly --nolocking 2>/dev/null | awk 'NR==1{print $1}')
  if [ -z "$vg_name" ]; then
    err "Failed to detect VG on PV: $pv_dev"
    return 1
  fi
  if compgen -G "/dev/mapper/${vg_name//-/--}-*" >/dev/null; then
    local base suffix new_vg
    base="$(sanitize_name "${SNAPSHOT}_${archive}")"
    base="${base:0:40}"
    suffix="$(date +%s)_$$"
    new_vg="pbs_${base}_${suffix}"
    log "Renaming VG via vgimportclone: $vg_name -> $new_vg (from $pv_dev)"
    if ! /sbin/lvm vgimportclone -n "$new_vg" --import --config "$lvm_cfg_rw" "$pv_dev"; then
      local cow_dev
      warn "vgimportclone failed on read-only PV; creating COW snapshot to allow metadata writes."
      cow_dev=$(create_cow_snapshot "$pv_dev" "$archive")
      if [ -z "$cow_dev" ]; then
        err "Failed to create COW snapshot for: $pv_dev"
        return 1
      fi
      lvm_cfg_rw="devices { filter=[\"a|${cow_dev}|\",\"r|.*|\"] write_cache_state=0 } global { metadata_read_only=0 locking_type=0 }"
      log "Retrying vgimportclone on COW snapshot: $cow_dev"
      /sbin/lvm vgimportclone -n "$new_vg" --import --config "$lvm_cfg_rw" --nolocking "$cow_dev"
      lvm_cfg="devices { filter=[\"a|${cow_dev}|\",\"r|.*|\"] write_cache_state=0 } global { metadata_read_only=1 locking_type=0 }"
      pv_dev="$cow_dev"
    fi
    vg_name="$new_vg"
  fi

  log "Activating VG read-only: $vg_name (from $pv_dev)"
  /sbin/lvm vgchange -ay --readonly --activationmode partial --config "$lvm_cfg" --nolocking "$vg_name"
  /sbin/lvm lvchange -ay -K --ignoreactivationskip --activationmode partial --config "$lvm_cfg" --nolocking "$vg_name" >/dev/null 2>&1 || true
  imported_vgs+=("$vg_name")

  while IFS='|' read -r lv lv_path lv_attr; do
    [ -n "$lv" ] || continue
    /sbin/lvm lvchange -ay --activationmode partial --config "$lvm_cfg" --nolocking "$vg_name/$lv" >/dev/null 2>&1 || true
    if [ -z "$lv_path" ]; then
      lv_path="/dev/${vg_name}/${lv}"
    fi
    if [ ! -e "$lv_path" ]; then
      dm_name="/dev/mapper/${vg_name//-/--}-${lv//-/--}"
      if [ -e "$dm_name" ]; then
        lv_path="$dm_name"
      fi
    fi
    fstype=$(detect_fstype "$lv_path")
  if [ -z "$fstype" ] || [ "$fstype" = "swap" ]; then
    if [ "$fstype" = "swap" ]; then
      warn "Skipping swap LV: $lv_path"
      continue
    fi
    warn "Attempting mount on LV with unknown filesystem: $lv_path"
  fi
    mp_subdir="$(sanitize_name "$archive")/$(sanitize_name "$lv")"
    mount_point="${MOUNT_ROOT}/${mp_subdir}"
    log "Mounting LV $lv_path -> $mount_point"
    if mount_lv "$lv_path" "$mount_point"; then
      mounted_paths+=("$mount_point")
    else
      warn "Mount failed for $lv_path"
      rmdir "$mount_point" 2>/dev/null || true
    fi
  done < <(/sbin/lvm lvs --noheadings --separator '|' -o lv_name,lv_path,lv_attr --config "$lvm_cfg" --nolocking "$vg_name" | awk '{$1=$1};1')
}

mounted_paths=()
mapped_devs=()
imported_vgs=()
cow_loops=()
cow_dms=()
cow_files=()

cleanup_on_error() {
  local code=$?
  if [ "$CLEANING_UP" -eq 1 ]; then
    return
  fi
  CLEANING_UP=1
  if [ $code -eq 0 ]; then
    return
  fi
  warn "Cleaning up after error"
  for mp in "${mounted_paths[@]:-}"; do
    umount "$mp" 2>/dev/null || true
  done
  for vg in "${imported_vgs[@]:-}"; do
    /sbin/lvm vgchange -an --nolocking "$vg" 2>/dev/null || true
  done
  for dm in "${cow_dms[@]:-}"; do
    /sbin/dmsetup remove "$dm" 2>/dev/null || true
  done
  for loopdev in "${cow_loops[@]:-}"; do
    losetup -d "$loopdev" 2>/dev/null || true
  done
  for f in "${cow_files[@]:-}"; do
    rm -f "$f" 2>/dev/null || true
  done
  for dev in "${mapped_devs[@]:-}"; do
    proxmox-backup-client unmap "$dev" >/dev/null 2>&1 || true
  done
}
trap cleanup_on_error ERR

if [ ${#ARCHIVES[@]} -eq 0 ]; then
  if ! mapfile -t ARCHIVES < <(list_archives); then
    err "No .img archives found for snapshot: $SNAPSHOT"
    exit 1
  fi
  if [ ${#ARCHIVES[@]} -eq 0 ]; then
    err "No .img archives found for snapshot: $SNAPSHOT"
    exit 1
  fi
fi

log "Found ${#ARCHIVES[@]} archive(s)"

for archive in "${ARCHIVES[@]}"; do
  log "Mapping archive: $archive"
  dev=$(map_archive "$archive")
  mapped_devs+=("$dev")

  if blkid -o value -s TYPE "$dev" 2>/dev/null | grep -qx "LVM2_member"; then
    handle_lvm_pv "$dev" "$archive"
  else
    mapdir="$(sanitize_name "$archive")"
    root_target="${MOUNT_ROOT}/${mapdir}"

    mapfile -t parts < <(lsblk -rno NAME,TYPE "$dev" | awk '$2=="part"{print $1}')
    if [ ${#parts[@]} -gt 0 ]; then
      for p in "${parts[@]}"; do
        part_dev="/dev/${p}"
        part_name="$(sanitize_name "$p")"
        mount_point="${root_target}/${part_name}"
        if blkid -o value -s TYPE "$part_dev" 2>/dev/null | grep -qx "LVM2_member"; then
          handle_lvm_pv "$part_dev" "$archive"
          continue
        fi
        fstype=$(lsblk -no FSTYPE "$part_dev" 2>/dev/null | head -n1 || true)
        if [ -z "$fstype" ] || [ "$fstype" = "swap" ]; then
          warn "Skipping partition without mountable filesystem: $part_dev (fstype=${fstype:-none})"
          continue
        fi
        log "Mounting partition $part_dev -> $mount_point"
        mount_lv "$part_dev" "$mount_point"
        mounted_paths+=("$mount_point")
      done
    else
      fstype=$(lsblk -no FSTYPE "$dev" 2>/dev/null | head -n1 || true)
      if [ -z "$fstype" ] || [ "$fstype" = "swap" ]; then
        warn "Skipping device without mountable filesystem: $dev (fstype=${fstype:-none})"
      else
        log "Mounting device $dev -> $root_target"
        mount_lv "$dev" "$root_target"
        mounted_paths+=("$root_target")
      fi
    fi
  fi
done

if [ ${#mounted_paths[@]} -eq 0 ]; then
  err "No mounts completed."
  exit 1
fi

log "Mount complete. Mounted paths:"
for mp in "${mounted_paths[@]}"; do
  printf '  %s\n' "$mp"
done
if [ ${#cow_dms[@]} -gt 0 ]; then
  log "COW snapshots active:"
  for dm in "${cow_dms[@]}"; do
    printf '  /dev/mapper/%s\n' "$dm"
  done
fi

cat <<'NOTE'

Cleanup:
  ./mount-pbs-snapshot.sh --cleanup /mnt/pbs-snap
NOTE
