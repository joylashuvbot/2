"""
GitHub Backup Moduli
--------------------
• Har qanday o'zgartirish bo'lganda places.json ni yangilaydi
• O'zgarishni GitHub repoga push qiladi
• Bot qayta ishga tushganda baza bo'sh bo'lsa, json dan tiklaydi

Kerakli ENV o'zgaruvchilar:
  GITHUB_TOKEN   – Personal Access Token (repo yozish huquqi bilan)
  GITHUB_REPO    – "username/repo-name"  masalan: "ali/halal-bot"
  GITHUB_BRANCH  – (ixtiyoriy, default: "main")
"""

import os
import json
import base64
import asyncio
import aiohttp
import logging

log = logging.getLogger(__name__)

GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO   = os.getenv("GITHUB_REPO", "")       # "username/repo"
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
JSON_FILENAME = "places.json"   # repodagi fayl nomi

# ─────────────────────────────────────────────────────────────────────────────
# Ichki yordamchi: GitHub Contents API
# ─────────────────────────────────────────────────────────────────────────────

async def _get_file_sha(session: aiohttp.ClientSession) -> str | None:
    """Repodagi faylning SHA ni oladi (yangilash uchun kerak)."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{JSON_FILENAME}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    params = {"ref": GITHUB_BRANCH}
    async with session.get(url, headers=headers, params=params) as resp:
        if resp.status == 200:
            data = await resp.json()
            return data.get("sha")
        return None  # fayl hali yo'q


async def _push_json(content_str: str) -> bool:
    """
    places.json ni GitHub repoga push qiladi.
    Qaytaradi: True – muvaffaqiyatli, False – xato.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log.warning("GITHUB_TOKEN yoki GITHUB_REPO ENV da yo'q – backup o'tkazib yuborildi.")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{JSON_FILENAME}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
    }
    encoded = base64.b64encode(content_str.encode("utf-8")).decode("ascii")

    async with aiohttp.ClientSession() as session:
        sha = await _get_file_sha(session)

        body: dict = {
            "message": "bot: places.json yangilandi (avtomatik)",
            "content": encoded,
            "branch": GITHUB_BRANCH,
        }
        if sha:
            body["sha"] = sha  # mavjud faylni yangilash uchun sha kerak

        async with session.put(url, headers=headers, json=body) as resp:
            if resp.status in (200, 201):
                log.info("✅ places.json GitHub ga muvaffaqiyatli push qilindi.")
                return True
            else:
                text = await resp.text()
                log.error(f"❌ GitHub push xatosi {resp.status}: {text}")
                return False


# ─────────────────────────────────────────────────────────────────────────────
# Tashqi funksiyalar (app.py dan chaqiriladi)
# ─────────────────────────────────────────────────────────────────────────────

async def backup_to_github(places: list[dict]) -> bool:
    """
    PLACES ro'yxatini places.json ga yozib, GitHub ga push qiladi.
    Har bir add / edit / delete dan keyin chaqiring.
    """
    # text/text_user/text_channel – barchasini saqlaymiz
    export = []
    for p in places:
        export.append({
            "name":         p.get("name", ""),
            "lat":          p.get("lat", 0.0),
            "lng":          p.get("lng", 0.0),
            "text_user":    p.get("text_user", p.get("text", "")),
            "text_channel": p.get("text_channel", p.get("text", "")),
        })

    content_str = json.dumps(export, ensure_ascii=False, indent=2)

    # JSON faylni lokal ham saqlaylik (optional, debug uchun)
    try:
        with open(JSON_FILENAME, "w", encoding="utf-8") as f:
            f.write(content_str)
    except Exception as e:
        log.warning(f"Lokal places.json yozishda xato: {e}")

    # GitHub ga yuborish
    try:
        return await _push_json(content_str)
    except Exception as e:
        log.error(f"backup_to_github xatosi: {e}")
        return False


async def restore_from_github() -> list[dict] | None:
    """
    GitHub dagi places.json ni yuklab, list qaytaradi.
    Baza bo'sh bo'lganda chaqiriladi.
    """
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log.warning("GITHUB_TOKEN yoki GITHUB_REPO yo'q – restore o'tkazib yuborildi.")
        return None

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{JSON_FILENAME}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    params = {"ref": GITHUB_BRANCH}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    log.warning(f"GitHub dan restore: {resp.status}")
                    return None
                data = await resp.json()
                raw = base64.b64decode(data["content"]).decode("utf-8")
                places = json.loads(raw)
                log.info(f"✅ GitHub dan {len(places)} ta joy yuklandi.")
                return places
    except Exception as e:
        log.error(f"restore_from_github xatosi: {e}")
        return None