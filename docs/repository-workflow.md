# Repository maintenance

This project is a public source fork of `LoneGazebo/Community-Patch-DLL`, hosted at <https://github.com/ruskyandrei/Civ5StackMod>. Packaged stacking releases are not configured yet. Upstream licensing and credits remain in place.

## Branches and remotes

| Name | Purpose |
|---|---|
| `origin` | Our fork: `https://github.com/ruskyandrei/Civ5StackMod.git` |
| `upstream` | Official VP: `https://github.com/LoneGazebo/Community-Patch-DLL.git` |
| `b-stack-prototype` | Default development branch containing the stacking changes |
| `master` on the fork | Unmodified branch inherited when the fork was created; not the stacking branch |
| `Release-5.4.6` | Current upstream base; peeled commit `dcb33a654cd9e8efb038a0733b4025e19cbcd8ba` |

The local checkout retains full commit ancestry. Large historical upstream file contents may be downloaded on demand through Git's `blob:none` partial-clone filter; this does not truncate commit history or change how merges work. Fetching upstream does not automatically update the installed game or merge new gameplay code.

## Another development machine

```powershell
git clone --filter=blob:none --branch b-stack-prototype https://github.com/ruskyandrei/Civ5StackMod.git
cd Civ5StackMod
git remote add upstream https://github.com/LoneGazebo/Community-Patch-DLL.git
git config remote.pushDefault origin
git config push.default simple
```

The repository contains source and selected development helpers. Compiler/SDK downloads, local build outputs and test evidence are not included. Read `work/BUILD-LOCAL.md` before building: several scripts still contain paths for the original development PC. Do not run deployment or restore scripts on another machine without reviewing those paths and prerequisites.

## Save work

Review `git status` and `git diff`, stage the intended source and documentation files, then commit and push the development branch:

```powershell
git commit -m "Describe the completed change"
git push origin b-stack-prototype
```

Root and `work/.gitignore` rules exclude newly created files inside `work` by default. Existing tracked helpers and notes remain tracked. After checking that a new helper belongs in source control, add that specific file with `git add -f -- work/example.py`. Do not force-add the entire work directory: it contains compilers, backups, local builds, saves and raw diagnostic evidence. Preserve exact DLL/PDB build pairs locally for crash investigation until a separate artifact/release process is established.

## Merge a future VP release

1. Commit or otherwise preserve current edits and start from a clean development branch. Fetch upstream releases; do not pull or merge upstream development automatically:

   ```powershell
   git fetch --filter=blob:none --tags upstream
   git switch b-stack-prototype
   ```

2. Create a temporary branch such as `b-vp-5.x-update`. Merge the **chosen official release tag**, using `git merge --no-ff Release-<version>` after replacing the placeholder. Keep merge commits rather than rewriting already published stacking history.
3. Resolve both text conflicts and behavior changes, particularly tactical/military AI, combat, movement, placement, database configuration and EUI. Update staging/version checks and compatibility documentation deliberately; some local scripts currently pin VP 5.4.6.
4. Build with the validated native toolchain and run appropriate configuration, combat, movement, AI, UI and save/reload checks. Compare bounded saved-game replays and fresh games before accepting the upgrade. A clean Git merge alone is not evidence of gameplay compatibility.
5. Merge the validated update branch back into `b-stack-prototype` and push that branch to `origin`. Keep the official upstream tags unchanged. Creating player releases and choosing stacking release tags is separate work.

There is no need to merge upstream `master` or change the fork's inherited `master` just to back up stacking work. Shared ancestry enables ordinary Git merges from future VP tags.

## Automation

Inherited GitHub Actions are disabled on this fork for now. Their build/release assumptions have not been adapted to our validated native workflow. No new stacking release tags or packaged downloads are published by the initial source setup.
