"""
Git Branch Manager — Streamlit Page

Visual UI for comparing branches, viewing diffs, creating PRs, and cleaning up stale branches.
"""

import subprocess
from pathlib import Path

import streamlit as st


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _run(cmd: str, cwd: str | None = None) -> tuple[str, int]:
    """Run a shell command and return (stdout, returncode)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd or st.session_state.get("git_repo_path", "."),
    )
    return (result.stdout.strip() + "\n" + result.stderr.strip()).strip(), result.returncode


def _get_repo_path() -> str | None:
    """Return the repo path from session state, or None."""
    return st.session_state.get("git_repo_path")


def _is_git_repo(path: str) -> bool:
    _, rc = _run("git rev-parse --is-inside-work-tree", cwd=path)
    return rc == 0


def _get_branches(cwd: str) -> list[str]:
    out, _ = _run("git branch -a --format='%(refname:short)'", cwd=cwd)
    return [b.strip().strip("'") for b in out.splitlines() if b.strip()]


def _get_local_branches(cwd: str) -> list[str]:
    out, _ = _run("git branch --format='%(refname:short)'", cwd=cwd)
    return [b.strip().strip("'") for b in out.splitlines() if b.strip()]


def _get_default_branch(cwd: str) -> str:
    """Try to detect the default branch (main or master)."""
    out, rc = _run("git symbolic-ref refs/remotes/origin/HEAD --short 2>/dev/null", cwd=cwd)
    if rc == 0 and out:
        return out.replace("origin/", "")
    # Fallback: check if main or master exists
    branches = _get_local_branches(cwd)
    if "main" in branches:
        return "main"
    if "master" in branches:
        return "master"
    return branches[0] if branches else "main"


def _get_commit_log(base: str, head: str, cwd: str) -> str:
    out, _ = _run(f"git log {base}..{head} --oneline --no-decorate", cwd=cwd)
    return out


def _get_diff_stat(base: str, head: str, cwd: str) -> str:
    out, _ = _run(f"git diff {base}..{head} --stat", cwd=cwd)
    return out


def _get_diff(base: str, head: str, cwd: str) -> str:
    out, _ = _run(f"git diff {base}..{head}", cwd=cwd)
    return out


def _get_commit_count(base: str, head: str, cwd: str) -> int:
    out, _ = _run(f"git rev-list --count {base}..{head}", cwd=cwd)
    try:
        return int(out.strip())
    except ValueError:
        return 0


def _same_commit(a: str, b: str, cwd: str) -> bool:
    ha, _ = _run(f"git rev-parse {a}", cwd=cwd)
    hb, _ = _run(f"git rev-parse {b}", cwd=cwd)
    return ha.splitlines()[0] == hb.splitlines()[0]


# ------------------------------------------------------------------
# Page
# ------------------------------------------------------------------

def render(db=None, config=None):
    st.header("Git Branch Manager")
    st.caption("Compare branches, create PRs, or clean up stale branches")

    # --- Repo path selector ---
    default_path = str(Path.cwd())
    repo_path = st.text_input(
        "Repository path",
        value=st.session_state.get("git_repo_path", default_path),
        help="Absolute path to a local Git repository",
    )
    st.session_state["git_repo_path"] = repo_path

    if not Path(repo_path).is_dir():
        st.error("Directory does not exist.")
        return
    if not _is_git_repo(repo_path):
        st.error("Not a Git repository. Please enter a valid repo path.")
        return

    # Fetch latest remote info
    if st.button("Fetch from remote"):
        out, rc = _run("git fetch --all --prune", cwd=repo_path)
        if rc == 0:
            st.success("Fetched latest from remote.")
        else:
            st.warning(f"Fetch issue: {out}")

    st.divider()

    # --- Branch selection ---
    local_branches = _get_local_branches(repo_path)
    all_branches = _get_branches(repo_path)
    default_branch = _get_default_branch(repo_path)

    col1, col2 = st.columns(2)
    with col1:
        base = st.selectbox(
            "Base branch",
            local_branches,
            index=local_branches.index(default_branch) if default_branch in local_branches else 0,
        )
    with col2:
        other_branches = [b for b in local_branches if b != base]
        if not other_branches:
            st.info("No other local branches to compare.")
            return
        compare = st.selectbox("Compare branch", other_branches)

    st.divider()

    # --- Comparison ---
    ahead = _get_commit_count(base, compare, repo_path)
    behind = _get_commit_count(compare, base, repo_path)
    identical = _same_commit(base, compare, repo_path)

    # Status metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Commits ahead of base", ahead)
    m2.metric("Commits behind base", behind)
    m3.metric("Status", "Identical" if identical else "Diverged")

    if identical:
        st.warning(f"**{compare}** is identical to **{base}** — no new changes.")

        # Cleanup option
        st.subheader("Cleanup")
        st.write(f"Since `{compare}` has no unique changes, you can safely delete it.")

        col_del_local, col_del_remote = st.columns(2)
        with col_del_local:
            if st.button(f"Delete local branch `{compare}`", type="primary"):
                # Switch to base first
                _run(f"git checkout {base}", cwd=repo_path)
                out, rc = _run(f"git branch -d {compare}", cwd=repo_path)
                if rc == 0:
                    st.success(f"Deleted local branch `{compare}`.")
                    st.rerun()
                else:
                    st.error(f"Failed: {out}")
        with col_del_remote:
            if st.button(f"Delete remote branch `{compare}`"):
                out, rc = _run(f"git push origin --delete {compare}", cwd=repo_path)
                if rc == 0:
                    st.success(f"Deleted remote branch `{compare}`.")
                else:
                    st.warning(f"Could not delete remote: {out}")

    else:
        # Show diff details
        if ahead > 0:
            st.subheader(f"Commits on `{compare}` not on `{base}` ({ahead})")
            log = _get_commit_log(base, compare, repo_path)
            st.code(log, language="text")

            st.subheader("Diff summary")
            stat = _get_diff_stat(base, compare, repo_path)
            st.code(stat, language="text")

            with st.expander("Full diff", expanded=False):
                diff = _get_diff(base, compare, repo_path)
                st.code(diff[:50000], language="diff")

            # PR creation
            st.divider()
            st.subheader("Create Pull Request")
            pr_title = st.text_input("PR title", value=f"Merge {compare} into {base}")
            pr_body = st.text_area("PR description", value=f"Merging branch `{compare}` into `{base}`.\n\n**Changes:**\n{log}")

            if st.button("Create PR with `gh`", type="primary"):
                # Push branch first
                push_out, push_rc = _run(f"git push -u origin {compare}", cwd=repo_path)
                if push_rc != 0:
                    st.warning(f"Push output: {push_out}")

                cmd = f'gh pr create --base {base} --head {compare} --title "{pr_title}" --body "{pr_body}"'
                out, rc = _run(cmd, cwd=repo_path)
                if rc == 0:
                    st.success(f"PR created! {out}")
                    st.balloons()
                else:
                    st.error(f"Failed to create PR: {out}")

        if behind > 0:
            st.subheader(f"Commits on `{base}` not on `{compare}` ({behind})")
            log_behind = _get_commit_log(compare, base, repo_path)
            st.code(log_behind, language="text")

    # --- All branches overview ---
    st.divider()
    st.subheader("All Branches")

    branch_data = []
    for b in local_branches:
        if b == base:
            branch_data.append({"Branch": b, "vs Base": "— (this is base)", "Ahead": 0, "Behind": 0})
        else:
            a = _get_commit_count(base, b, repo_path)
            bh = _get_commit_count(b, base, repo_path)
            status = "Identical" if _same_commit(base, b, repo_path) else f"+{a} / -{bh}"
            branch_data.append({"Branch": b, "vs Base": status, "Ahead": a, "Behind": bh})

    st.dataframe(branch_data, use_container_width=True)
