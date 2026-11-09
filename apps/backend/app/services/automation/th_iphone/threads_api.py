"""
th_iphone/threads_api.py — API privee Threads (async).

Publish, reply, list comments via i.instagram.com.
Session: bearer capture via ScaleTweak, stocke en DB.

Usage:
    from .threads_api import ThreadsAPI
    api = ThreadsAPI(log=print)
    await api.publish_text("Hello Threads!")
    await api.list_comments(media_id)
    await api.reply_to_thread(media_id, comment_text)
"""

import asyncio
import json
import time
import uuid
import hashlib
import random
import os
import base64

import httpx

TH_API = "https://i.instagram.com/api/v1"
TH_APP_ID = "1546306509211461"
TH_APP_VERSION = "448.0.0.29.66"
TH_APP_BUILD = "1071656538"


class ThreadsAPI:
    def __init__(self, bearer="", ds_user_id="", sessionid="", mid="",
                 device_id=None, proxy=None, log=print):
        self.log = log
        self.proxy = proxy
        self.bearer = bearer
        self.ds_user_id = ds_user_id
        self.sessionid = sessionid
        self.mid = mid
        self.device_id = device_id or "FAC0D9E4-757C-4C96-BBD2-F98698057805"
        self.family_device_id = "0ED93C2B-EC72-4097-890D-EFE1114CB707"
        self.pigeon_session_id = "UFS-" + str(uuid.uuid4()).upper()
        self.www_claim = "0"
        self._session_start = time.time()
        self._request_count = 0
        self._replied_cache: set[str] = set()

        if self.bearer:
            self._decode_bearer()

    @classmethod
    async def from_compte(cls, db, compte_id, log=print):
        """Build API client from a compte's stored session."""
        from app.models.compte import Compte
        compte = await db.get(Compte, compte_id)
        if not compte:
            return None

        env = compte.env or {}
        session = env.get("th_session") or env.get("ig_session") or {}

        bearer = session.get("authorization", session.get("bearer", ""))
        ds_user_id = session.get("ds_user_id", "")
        sessionid = session.get("sessionid", "")
        mid = session.get("mid", "")
        device_id = session.get("device_id")

        proxy = None
        if compte.proxy_id:
            from app.models.proxy import Proxy
            p = await db.get(Proxy, compte.proxy_id)
            if p:
                proxy = p.url

        return cls(
            bearer=bearer,
            ds_user_id=ds_user_id,
            sessionid=sessionid,
            mid=mid,
            device_id=device_id,
            proxy=proxy,
            log=log,
        )

    def _decode_bearer(self):
        if "IGT:2:" not in self.bearer:
            return
        b64 = self.bearer.split("IGT:2:")[1]
        pad = 4 - (len(b64) % 4)
        if pad < 4:
            b64 += "=" * pad
        try:
            payload = json.loads(base64.b64decode(b64))
            if not self.ds_user_id:
                self.ds_user_id = payload.get("ds_user_id", "")
            if not self.sessionid:
                self.sessionid = payload.get("sessionid", "")
        except Exception:
            pass

    def _csrf(self):
        return hashlib.md5(
            ("%s_%s_%d" % (self.sessionid, self.ds_user_id, int(time.time()))).encode()
        ).hexdigest()

    def _nav_chain(self):
        now_ms = int(time.time() * 1000)
        elapsed = int((time.time() - self._session_start) * 1000)
        entries = [
            "MainFeedFragment:feed_timeline:0:button",
            "FeedContextMenuFragment:feed_timeline:%d:misc" % (elapsed - random.randint(2000, 5000)),
        ]
        if self._request_count > 1:
            entries.append(
                "BCNProfileFeedFragment:text_profile:%d:button" % (elapsed - random.randint(500, 2000))
            )
        return ":".join(entries[-3:])

    def _headers(self):
        csrf = self._csrf()
        self._request_count += 1
        bw = random.randint(15000, 45000)

        return {
            "User-Agent": "Barcelona %s (iPhone12,1; iOS 16.5; fr_FR; fr; scale=3.00; 828x1792; %s) AppleWebKit/420+" % (TH_APP_VERSION, TH_APP_BUILD),
            "X-IG-App-ID": TH_APP_ID,
            "X-IG-Device-ID": self.device_id,
            "X-IG-Family-Device-ID": self.family_device_id,
            "X-IG-Timezone-Offset": "7200",
            "X-IG-App-Locale": "fr_FR",
            "X-IG-Device-Locale": "fr_FR",
            "X-IG-Mapped-Locale": "fr_FR",
            "X-IG-Device-Languages": '[{"locale":"fr_FR","device_language":"fr-FR","app_language":"fr-FR","is_default":true}]',
            "X-IG-Connection-Type": "WiFi",
            "X-IG-Connection-Speed": "%dkbps" % bw,
            "X-IG-Bandwidth-Speed-KBPS": str(bw),
            "X-IG-ABR-Connection-Speed-KBPS": str(bw + random.randint(-2000, 2000)),
            "X-IG-Capabilities": "36r/F/8=",
            "X-Pigeon-Session-Id": self.pigeon_session_id,
            "X-Pigeon-Rawclienttime": "%.3f" % time.time(),
            "X-IG-Nav-Chain": self._nav_chain(),
            "X-IG-Push-State": "background",
            "X-IG-WWW-Claim": self.www_claim,
            "X-IG-Set-WWW-Claim": self.www_claim,
            "X-Bloks-Version-Id": "85a53ac59f5ac1faab02cfbf1155266ef84037c7228ef176da7de1342b675612",
            "Authorization": self.bearer,
            "X-CSRFToken": csrf,
            "Accept-Language": "fr-FR,fr;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Cookie": "ds_user_id=%s; sessionid=%s; mid=%s; csrftoken=%s" % (
                self.ds_user_id, self.sessionid, self.mid, csrf),
        }

    def _update_claim(self, resp):
        claim = resp.headers.get("x-ig-set-www-claim", "")
        if claim:
            self.www_claim = claim

    def _signed(self, payload):
        return "NOSIG." + json.dumps(payload, separators=(",", ":"))

    async def _post(self, endpoint, payload):
        url = "%s/%s" % (TH_API, endpoint.lstrip("/"))
        headers = self._headers()
        body = "signed_body=" + httpx._utils.quote(self._signed(payload))
        try:
            async with httpx.AsyncClient(proxy=self.proxy, timeout=30) as client:
                r = await client.post(url, content=body, headers=headers)
                self._update_claim(r)
                return r.json()
        except Exception as e:
            return {"status": "fail", "error": str(e)[:100]}

    async def _get(self, endpoint, params=None):
        url = "%s/%s" % (TH_API, endpoint.lstrip("/"))
        headers = self._headers()
        try:
            async with httpx.AsyncClient(proxy=self.proxy, timeout=30) as client:
                r = await client.get(url, headers=headers, params=params)
                self._update_claim(r)
                return r.json()
        except Exception as e:
            return {"status": "fail", "error": str(e)[:100]}

    # ── PUBLISH ───────────────────────────────────────────────────────────

    async def publish_text(self, caption, reply_control="everyone"):
        self.log("   [api] publish text (%d chars)" % len(caption))
        rc_map = {"everyone": 0, "accounts_you_follow": 1, "mentioned_only": 2}
        upload_id = str(int(time.time() * 1000))
        payload = {
            "_csrftoken": self._csrf(),
            "publish_mode": "text_post",
            "text_post_app_info": json.dumps({"reply_control": rc_map.get(reply_control, 0)}),
            "timezone_offset": "7200",
            "source_type": "4",
            "_uid": self.ds_user_id,
            "_uuid": self.device_id,
            "caption": caption,
            "upload_id": upload_id,
            "device_id": self.device_id,
        }
        result = await self._post("media/configure_text_only_post/", payload)
        if result.get("status") == "ok":
            media = result.get("media", {})
            self.log("   [api] published! pk=%s code=%s" % (media.get("pk"), media.get("code")))
        else:
            self.log("   [api] publish failed: %s" % result.get("message", result.get("error", "?")))
        return result

    async def publish_with_image(self, caption, image_data_or_url, reply_control="everyone"):
        """Publish a thread with an image."""
        self.log("   [api] publish with image (%d chars)" % len(caption))

        if isinstance(image_data_or_url, str) and image_data_or_url.startswith("http"):
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.get(image_data_or_url)
                img_data = r.content
        elif isinstance(image_data_or_url, bytes):
            img_data = image_data_or_url
        else:
            with open(image_data_or_url, "rb") as f:
                img_data = f.read()

        upload_id = str(int(time.time() * 1000))
        upload_name = "%s_0_%s" % (upload_id, str(int(time.time() * 1000)))

        headers = self._headers()
        headers.update({
            "Content-Type": "image/jpeg",
            "X-Entity-Length": str(len(img_data)),
            "X-Entity-Name": upload_name,
            "X-Entity-Type": "image/jpeg",
            "X-Instagram-Rupload-Params": json.dumps({
                "upload_id": upload_id,
                "media_type": 1,
                "image_compression": json.dumps({
                    "lib_name": "moz",
                    "lib_version": "3.1.m",
                    "quality": "87",
                }),
            }),
            "Offset": "0",
        })

        try:
            async with httpx.AsyncClient(proxy=self.proxy, timeout=60) as client:
                r_upload = await client.post(
                    "https://i.instagram.com/rupload_igphoto/%s" % upload_name,
                    content=img_data,
                    headers=headers,
                )
        except Exception as e:
            return {"status": "fail", "error": str(e)[:100]}

        if r_upload.status_code != 200:
            return {"status": "fail", "error": "upload failed: %d" % r_upload.status_code}

        self.log("   [api] uploaded (%d bytes)" % len(img_data))
        await asyncio.sleep(1)

        rc_map = {"everyone": 0, "accounts_you_follow": 1, "mentioned_only": 2}
        payload = {
            "_csrftoken": self._csrf(),
            "publish_mode": "default",
            "text_post_app_info": {"reply_control": rc_map.get(reply_control, 0)},
            "timezone_offset": "7200",
            "source_type": "4",
            "_uid": self.ds_user_id,
            "_uuid": self.device_id,
            "device_id": self.device_id,
            "device_timestamp": str(int(time.time())),
            "caption": caption,
            "upload_id": upload_id,
        }

        h2 = self._headers()
        body = "signed_body=NOSIG." + json.dumps(payload, separators=(",", ":"))
        try:
            async with httpx.AsyncClient(proxy=self.proxy, timeout=30) as client:
                r2 = await client.post(
                    "https://i.instagram.com/api/v1/media/configure_text_post_app_feed/",
                    content=body,
                    headers=h2,
                )
                self._update_claim(r2)
                result = r2.json()
        except Exception as e:
            return {"status": "fail", "error": str(e)[:100]}

        if result.get("status") == "ok":
            media = result.get("media", {})
            self.log("   [api] published with image! pk=%s code=%s" % (
                media.get("pk"), media.get("code")))
        else:
            self.log("   [api] publish failed: %s" % result.get("message", "?"))

        return result

    # ── COMMENTS ──────────────────────────────────────────────────────────

    async def list_comments(self, media_id, min_id=None):
        self.log("   [api] list comments (media=%s)" % str(media_id)[:20])
        params = {}
        if min_id:
            params["min_id"] = min_id
        result = await self._get("media/%s/comments/" % media_id, params)
        if result.get("status") == "ok":
            comments = result.get("comments", [])
            self.log("   [api] %d comments" % len(comments))
        else:
            self.log("   [api] comments failed: %s" % result.get("message", "?"))
        return result

    async def reply_to_thread(self, parent_media_id, text, reply_control="everyone"):
        """Reply to a thread post."""
        self.log("   [api] reply to %s (%d chars)" % (str(parent_media_id)[:20], len(text)))
        rc_map = {"everyone": 0, "accounts_you_follow": 1, "mentioned_only": 2}
        upload_id = str(int(time.time() * 1000))
        payload = {
            "_csrftoken": self._csrf(),
            "publish_mode": "text_post",
            "text_post_app_info": json.dumps({
                "reply_control": rc_map.get(reply_control, 0),
                "reply_id": str(parent_media_id),
            }),
            "timezone_offset": "7200",
            "source_type": "4",
            "_uid": self.ds_user_id,
            "_uuid": self.device_id,
            "caption": text,
            "upload_id": upload_id,
            "device_id": self.device_id,
        }
        result = await self._post("media/configure_text_only_post/", payload)
        if result.get("status") == "ok":
            media = result.get("media", {})
            self.log("   [api] replied! pk=%s" % media.get("pk"))
        else:
            self.log("   [api] reply failed: %s" % result.get("message", result.get("error", "?")))
        return result

    # ── USER POSTS ────────────────────────────────────────────────────────

    async def get_user_posts(self, user_id=None, max_id=None):
        uid = user_id or self.ds_user_id
        self.log("   [api] get posts (user=%s)" % uid)
        params = {}
        if max_id:
            params["max_id"] = max_id
        result = await self._get("text_feed/%s/profile/" % uid, params)
        if result.get("status") == "ok":
            threads = result.get("threads", [])
            self.log("   [api] %d threads" % len(threads))
        else:
            self.log("   [api] posts failed: %s" % result.get("message", "?"))
        return result

    # ── THREAD DETAIL ─────────────────────────────────────────────────────

    async def get_thread(self, media_id):
        """Get a single thread with all replies."""
        self.log("   [api] get thread %s" % str(media_id)[:20])
        return await self._get("text_feed/%s/single_thread/" % str(media_id))

    async def get_replies(self, media_id):
        """Get replies to a thread from other users."""
        r = await self.get_thread(media_id)
        replies = []
        for rt in r.get("reply_threads", []) or []:
            for item in rt.get("thread_items", []):
                post = item.get("post", {})
                user = post.get("user", {})
                caption = post.get("caption")
                if str(user.get("pk", "")) != str(self.ds_user_id):
                    replies.append({
                        "username": user.get("username", ""),
                        "user_id": str(user.get("pk", "")),
                        "text": caption.get("text", "") if caption else "",
                        "pk": str(post.get("pk", "")),
                        "created_at": post.get("taken_at", 0),
                    })
        return replies

    async def get_all_pending_replies(self):
        """Get all unanswered replies across all our threads."""
        self.log("   [api] scanning for pending replies")
        pending = []
        r = await self.get_user_posts()
        for t in r.get("threads", []):
            items = t.get("thread_items", [])
            if not items:
                continue
            post = items[0].get("post", {})
            tpai = post.get("text_post_app_info", {}) or {}
            reply_count = tpai.get("direct_reply_count", 0)
            if reply_count > 0:
                thread_pk = post.get("pk")
                replies = await self.get_replies(thread_pk)
                for reply in replies:
                    if reply["pk"] not in self._replied_cache:
                        pending.append({
                            "thread_pk": str(thread_pk),
                            "thread_text": (post.get("caption", {}) or {}).get("text", "")[:60],
                            "reply_pk": reply["pk"],
                            "username": reply["username"],
                            "text": reply["text"],
                        })
        self.log("   [api] %d pending replies" % len(pending))
        return pending

    def mark_replied(self, reply_pk):
        """Mark a reply as answered (in-memory cache)."""
        self._replied_cache.add(str(reply_pk))

    def is_replied(self, reply_pk):
        """Check if we already replied to this."""
        return str(reply_pk) in self._replied_cache

    async def reply_and_track(self, parent_pk, text):
        """Reply to a thread and mark it as answered."""
        result = await self.reply_to_thread(parent_pk, text)
        if result.get("status") == "ok":
            self.mark_replied(parent_pk)
        return result

    # ── ACTIVITY ──────────────────────────────────────────────────────────

    async def get_activity_count(self):
        return await self._get("text_feed/ig_text_post_app_new_activity_feed_count/")

    # ── EDIT / PIN ────────────────────────────────────────────────────────

    async def edit_post(self, media_id, new_caption):
        self.log("   [api] edit post %s" % str(media_id)[:20])
        payload = {"_csrftoken": self._csrf(), "caption": new_caption, "_uid": self.ds_user_id, "_uuid": self.device_id}
        return await self._post("text_feed/%s/edit_post/" % media_id, payload)

    async def pin_to_profile(self, media_id):
        self.log("   [api] pin %s" % str(media_id)[:20])
        payload = {"_csrftoken": self._csrf(), "_uid": self.ds_user_id, "_uuid": self.device_id}
        return await self._post("text_feed/%s/pin_to_profile/" % media_id, payload)

    async def unpin_from_profile(self, media_id):
        payload = {"_csrftoken": self._csrf(), "_uid": self.ds_user_id, "_uuid": self.device_id}
        return await self._post("text_feed/%s/unpin_from_profile/" % media_id, payload)

    # ── REPOST ────────────────────────────────────────────────────────────

    async def repost(self, media_id):
        self.log("   [api] repost %s" % str(media_id)[:20])
        payload = {"_csrftoken": self._csrf(), "media_id": str(media_id), "_uid": self.ds_user_id, "_uuid": self.device_id}
        return await self._post("repost/create_repost/", payload)

    # ── INSIGHTS ──────────────────────────────────────────────────────────

    async def get_post_insights(self, media_id=None):
        """Get insights for a specific post or all posts."""
        self.log("   [api] get insights")
        r = await self.get_user_posts()
        insights = []

        for t in r.get("threads", []):
            for item in t.get("thread_items", []):
                post = item.get("post", {})
                tpai = post.get("text_post_app_info", {}) or {}
                caption = post.get("caption")

                if media_id and str(post.get("pk")) != str(media_id):
                    continue

                insights.append({
                    "pk": str(post.get("pk", "")),
                    "code": post.get("code", ""),
                    "text": (caption.get("text", "") if caption else "")[:80],
                    "media_type": post.get("media_type"),
                    "likes": post.get("like_count", 0),
                    "replies": tpai.get("direct_reply_count", 0),
                    "reposts": tpai.get("repost_count", 0),
                    "quotes": tpai.get("quote_count", 0),
                    "is_reply": tpai.get("is_reply", False),
                    "created_at": post.get("taken_at", 0),
                    "url": "https://www.threads.net/t/%s" % post.get("code", ""),
                })

        if media_id:
            return insights[0] if insights else None

        self.log("   [api] %d posts with insights" % len(insights))
        return insights

    async def get_account_summary(self):
        """Get account summary: total posts, total engagement."""
        self.log("   [api] account summary")
        insights = await self.get_post_insights()
        original_posts = [p for p in insights if not p["is_reply"]]

        total_likes = sum(p["likes"] for p in original_posts)
        total_replies = sum(p["replies"] for p in original_posts)
        total_reposts = sum(p["reposts"] for p in original_posts)
        total_quotes = sum(p["quotes"] for p in original_posts)
        total_engagement = total_likes + total_replies + total_reposts + total_quotes

        return {
            "posts": len(original_posts),
            "total_likes": total_likes,
            "total_replies": total_replies,
            "total_reposts": total_reposts,
            "total_quotes": total_quotes,
            "total_engagement": total_engagement,
            "avg_engagement": round(total_engagement / max(len(original_posts), 1), 1),
        }

    # ── SEARCH ────────────────────────────────────────────────────────────

    async def search_users(self, query, count=10):
        return await self._get("users/search/", {"q": query, "count": count})
