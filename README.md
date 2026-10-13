# Ley Thiki MV — automatic Instagram posting

Posts one day of the anaemia series to @leythikimv every evening without anyone touching Instagram.

- `schedule.json` — every day's carousel (English slides, then Dhivehi), story images, caption and alt text.
  A day posts only if its number is in `approved_days` and `start_date` is set (Day 1 posts on `start_date`).
- `media/` — JPEG copies of the approved images. Instagram downloads them from this public repository.
- `publish.py` — does the posting through Instagram's official publishing API.
- `.github/workflows/post.yml` — runs `publish.py` daily at 20:00 Maldives time on GitHub's servers.
- `state.json` — written by the job; records what has been posted so nothing is ever posted twice.

## One-time setup
1. Instagram: create @leythikimv, then Settings → Account type and tools → switch to a professional account.
2. Meta: developers.facebook.com → My Apps → Create app → add the "Instagram" product → "API setup with
   Instagram login" → add the @leythikimv account → Generate token. Copy the long token.
   Permissions needed: instagram_business_basic and instagram_business_content_publish.
3. GitHub: create a PUBLIC repository named `leythikimv-publisher` and push this folder to it.
4. In the repository: Settings → Secrets and variables → Actions → New repository secret,
   name `IG_ACCESS_TOKEN`, value = the token from step 2.
5. Test: Actions tab → "Post to Instagram" → Run workflow → leave "Dry run" ticked. It prints what would be posted.

## Every week
- Approve days by adding their numbers to `approved_days` in `schedule.json`; set `start_date` once (YYYY-MM-DD).
- New days: run `build_schedule.py` in the studio, commit, push.

## Limits to know
- Poll, quiz and question stickers cannot be added by the API. Stories go out as plain images.
- The token lasts about 60 days. Generate a new one in the Meta app and replace the secret before it expires.
- If a post fails, or a day is due but not approved, the job fails and GitHub emails the repository owner.
- To stop everything: Actions tab → "Post to Instagram" → "…" → Disable workflow.
