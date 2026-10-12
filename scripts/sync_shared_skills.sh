#!/usr/bin/env bash
# sync_shared_skills.sh - keep canonical shared skills byte-identical across sibling repos.
#
# Purpose:
#   kveld-morphe-patches is the single source of truth for shared agent skills and
#   sync tooling. Edit shared skills only in kveld-morphe-patches.
#
# Roles:
#   - canonical: kveld-morphe-patches (source of truth).
#   - mirror:    kveld-extra-morphe-patches (mirrors canonical HEAD).
#
# Modes:
#   --check: Check for drift between canonical HEAD and mirror HEAD. Also warns
#            if uncommitted changes exist in mirror shared files.
#   --push:  Propagate canonical HEAD into mirror working tree and commit. Must be
#            run from the canonical repository.
#   --hook:  Invoked by post-commit and post-merge hooks. Propagates changes to
#            mirror if safe; always exits 0.
#   --guard: Invoked by pre-commit hook in mirror repo. Blocks direct commits to
#            mirrored files unless bypassed with --no-verify.
#
# Safety and Invariants:
#   - Hooks skip linked worktrees: task branches never propagate until merged
#     into the main checkout.
#   - Mirror commits happen only when the mirror checkout is safe to write:
#     on a branch, no merge/rebase/cherry-pick/revert in progress, clean index,
#     and no uncommitted changes in shared paths.
#   - SYNC_SHARED_SKILLS_DISABLE=1 disables automatic hook propagation.
#   - SIBLING_REPO or --with overrides the default sibling repo path.
#   - Hooks are enabled per clone with: git config core.hooksPath scripts/hooks
#   - Nothing is ever pushed by this script.
#
set -euo pipefail

# Intrinsic definition of the shared repository names, synced paths, and commit subject.
CANONICAL_REPO="kveld-morphe-patches"
MIRROR_REPO="kveld-extra-morphe-patches"
SHARED_PATHS=(
  .agents/skills/morphe-patcher
  .agents/skills/smali-bytecode-hooks
  .agents/skills/native-binary-patching
  .agents/skills/telemetry-blocking
  .agents/skills/new-telemetry-app
  scripts/sync_shared_skills.sh
  scripts/hooks/post-commit
  scripts/hooks/post-merge
  scripts/hooks/pre-commit
)
SYNC_SUBJECT="chore(sync): mirror shared skills from kveld-morphe-patches"

MODE=""
OTHER_REPO_ARG=""
main_root=""
other_root=""
canon_root=""
mirror_root=""
role=""
other_name=""
is_linked_worktree=0

declare -A CANON_BLOB=()
declare -A CANON_MODE=()
declare -A MIRROR_BLOB=()
declare -A MIRROR_MODE=()
CHANGED_PATHS=()
CONFLICTING_PATHS=()
STAGED_SHARED_PATHS=()

usage() {
    cat <<'EOF' >&2
Usage: scripts/sync_shared_skills.sh --check | --push | --hook | --guard [--with <other-repo-path>]
EOF
    exit 2
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --check|--push|--hook|--guard)
                [ -z "$MODE" ] || usage
                MODE="${1#--}"
                shift
                ;;
            --with)
                [ $# -ge 2 ] || usage
                OTHER_REPO_ARG="$2"
                shift 2
                ;;
            *)
                usage
                ;;
        esac
    done
    [ -n "$MODE" ] || usage
}

resolve_repo_name() {
    local root="$1"
    local name origin_url origin_name
    name="$(basename "$root")"
    if [ "$name" = "$CANONICAL_REPO" ] || [ "$name" = "$MIRROR_REPO" ]; then
        echo "$name"
        return 0
    fi
    origin_url="$(git remote get-url origin 2>/dev/null || true)"
    origin_name="$(basename "$origin_url" .git)"
    if [ "$origin_name" = "$CANONICAL_REPO" ] || [ "$origin_name" = "$MIRROR_REPO" ]; then
        echo "$origin_name"
        return 0
    fi
    echo "$name"
}

handle_unknown_repo() {
    local name="$1"
    if [ "$MODE" = "hook" ] || [ "$MODE" = "guard" ]; then
        exit 0
    fi
    echo "[SYNC] Unknown repository: $name"
    exit 2
}

assign_repo_roles() {
    local name="$1"
    local default_other
    if [ "$name" = "$CANONICAL_REPO" ]; then
        role="canonical"
        other_name="$MIRROR_REPO"
        canon_root="$main_root"
        default_other="$(dirname "$main_root")/$other_name"
        mirror_root="${OTHER_REPO_ARG:-${SIBLING_REPO:-$default_other}}"
        other_root="$mirror_root"
        return 0
    fi
    role="mirror"
    other_name="$CANONICAL_REPO"
    default_other="$(dirname "$main_root")/$other_name"
    canon_root="${OTHER_REPO_ARG:-${SIBLING_REPO:-$default_other}}"
    mirror_root="$main_root"
    other_root="$canon_root"
}

resolve_identity() {
    local common_dir git_dir name
    common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
    main_root="$(dirname "$common_dir")"
    git_dir="$(git rev-parse --path-format=absolute --git-dir)"

    is_linked_worktree=0
    if [ "$git_dir" != "$common_dir" ]; then
        is_linked_worktree=1
    fi

    name="$(resolve_repo_name "$main_root")"
    if [ "$name" != "$CANONICAL_REPO" ] && [ "$name" != "$MIRROR_REPO" ]; then
        handle_unknown_repo "$name"
    fi

    assign_repo_roles "$name"
}

unset_git_env() {
    unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
}

load_canon_tree() {
    CANON_BLOB=()
    CANON_MODE=()
    local meta path mode type sha
    while IFS=$'\t' read -r meta path; do
        [ -n "${path:-}" ] || continue
        read -r mode type sha <<< "$meta"
        CANON_BLOB["$path"]="$sha"
        CANON_MODE["$path"]="$mode"
    done < <(git -C "$canon_root" ls-tree -r --full-tree HEAD -- "${SHARED_PATHS[@]}" 2>/dev/null || true)
}

assert_canon_tree() {
    if [ "${#CANON_BLOB[@]}" -eq 0 ]; then
        echo "[SYNC] ERROR: canonical tree for shared paths is empty or unreadable in $canon_root; nothing written."
        if [ "$MODE" = "hook" ]; then
            exit 0
        fi
        exit 1
    fi
}

load_mirror_tree() {
    MIRROR_BLOB=()
    MIRROR_MODE=()
    local meta path mode type sha
    while IFS=$'\t' read -r meta path; do
        [ -n "${path:-}" ] || continue
        read -r mode type sha <<< "$meta"
        MIRROR_BLOB["$path"]="$sha"
        MIRROR_MODE["$path"]="$mode"
    done < <(git -C "$mirror_root" ls-tree -r --full-tree HEAD -- "${SHARED_PATHS[@]}" 2>/dev/null || true)
}

get_all_paths() {
    local p
    declare -A seen=()
    if [ "${#CANON_BLOB[@]}" -gt 0 ]; then
        for p in "${!CANON_BLOB[@]}"; do
            seen["$p"]=1
        done
    fi
    if [ "${#MIRROR_BLOB[@]}" -gt 0 ]; then
        for p in "${!MIRROR_BLOB[@]}"; do
            seen["$p"]=1
        done
    fi
    if [ "${#seen[@]}" -gt 0 ]; then
        printf '%s\n' "${!seen[@]}" | sort
    fi
}

compute_changed_paths() {
    CHANGED_PATHS=()
    local p c_sha m_sha c_mode m_mode
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        c_sha="${CANON_BLOB[$p]:-}"
        m_sha="${MIRROR_BLOB[$p]:-}"
        c_mode="${CANON_MODE[$p]:-}"
        m_mode="${MIRROR_MODE[$p]:-}"
        if [ "$c_sha" != "$m_sha" ] || [ "$c_mode" != "$m_mode" ]; then
            CHANGED_PATHS+=("$p")
        fi
    done < <(get_all_paths)
}

get_mirror_uncommitted_paths() {
    {
        git -C "$mirror_root" diff --name-only HEAD -- "${SHARED_PATHS[@]}" 2>/dev/null || true
        git -C "$mirror_root" ls-files --others --exclude-standard -- "${SHARED_PATHS[@]}" 2>/dev/null || true
    } | sort -u
}

run_check() {
    if [ ! -e "$other_root/.git" ]; then
        echo "[SYNC] Other repository not found: $other_root (use --with or SIBLING_REPO)"
        exit 2
    fi
    load_canon_tree
    assert_canon_tree
    load_mirror_tree
    compute_changed_paths
    local p
    if [ "${#CHANGED_PATHS[@]}" -gt 0 ]; then
        for p in "${CHANGED_PATHS[@]}"; do
            echo "[SYNC] drift: $p"
        done
    fi
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        echo "[SYNC] WARN: uncommitted change in mirror: $p"
    done < <(get_mirror_uncommitted_paths)
    if [ "${#CHANGED_PATHS[@]}" -gt 0 ]; then
        echo "[SYNC] FAIL: shared files drifted."
        exit 1
    fi
    echo "[SYNC] PASS: shared files identical."
    exit 0
}

check_mirror_operation() {
    local ops=(MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply)
    local op p path
    for op in "${ops[@]}"; do
        p="$(git -C "$mirror_root" rev-parse --git-path "$op" 2>/dev/null || true)"
        [ -n "$p" ] || continue
        case "$p" in
            /*) path="$p" ;;
            *) path="$mirror_root/$p" ;;
        esac
        if [ -e "$path" ]; then
            echo "$op"
            return 0
        fi
    done
    return 1
}

check_push_preconditions() {
    if [ ! -e "$mirror_root/.git" ]; then
        echo "[SYNC] Skipped: mirror repository not found."
        exit 0
    fi
    if ! git -C "$mirror_root" symbolic-ref -q HEAD >/dev/null; then
        echo "[SYNC] Skipped: mirror HEAD is not on a branch."
        exit 0
    fi
    local op
    if op="$(check_mirror_operation)"; then
        echo "[SYNC] Skipped: operation in progress in mirror: $op"
        exit 0
    fi
    if ! git -C "$mirror_root" diff --cached --quiet; then
        echo "[SYNC] Skipped: mirror index has staged changes."
        exit 0
    fi
}

find_uncommitted_conflicts() {
    declare -A uncommitted=()
    local p
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        uncommitted["$p"]=1
    done < <(get_mirror_uncommitted_paths)

    CONFLICTING_PATHS=()
    for p in "${CHANGED_PATHS[@]}"; do
        if [ -n "${uncommitted[$p]:-}" ]; then
            CONFLICTING_PATHS+=("$p")
        fi
    done
}

apply_changed_path() {
    local p="$1"
    local sha="${CANON_BLOB[$p]:-}"
    local mode="${CANON_MODE[$p]:-}"
    local target="$mirror_root/$p"
    if [ -n "$sha" ]; then
        mkdir -p "$(dirname "$target")"
        git -C "$canon_root" cat-file blob "$sha" > "$target"
        if [ "$mode" = "100755" ]; then
            chmod 755 "$target"
        else
            chmod 644 "$target"
        fi
        git -C "$mirror_root" add -- "$p"
        return 0
    fi
    git -C "$mirror_root" rm -q -- "$p"
}

commit_mirror() {
    local canon_sha mirror_sha count
    canon_sha="$(git -C "$canon_root" rev-parse --short HEAD)"
    count="${#CHANGED_PATHS[@]}"
    # SIBLING_REPO is role-relative and must not reach the mirror's hooks.
    if ! env -u SIBLING_REPO git -C "$mirror_root" commit -q -m "$SYNC_SUBJECT" -m "Source: $CANONICAL_REPO $canon_sha"; then
        echo "[SYNC] ERROR: mirror commit failed; changes left staged in $mirror_root."
        if [ "$MODE" = "hook" ]; then
            exit 0
        fi
        exit 1
    fi
    mirror_sha="$(git -C "$mirror_root" rev-parse --short HEAD)"
    echo "[SYNC] Mirrored $count path(s) into $MIRROR_REPO as $mirror_sha; push it with the normal workflow."
    exit 0
}

run_push() {
    if [ "$role" != "canonical" ]; then
        echo "[SYNC] --push must run in $CANONICAL_REPO."
        exit 2
    fi
    check_push_preconditions
    load_canon_tree
    assert_canon_tree
    load_mirror_tree
    compute_changed_paths
    if [ "${#CHANGED_PATHS[@]}" -eq 0 ]; then
        echo "[SYNC] Mirror already in sync."
        exit 0
    fi
    find_uncommitted_conflicts
    if [ "${#CONFLICTING_PATHS[@]}" -gt 0 ]; then
        echo "[SYNC] Skipped: uncommitted mirror changes in ${CONFLICTING_PATHS[*]}."
        exit 0
    fi
    local p
    for p in "${CHANGED_PATHS[@]}"; do
        apply_changed_path "$p"
    done
    commit_mirror
}

run_hook() {
    if [ "$role" = "mirror" ] || [ "$is_linked_worktree" -eq 1 ] || [ "${SYNC_SHARED_SKILLS_DISABLE:-}" = "1" ]; then
        exit 0
    fi
    run_push
    exit 0
}

find_staged_shared_paths() {
    STAGED_SHARED_PATHS=()
    local p
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        STAGED_SHARED_PATHS+=("$p")
    done < <(git diff --cached --name-only --no-renames -- "${SHARED_PATHS[@]}")
}

run_guard() {
    if [ "$role" = "canonical" ]; then
        exit 0
    fi
    find_staged_shared_paths
    if [ "${#STAGED_SHARED_PATHS[@]}" -eq 0 ]; then
        exit 0
    fi
    declare -A staged_blobs=()
    local p
    for p in "${STAGED_SHARED_PATHS[@]}"; do
        staged_blobs["$p"]="$(git rev-parse -q --verify ":$p" 2>/dev/null || true)"
    done

    unset_git_env

    if [ ! -e "$canon_root/.git" ]; then
        echo "[SYNC] WARN: $CANONICAL_REPO not found; cannot verify shared files."
        exit 0
    fi

    local offending=()
    local staged_blob canon_blob
    for p in "${STAGED_SHARED_PATHS[@]}"; do
        staged_blob="${staged_blobs[$p]:-}"
        canon_blob="$(git -C "$canon_root" rev-parse -q --verify "HEAD:$p" 2>/dev/null || true)"
        if [ "$staged_blob" != "$canon_blob" ]; then
            offending+=("$p")
        fi
    done

    if [ "${#offending[@]}" -gt 0 ]; then
        echo "[SYNC] BLOCKED: these files are mirrored from $CANONICAL_REPO; edit them there and commit, the mirror updates itself:"
        for p in "${offending[@]}"; do
            echo "  $p"
        done
        echo "[SYNC] Bypass only if intended: git commit --no-verify"
        exit 1
    fi
    exit 0
}

main() {
    parse_args "$@"
    resolve_identity
    if [ "$MODE" != "guard" ]; then
        unset_git_env
    fi
    case "$MODE" in
        check) run_check ;;
        push)  run_push ;;
        hook)  run_hook ;;
        guard) run_guard ;;
    esac
}

main "$@"
