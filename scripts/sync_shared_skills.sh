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
#   - Hooks propagate only commits on CANONICAL_BRANCH (dev); --push syncs from any branch.
#   - Mirror commits happen only when the mirror checkout is safe to write:
#     on a branch, no merge/rebase/cherry-pick/revert in progress, clean index,
#     and no uncommitted changes in shared paths.
#   - SYNC_SHARED_SKILLS_DISABLE=1 disables automatic hook propagation.
#   - SIBLING_REPO or --with overrides the default sibling repo path.
#   - Hooks are enabled per clone with: git config core.hooksPath scripts/hooks
#   - Nothing is ever pushed by this script.
#
set -euo pipefail

# Intrinsic definition of the shared repository names, canonical working branch, synced paths, and commit subject.
CANONICAL_REPO="kveld-morphe-patches"
MIRROR_REPO="kveld-extra-morphe-patches"
CANONICAL_BRANCH="dev"
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
SYNC_SUBJECT="chore(sync): mirror shared skills from $CANONICAL_REPO"

# Every path the script passes to git is a literal file or directory name, never a glob.
# Clear other global pathspec modes because git rejects combining them with literal mode.
unset GIT_GLOB_PATHSPECS GIT_NOGLOB_PATHSPECS GIT_ICASE_PATHSPECS
export GIT_LITERAL_PATHSPECS=1

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
APPLIED_PATHS=()
CONFLICTING_PATHS=()
UNSAFE_PATHS=()
STAGED_SHARED_PATHS=()
declare -A STAGED_BLOBS=()
OFFENDING_PATHS=()

usage() {
    cat <<'EOF' >&2
Usage: scripts/sync_shared_skills.sh --check | --push | --hook | --guard [--with <other-repo-path>]
EOF
    exit 2
}

# Fail with exit 1, except in hook mode, which must never fail the calling git command.
exit_failure() {
    if [ "$MODE" = "hook" ]; then
        exit 0
    fi
    exit 1
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

load_tree() {
    local root="$1"
    local -n blob_map="$2"
    local -n mode_map="$3"
    blob_map=()
    mode_map=()
    local rec meta path mode type sha
    while IFS= read -r -d '' rec; do
        meta="${rec%%$'\t'*}"
        path="${rec#*$'\t'}"
        [ -n "${path:-}" ] || continue
        read -r mode type sha <<< "$meta"
        blob_map["$path"]="$sha"
        mode_map["$path"]="$mode"
    done < <(git -C "$root" ls-tree -r -z --full-tree HEAD -- "${SHARED_PATHS[@]}" 2>/dev/null || true)
}

assert_canon_tree() {
    if [ "${#CANON_BLOB[@]}" -eq 0 ]; then
        echo "[SYNC] ERROR: canonical tree for shared paths is empty or unreadable in $canon_root; nothing written."
        exit_failure
    fi
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
        printf '%s\0' "${!seen[@]}" | sort -z
    fi
}

compute_changed_paths() {
    CHANGED_PATHS=()
    local p c_sha m_sha c_mode m_mode
    while IFS= read -r -d '' p; do
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
        git -C "$mirror_root" diff -z --name-only HEAD -- "${SHARED_PATHS[@]}" 2>/dev/null || true
        git -C "$mirror_root" ls-files -z --others --exclude-standard -- "${SHARED_PATHS[@]}" 2>/dev/null || true
    } | sort -zu
}

print_drift_paths() {
    local p
    if [ "${#CHANGED_PATHS[@]}" -gt 0 ]; then
        for p in "${CHANGED_PATHS[@]}"; do
            echo "[SYNC] drift: $p"
        done
    fi
}

print_mirror_warnings() {
    local p
    while IFS= read -r -d '' p; do
        [ -n "$p" ] || continue
        echo "[SYNC] WARN: uncommitted change in mirror: $p"
    done < <(get_mirror_uncommitted_paths)
}

run_check() {
    if [ ! -e "$other_root/.git" ]; then
        echo "[SYNC] Other repository not found: $other_root (use --with or SIBLING_REPO)"
        exit 2
    fi
    load_tree "$canon_root" CANON_BLOB CANON_MODE
    assert_canon_tree
    load_tree "$mirror_root" MIRROR_BLOB MIRROR_MODE
    compute_changed_paths
    print_drift_paths
    print_mirror_warnings
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

is_safe_tree_path() {
    local p="$1"
    case "$p" in
        /*|"") return 1 ;;
    esac
    local parts=() part
    IFS=/ read -r -d "" -a parts < <(printf "%s" "$p") || true
    for part in "${parts[@]}"; do
        case "$part" in
            ""|"."|".."|".git") return 1 ;;
        esac
    done
    return 0
}

has_symlink_component() {
    local p="$1"
    local parts=() part prefix="" target
    IFS=/ read -r -d "" -a parts < <(printf "%s" "$p") || true
    for part in "${parts[@]}"; do
        prefix="${prefix:+$prefix/}$part"
        target="$mirror_root/$prefix"
        if [ -L "$target" ]; then
            return 0
        fi
        if [ ! -e "$target" ]; then
            return 1
        fi
    done
    return 1
}

# Keep all writes inside the mirror tree and reject symlinks or invalid paths.
find_unsafe_paths() {
    UNSAFE_PATHS=()
    local p
    for p in "${CHANGED_PATHS[@]}"; do
        if ! is_safe_tree_path "$p"; then
            UNSAFE_PATHS+=("$p")
            continue
        fi
        if [ "${CANON_MODE[$p]:-}" = "120000" ] || [ "${MIRROR_MODE[$p]:-}" = "120000" ]; then
            UNSAFE_PATHS+=("$p")
            continue
        fi
        if has_symlink_component "$p"; then
            UNSAFE_PATHS+=("$p")
        fi
    done
}

is_mirror_path_occupied() {
    local p="$1"
    [ -L "$mirror_root/$p" ] || { [ -e "$mirror_root/$p" ] && [ ! -d "$mirror_root/$p" ]; }
}

find_uncommitted_conflicts() {
    declare -A uncommitted=()
    local p
    while IFS= read -r -d '' p; do
        [ -n "$p" ] || continue
        uncommitted["$p"]=1
    done < <(get_mirror_uncommitted_paths)

    CONFLICTING_PATHS=()
    for p in "${CHANGED_PATHS[@]}"; do
        if [ -n "${uncommitted[$p]:-}" ]; then
            CONFLICTING_PATHS+=("$p")
        elif [ -z "${MIRROR_BLOB[$p]:-}" ] && is_mirror_path_occupied "$p"; then
            CONFLICTING_PATHS+=("$p")
        fi
    done
}

apply_changed_path() {
    local p="$1"
    APPLIED_PATHS+=("$p")
    local sha="${CANON_BLOB[$p]:-}"
    local mode="${CANON_MODE[$p]:-}"
    local target="$mirror_root/$p"
    if [ -z "$sha" ]; then
        git -C "$mirror_root" rm -q -- "$p" || return 1
        return 0
    fi
    mkdir -p "$(dirname "$target")" || return 1
    git -C "$canon_root" cat-file blob "$sha" > "$target" || return 1
    if [ "$mode" = "100755" ]; then
        chmod 755 "$target" || return 1
    else
        chmod 644 "$target" || return 1
    fi
    # -f: the path is tracked in canonical, so the mirror must track it even if its .gitignore matches.
    git -C "$mirror_root" add -f -- "$p" || return 1
    return 0
}

apply_all_changed_paths() {
    local p
    for p in "${CHANGED_PATHS[@]}"; do
        if [ -z "${CANON_BLOB[$p]:-}" ]; then
            apply_changed_path "$p" || return 1
        fi
    done
    for p in "${CHANGED_PATHS[@]}"; do
        if [ -n "${CANON_BLOB[$p]:-}" ]; then
            apply_changed_path "$p" || return 1
        fi
    done
    return 0
}

rollback_mirror() {
    local p
    for p in "${APPLIED_PATHS[@]}"; do
        if [ -n "${MIRROR_BLOB[$p]:-}" ]; then
            git -C "$mirror_root" restore --source=HEAD --staged --worktree -- "$p" || true
        else
            git -C "$mirror_root" rm -q --cached --ignore-unmatch -- "$p" || true
            rm -f -- "$mirror_root/$p" || true
        fi
    done
}

# Print the applied paths that still differ from mirror HEAD after a rollback.
find_unrestored_paths() {
    local p
    if [ "${#APPLIED_PATHS[@]}" -gt 0 ]; then
        for p in "${APPLIED_PATHS[@]}"; do
            if [ -n "${MIRROR_BLOB[$p]:-}" ]; then
                git -C "$mirror_root" diff --quiet HEAD -- "$p" 2>/dev/null || echo "$p"
            elif [ -e "$mirror_root/$p" ] || [ -L "$mirror_root/$p" ] || git -C "$mirror_root" ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
                echo "$p"
            fi
        done
    fi
}

# Roll back the applied paths and report whether the mirror is really restored.
rollback_and_report() {
    local reason="$1"
    local left
    rollback_mirror
    left="$(find_unrestored_paths | tr '\n' ' ')"
    if [ -n "$left" ]; then
        echo "[SYNC] ERROR: $reason; mirror NOT fully restored, nothing committed. Inspect: ${left% }"
    else
        echo "[SYNC] ERROR: $reason; mirror restored, nothing committed."
    fi
    exit_failure
}

commit_mirror() {
    local canon_sha mirror_sha count
    canon_sha="$(git -C "$canon_root" rev-parse --short HEAD)"
    count="${#CHANGED_PATHS[@]}"
    # SIBLING_REPO is role-relative and must not reach the mirror's hooks.
    if ! env -u SIBLING_REPO git -C "$mirror_root" commit -q -m "$SYNC_SUBJECT" -m "Source: $CANONICAL_REPO $canon_sha"; then
        rollback_and_report "mirror commit failed"
    fi
    mirror_sha="$(git -C "$mirror_root" rev-parse --short HEAD)"
    echo "[SYNC] Mirrored $count path(s) into $MIRROR_REPO as $mirror_sha; push it with the normal workflow."
    exit 0
}

refuse_unsafe_paths() {
    find_unsafe_paths
    if [ "${#UNSAFE_PATHS[@]}" -gt 0 ]; then
        echo "[SYNC] ERROR: refusing unsafe shared paths (symlink or invalid path): ${UNSAFE_PATHS[*]}; nothing written."
        exit_failure
    fi
}

skip_on_uncommitted_conflicts() {
    find_uncommitted_conflicts
    if [ "${#CONFLICTING_PATHS[@]}" -gt 0 ]; then
        echo "[SYNC] Skipped: uncommitted mirror changes in ${CONFLICTING_PATHS[*]}."
        exit 0
    fi
}

apply_or_rollback() {
    if ! apply_all_changed_paths; then
        rollback_and_report "applying shared files failed"
    fi
}

run_push() {
    if [ "$role" != "canonical" ]; then
        echo "[SYNC] --push must run in $CANONICAL_REPO."
        exit 2
    fi
    check_push_preconditions
    load_tree "$canon_root" CANON_BLOB CANON_MODE
    assert_canon_tree
    load_tree "$mirror_root" MIRROR_BLOB MIRROR_MODE
    compute_changed_paths
    if [ "${#CHANGED_PATHS[@]}" -eq 0 ]; then
        echo "[SYNC] Mirror already in sync."
        exit 0
    fi
    refuse_unsafe_paths
    skip_on_uncommitted_conflicts
    apply_or_rollback
    commit_mirror
}

# Hooks propagate only commits on CANONICAL_BRANCH; --push still syncs from any branch.
skip_unless_canonical_branch() {
    local branch
    branch="$(git -C "$canon_root" symbolic-ref --short -q HEAD || true)"
    if [ "$branch" != "$CANONICAL_BRANCH" ]; then
        echo "[SYNC] Skipped: canonical checkout is on ${branch:-a detached HEAD}, not $CANONICAL_BRANCH; run scripts/sync_shared_skills.sh --push to sync it manually."
        exit 0
    fi
}

run_hook() {
    if [ "$role" = "mirror" ] || [ "$is_linked_worktree" -eq 1 ] || [ "${SYNC_SHARED_SKILLS_DISABLE:-}" = "1" ]; then
        exit 0
    fi
    skip_unless_canonical_branch
    run_push
    exit 0
}

find_staged_shared_paths() {
    STAGED_SHARED_PATHS=()
    local p
    while IFS= read -r -d '' p; do
        [ -n "$p" ] || continue
        STAGED_SHARED_PATHS+=("$p")
    done < <(git diff -z --cached --name-only --no-renames -- "${SHARED_PATHS[@]}")
}

record_staged_blobs() {
    STAGED_BLOBS=()
    local p
    if [ "${#STAGED_SHARED_PATHS[@]}" -gt 0 ]; then
        for p in "${STAGED_SHARED_PATHS[@]}"; do
            STAGED_BLOBS["$p"]="$(git rev-parse -q --verify ":$p" 2>/dev/null || true)"
        done
    fi
}

# Blob id of a canonical file at HEAD; empty when the path is missing or now a directory.
canonical_blob_at() {
    local sha
    sha="$(git -C "$canon_root" rev-parse -q --verify "HEAD:$1" 2>/dev/null || true)"
    if [ -n "$sha" ] && [ "$(git -C "$canon_root" cat-file -t "$sha" 2>/dev/null || true)" = "blob" ]; then
        echo "$sha"
    fi
}

find_offending_paths() {
    OFFENDING_PATHS=()
    local p staged_blob canon_blob
    if [ "${#STAGED_SHARED_PATHS[@]}" -gt 0 ]; then
        for p in "${STAGED_SHARED_PATHS[@]}"; do
            staged_blob="${STAGED_BLOBS[$p]:-}"
            canon_blob="$(canonical_blob_at "$p")"
            if [ "$staged_blob" != "$canon_blob" ]; then
                OFFENDING_PATHS+=("$p")
            fi
        done
    fi
}

report_offending_paths() {
    local p
    echo "[SYNC] BLOCKED: these files are mirrored from $CANONICAL_REPO; edit them there and commit, the mirror updates itself:"
    if [ "${#OFFENDING_PATHS[@]}" -gt 0 ]; then
        for p in "${OFFENDING_PATHS[@]}"; do
            echo "  $p"
        done
    fi
    echo "[SYNC] Bypass only if intended: git commit --no-verify"
    exit 1
}

run_guard() {
    if [ "$role" = "canonical" ]; then
        exit 0
    fi
    find_staged_shared_paths
    if [ "${#STAGED_SHARED_PATHS[@]}" -eq 0 ]; then
        exit 0
    fi
    record_staged_blobs
    unset_git_env
    if [ ! -e "$canon_root/.git" ]; then
        echo "[SYNC] WARN: $CANONICAL_REPO not found; cannot verify shared files."
        exit 0
    fi
    find_offending_paths
    if [ "${#OFFENDING_PATHS[@]}" -gt 0 ]; then
        report_offending_paths
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
