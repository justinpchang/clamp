# clamp

## Committing and pushing

This is a personal repo (`justinpchang/clamp`). Two GitHub accounts are configured on this machine:

- `jpc-owner` — work account (default, keep active outside of clamp work)
- `justinpchang` — personal account, owns this repo

Before pushing to this repo, switch gh auth and author the commit under the personal identity. Don't modify global git config — pass identity per-command with `-c`:

```bash
gh auth switch --user justinpchang

git -c user.email=justin.p.chang@gmail.com -c user.name="Justin Chang" \
    commit -m "..."
git push

gh auth switch --user jpc-owner   # always switch back when done
```
