import asyncio
import base64
import logging
import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.utils import parseaddr
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.ingestion.base import BaseIngestor, RawItem, SourceFetchError
from app.utils.date_parser import parse_date
from app.utils.hash import normalize_url, validate_url
from app.utils.text_cleaner import clean_body, clean_title


logger = logging.getLogger(__name__)

GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
HARD_BLOCKED_PATH_RE = re.compile(
    r"(?:^|/)(?:unsubscribe|optout|email-preferences|manage-preferences|"
    r"pixel|beacon)(?:/|$)",
    re.IGNORECASE,
)
TRACKER_PATH_RE = re.compile(
    r"(?:^|/)(?:click|track|redirect|redirector)(?:/|$)",
    re.IGNORECASE,
)
NON_ARTICLE_PATH_RE = re.compile(
    r"(?:^|/)(?:account|auth|careers?|events?|jobs?|login|privacy|"
    r"register|settings|sign-?in|signup|subscribe|terms)(?:/|$)",
    re.IGNORECASE,
)
PROMOTION_RE = re.compile(
    r"\b(?:a message from|advertisement|advertorial|brought to you by|"
    r"exclusive offer|paid partnership|partner message|promoted by|"
    r"promotion|sponsor(?:ed| message)?|special offer|presented by|"
    r"today(?:'s|s) partner|together with|use code)\b|"
    r"\bsave\s+\d{1,3}\s*%",
    re.IGNORECASE,
)
PROMOTIONAL_SUBJECT_RE = re.compile(
    r"^\s*(?:ad|advertisement|deal|offer|promotion|sponsored)\s*[:\-]",
    re.IGNORECASE,
)
NOISE_TEXT_RE = re.compile(
    r"^(?:advertise|advertise with us|apply here|apply now|contact us|"
    r"create your own role|download on the app store|follow us|"
    r"forward to a friend|get it on google play|join now|"
    r"facebook|instagram|linkedin|manage preferences|privacy policy|"
    r"register now|share|sign in|sign up|subscribe|thanks for reading|"
    r"track your referrals|tracking link|twitter|unsubscribe|upgrade|"
    r"view in browser|view online|x)\b",
    re.IGNORECASE,
)
FOOTER_TEXT_RE = re.compile(
    r"\b(?:manage (?:email )?preferences|privacy policy|"
    r"received this email because|update your preferences|unsubscribe)\b",
    re.IGNORECASE,
)
PROMO_ATTRIBUTE_RE = re.compile(
    r"(?:^|[-_\s])(?:ad|advert|promo|promotion|sponsor)(?:$|[-_\s])",
    re.IGNORECASE,
)
SOCIAL_SHARE_HOSTS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "threads.net",
    "twitter.com",
    "x.com",
}
SOCIAL_SHARE_PATH_RE = re.compile(
    r"(?:/intent/|/share(?:article)?/?$|/sharer)",
    re.IGNORECASE,
)
NON_CONTENT_EXTENSIONS = {
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}
PLAIN_URL_RE = re.compile(r"https?://[^\s<>()\[\]\"']+")
GENERIC_LINK_TITLES = {
    "",
    "click here",
    "continue reading",
    "learn more",
    "more",
    "read",
    "read more",
    "view",
    "view article",
}
TRACKER_HOST_LABELS = {"click", "go", "link", "links", "redirect", "track"}
TRACKER_HOSTS = {"bit.ly", "lnkd.in", "short.gy", "t.co", "tinyurl.com"}
NON_ARTICLE_HOST_LABELS = {
    "advertise",
    "careers",
    "events",
    "jobs",
    "refer",
}
REDIRECT_QUERY_KEYS = {
    "continue",
    "dest",
    "destination",
    "next",
    "redirect",
    "redirect_url",
    "target",
    "u",
    "url",
}
MAX_ARTICLE_CONTEXT = 3000


async def resolve_redirect_url(
    url: str,
    *,
    timeout_seconds: float = 5.0,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Resolve at most one HTTP redirect without following the destination."""
    try:
        original = validate_url(url)
    except ValueError:
        return None
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    for attempt in range(2):
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            return None
        try:
            if client is None:
                async with httpx.AsyncClient(timeout=remaining) as local_client:
                    response = await local_client.get(
                        original,
                        follow_redirects=False,
                    )
            else:
                response = await client.get(original, follow_redirects=False)
            if response.is_redirect:
                location = response.headers.get("location")
                return (
                    validate_url(urljoin(original, location))
                    if location
                    else None
                )
            if response.is_success:
                return original
            if response.status_code < 500:
                return None
        except (httpx.HTTPError, ValueError):
            if attempt == 1:
                return None
    return None


class GmailIngestor(BaseIngestor):
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        newsletter_senders: list[str],
        service_factory: Callable[[], Any] | None = None,
        redirect_resolver: Callable[[str], Any] = resolve_redirect_url,
        now_factory: Callable[[], datetime] | None = None,
    ):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.refresh_token = refresh_token.strip()
        self.newsletter_senders = [
            sender.strip().lower()
            for sender in newsletter_senders
            if sender.strip()
        ]
        self.service_factory = service_factory
        self.redirect_resolver = redirect_resolver
        self.now_factory = now_factory or (lambda: datetime.now(UTC))

    async def fetch(self) -> list[RawItem]:
        self._validate_configuration()
        try:
            service = await asyncio.to_thread(self._build_service)
            message_ids = await self._list_message_ids(service)
        except RefreshError as exc:
            raise SourceFetchError(
                "Gmail OAuth refresh failed. Re-run gmail_auth_setup.py with "
                "the gmail.readonly scope."
            ) from exc
        except HttpError as exc:
            if exc.resp.status in {401, 403}:
                raise SourceFetchError(
                    "Gmail OAuth grant is missing gmail.readonly access. "
                    "Revoke the old grant and run gmail_auth_setup.py again."
                ) from exc
            raise SourceFetchError(f"Gmail API request failed: {exc}") from exc

        items: list[RawItem] = []
        extraction_failures = 0
        for gmail_id, sender_domain in message_ids.items():
            try:
                message = await asyncio.to_thread(
                    lambda message_id=gmail_id: service.users()
                    .messages()
                    .get(userId="me", id=message_id, format="full")
                    .execute()
                )
            except HttpError as exc:
                logger.error("Gmail message %s could not be read: %s", gmail_id, exc)
                continue
            try:
                items.extend(await self.extract_message(message, sender_domain))
            except Exception:
                extraction_failures += 1
                logger.exception(
                    "Gmail message %s could not be extracted",
                    gmail_id,
                )
        if message_ids and extraction_failures == len(message_ids):
            raise SourceFetchError("Every matched Gmail message failed extraction")
        return self._deduplicate_items(items)

    def _validate_configuration(self) -> None:
        missing = [
            name
            for name, value in (
                ("GMAIL_CLIENT_ID", self.client_id),
                ("GMAIL_CLIENT_SECRET", self.client_secret),
                ("GMAIL_REFRESH_TOKEN", self.refresh_token),
                ("NEWSLETTER_SENDERS", ",".join(self.newsletter_senders)),
            )
            if not value
        ]
        if missing:
            raise SourceFetchError(
                "Gmail is not configured; missing " + ", ".join(missing)
            )

    def _build_service(self) -> Any:
        if self.service_factory is not None:
            return self.service_factory()
        credentials = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri=GOOGLE_TOKEN_URI,
            client_id=self.client_id,
            client_secret=self.client_secret,
        )
        return build(
            "gmail",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

    async def _list_message_ids(self, service: Any) -> dict[str, str]:
        after_epoch = int(
            (self.now_factory().astimezone(UTC) - timedelta(hours=48)).timestamp()
        )
        found: dict[str, str] = {}
        for sender in self.newsletter_senders:
            page_token: str | None = None
            query = f"from:{sender} after:{after_epoch} is:unread"
            while True:
                response = await asyncio.to_thread(
                    lambda token=page_token, q=query: service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=q,
                        maxResults=100,
                        pageToken=token,
                    )
                    .execute()
                )
                for message in response.get("messages", []):
                    gmail_id = str(message.get("id") or "")
                    if gmail_id:
                        found.setdefault(gmail_id, sender)
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        return found

    async def extract_message(
        self,
        message: dict[str, Any],
        sender_domain: str,
    ) -> list[RawItem]:
        payload = message.get("payload") or {}
        headers = {
            str(header.get("name") or "").lower(): str(
                header.get("value") or ""
            )
            for header in payload.get("headers", [])
        }
        gmail_id = str(message.get("id") or "")
        message_id = headers.get("message-id") or gmail_id
        if not message_id:
            return []

        subject = clean_title(headers.get("subject") or "Newsletter update")
        if PROMOTIONAL_SUBJECT_RE.search(subject):
            logger.info("Skipping promotional Gmail message: %s", subject)
            return []
        received_at = self._received_at(message, headers)
        plain_parts, html_parts = self._message_bodies(payload)
        raw_plain = "\n".join(plain_parts)
        raw_html = "\n".join(html_parts)
        if self._looks_like_html(raw_plain):
            raw_html = f"{raw_html}\n{raw_plain}"
            raw_plain = ""
        plain_text = self._sanitize_plain_text(raw_plain)
        html = self._sanitize_html(raw_html)
        body_text = self._clean_content_text(
            plain_text or clean_body(html),
            8000,
        )
        email_url = self._email_url(gmail_id)

        sender_address = parseaddr(headers.get("from", ""))[1]
        actual_sender_domain = (
            sender_address.rsplit("@", 1)[-1].lower()
            if "@" in sender_address
            else sender_domain
        )
        own_domains = {sender_domain.lower(), actual_sender_domain}

        candidates = (
            self._html_link_candidates(html, subject)
            if html
            else self._plain_link_candidates(plain_text, subject)
        )
        items: list[RawItem] = []
        for href, title, context in candidates:
            if self._is_noise_candidate(title, context):
                continue
            resolved_url = await self._external_url(href, own_domains)
            if resolved_url is None:
                continue
            context = self._clean_content_text(context, MAX_ARTICLE_CONTEXT)
            if len(context) < 80 and title.casefold() in GENERIC_LINK_TITLES:
                continue
            try:
                source_link_id = validate_url(href)
            except ValueError:
                source_link_id = resolved_url
            items.append(
                RawItem(
                    title=title,
                    url=resolved_url,
                    source="gmail",
                    source_id=f"{message_id}::{source_link_id}",
                    published_at=received_at,
                    raw_text=context or body_text[:500],
                    raw_html=None,
                )
            )

        if not items and html:
            items.extend(
                self._inline_section_items(
                    html=html,
                    subject=subject,
                    message_id=message_id,
                    email_url=email_url,
                    published_at=received_at,
                )
            )

        if len(body_text) > 500:
            items.append(
                RawItem(
                    title=subject,
                    url=email_url,
                    source="gmail",
                    source_id=message_id,
                    published_at=received_at,
                    raw_text=body_text,
                    raw_html=html or None,
                )
            )
        return self._deduplicate_items(items)

    async def _external_url(
        self,
        href: str,
        own_domains: set[str],
    ) -> str | None:
        try:
            original_url = validate_url(href)
        except ValueError:
            return None
        if self._is_hard_blocked_url(original_url):
            return None

        url = self._embedded_redirect_target(original_url) or original_url
        if self._needs_redirect_resolution(url):
            resolved = self.redirect_resolver(url)
            resolved_url = (
                await resolved if hasattr(resolved, "__await__") else resolved
            )
            if resolved_url is not None:
                try:
                    url = validate_url(resolved_url)
                except ValueError:
                    pass

        if self._is_hard_blocked_url(url):
            return None
        final_hostname = (urlparse(url).hostname or "").lower()
        if self._is_social_share_url(url):
            return None
        final_hostname = (urlparse(url).hostname or "").lower()
        if self._is_non_article_host(final_hostname):
            return None
        if self._is_non_article_navigation(url):
            if url != original_url and not self._is_non_article_navigation(
                original_url
            ):
                url = original_url
            else:
                return None
        final_hostname = (urlparse(url).hostname or "").lower()
        if self._is_newsletter_navigation(url, final_hostname, own_domains):
            return None
        return url

    @staticmethod
    def _needs_redirect_resolution(url: str) -> bool:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        first_label = hostname.split(".", 1)[0]
        return (
            first_label in TRACKER_HOST_LABELS
            or hostname.removeprefix("www.") in TRACKER_HOSTS
            or TRACKER_PATH_RE.search(parsed.path) is not None
        )

    @staticmethod
    def _embedded_redirect_target(url: str) -> str | None:
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")
        if len(path_parts) >= 4 and path_parts[1].casefold() == "cl0":
            candidate = unquote(path_parts[2])
            try:
                return validate_url(candidate)
            except ValueError:
                pass

        query = parse_qs(parsed.query)
        for key in REDIRECT_QUERY_KEYS:
            values = query.get(key)
            if not values:
                continue
            candidate = unquote(values[0])
            try:
                return validate_url(candidate)
            except ValueError:
                continue
        return None

    @staticmethod
    def _is_hard_blocked_url(url: str) -> bool:
        parsed = urlparse(url)
        path = parsed.path.lower()
        return (
            HARD_BLOCKED_PATH_RE.search(path) is not None
            or any(path.endswith(extension) for extension in NON_CONTENT_EXTENSIONS)
        )

    @staticmethod
    def _is_social_share_url(url: str) -> bool:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower().removeprefix("www.")
        return hostname in SOCIAL_SHARE_HOSTS

    @staticmethod
    def _is_non_article_host(hostname: str) -> bool:
        first_label = hostname.removeprefix("www.").split(".", 1)[0]
        return (
            first_label in NON_ARTICLE_HOST_LABELS
            or hostname.endswith(".sparklp.co")
        )

    @staticmethod
    def _is_non_article_navigation(url: str) -> bool:
        parsed = urlparse(url)
        if NON_ARTICLE_PATH_RE.search(parsed.path) is None:
            return False
        query_keys = {key.casefold() for key in parse_qs(parsed.query)}
        return not bool(query_keys & REDIRECT_QUERY_KEYS)

    @staticmethod
    def _is_newsletter_navigation(
        url: str,
        hostname: str,
        own_domains: set[str],
    ) -> bool:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        is_own_domain = any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in own_domains
            if domain and "@" not in domain
        )
        if not is_own_domain:
            return False
        if not path:
            return True
        return path.casefold() in {
            "/about",
            "/archive",
            "/home",
            "/podcast",
            "/recommendations",
            "/welcome",
        }

    @staticmethod
    def _html_link_candidates(
        html: str,
        subject: str,
    ) -> list[tuple[str, str, str]]:
        soup = BeautifulSoup(html, "html.parser")
        candidates: list[tuple[str, str, str]] = []
        for anchor in soup.find_all("a", href=True):
            if GmailIngestor._is_promotional_node(anchor):
                continue
            href = str(anchor.get("href") or "").strip()
            if not href.lower().startswith(("http://", "https://")):
                continue
            anchor_text = clean_title(anchor.get_text(" ", strip=True), 200)
            heading = anchor.find_previous(["h1", "h2", "h3", "h4"])
            heading_text = (
                clean_title(heading.get_text(" ", strip=True), 200)
                if isinstance(heading, Tag)
                else ""
            )
            title = (
                heading_text
                if anchor_text.lower() in GENERIC_LINK_TITLES
                else anchor_text
            )
            title = title or heading_text or subject
            context = GmailIngestor._article_context(anchor, heading, anchor_text)
            candidates.append((href, title, context))
        return candidates

    @staticmethod
    def _article_context(
        anchor: Tag,
        heading: Tag | None,
        anchor_text: str,
    ) -> str:
        context_options: list[str] = []
        for parent in anchor.parents:
            if not isinstance(parent, Tag) or parent.name in {"body", "html"}:
                break
            if parent.name not in {
                "article",
                "blockquote",
                "div",
                "li",
                "section",
                "td",
            }:
                continue
            text = GmailIngestor._clean_content_text(
                parent.get_text(" ", strip=True),
                MAX_ARTICLE_CONTEXT,
            )
            if 100 <= len(text) <= MAX_ARTICLE_CONTEXT:
                context_options.append(text)
                break

        if isinstance(heading, Tag):
            section_parts = [heading.get_text(" ", strip=True)]
            for sibling in heading.next_siblings:
                if isinstance(sibling, Tag) and sibling.name in {
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                }:
                    break
                text = (
                    sibling.get_text(" ", strip=True)
                    if isinstance(sibling, Tag)
                    else str(sibling).strip()
                )
                if text:
                    section_parts.append(text)
                if len(" ".join(section_parts)) >= MAX_ARTICLE_CONTEXT:
                    break
            section_text = GmailIngestor._clean_content_text(
                " ".join(section_parts),
                MAX_ARTICLE_CONTEXT,
            )
            if len(section_text) >= 80:
                context_options.append(section_text)

        paragraph = anchor.find_parent(["p", "li", "blockquote"])
        paragraph_text = (
            GmailIngestor._clean_content_text(
                paragraph.get_text(" ", strip=True),
                MAX_ARTICLE_CONTEXT,
            )
            if isinstance(paragraph, Tag)
            else anchor_text
        )
        if paragraph_text:
            context_options.append(paragraph_text)
        if not context_options:
            return anchor_text
        return max(context_options, key=len)

    @staticmethod
    def _plain_link_candidates(
        plain_text: str,
        subject: str,
    ) -> list[tuple[str, str, str]]:
        candidates: list[tuple[str, str, str]] = []
        for match in PLAIN_URL_RE.finditer(plain_text):
            href = match.group(0).rstrip(".,;:")
            start = max(0, match.start() - 250)
            end = min(len(plain_text), match.end() + 250)
            context = clean_body(plain_text[start:end], 500)
            line_start = plain_text.rfind("\n", 0, match.start()) + 1
            preceding = clean_title(
                plain_text[line_start:match.start()].strip(" :-"),
                200,
            )
            context = GmailIngestor._clean_content_text(
                context,
                MAX_ARTICLE_CONTEXT,
            )
            candidates.append((href, preceding or subject, context))
        return candidates

    @staticmethod
    def _inline_section_items(
        *,
        html: str,
        subject: str,
        message_id: str,
        email_url: str,
        published_at: datetime | None,
    ) -> list[RawItem]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[RawItem] = []
        for index, heading in enumerate(soup.find_all(["h2", "h3"]), start=1):
            if GmailIngestor._is_promotional_node(heading):
                continue
            section_parts: list[str] = []
            for sibling in heading.next_siblings:
                if isinstance(sibling, Tag) and sibling.name in {"h2", "h3"}:
                    break
                if isinstance(sibling, Tag):
                    text = sibling.get_text(" ", strip=True)
                else:
                    text = str(sibling).strip()
                if text:
                    section_parts.append(text)
            section_text = GmailIngestor._clean_content_text(
                " ".join(section_parts),
                MAX_ARTICLE_CONTEXT,
            )
            if len(section_text) < 100:
                continue
            title = clean_title(heading.get_text(" ", strip=True), 200) or subject
            items.append(
                RawItem(
                    title=title,
                    url=f"{email_url}&pulse_section={index}",
                    source="gmail",
                    source_id=f"{message_id}::section::{index}",
                    published_at=published_at,
                    raw_text=section_text,
                    raw_html=None,
                )
            )
        return items

    @staticmethod
    def _sanitize_html(html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(
            ["script", "style", "noscript", "svg", "form", "iframe"]
        ):
            tag.decompose()
        for tag in list(soup.find_all(True)):
            if tag.attrs is None:
                continue
            style = str(tag.get("style") or "").replace(" ", "").casefold()
            classes = " ".join(tag.get("class") or []).casefold()
            if (
                tag.has_attr("hidden")
                or str(tag.get("aria-hidden") or "").casefold() == "true"
                or "display:none" in style
                or "visibility:hidden" in style
                or "max-height:0" in style
                or "preheader" in classes
                or "gmail_quote" in classes
            ):
                tag.decompose()
        for tag in list(
            soup.find_all(
                ["aside", "blockquote", "div", "footer", "li", "p", "section", "table", "td"]
            )
        ):
            if not tag.parent:
                continue
            if GmailIngestor._is_promotional_node(tag):
                tag.decompose()
                continue
            text = clean_body(tag.get_text(" ", strip=True), 500)
            if len(text) <= 500 and FOOTER_TEXT_RE.search(text):
                tag.decompose()
        return str(soup)

    @staticmethod
    def _sanitize_plain_text(value: str) -> str:
        if not value:
            return ""
        kept: list[str] = []
        for block in re.split(r"\n\s*\n", value):
            cleaned = clean_body(block, MAX_ARTICLE_CONTEXT)
            if not cleaned:
                continue
            footer_match = FOOTER_TEXT_RE.search(cleaned)
            if footer_match:
                prefix = clean_body(cleaned[: footer_match.start()])
                if prefix:
                    kept.append(prefix)
                break
            if PROMOTION_RE.search(cleaned[:200]):
                continue
            if NOISE_TEXT_RE.search(cleaned):
                continue
            kept.append(cleaned)
        return clean_body(" ".join(kept))

    @staticmethod
    def _looks_like_html(value: str) -> bool:
        sample = value.lstrip()[:1000].casefold()
        return (
            sample.startswith("<!doctype html")
            or sample.startswith("<html")
            or ("<head" in sample and "<body" in sample)
        )

    @staticmethod
    def _is_promotional_node(node: Tag) -> bool:
        attributes = " ".join(
            str(value)
            for key in ("class", "id", "aria-label", "data-testid")
            for value in (
                node.get(key, [])
                if isinstance(node.get(key, []), list)
                else [node.get(key, "")]
            )
        )
        if PROMO_ATTRIBUTE_RE.search(attributes):
            return True
        text = clean_body(node.get_text(" ", strip=True), 2000)
        return len(text) <= 2000 and PROMOTION_RE.search(text[:250]) is not None

    @staticmethod
    def _clean_content_text(value: str, max_length: int) -> str:
        if not value:
            return ""
        sentences = re.split(r"(?<=[.!?])\s+|\s*[|•]\s*", clean_body(value))
        kept = [
            sentence
            for sentence in sentences
            if sentence
            and not PROMOTION_RE.search(sentence[:200])
            and not NOISE_TEXT_RE.search(sentence)
            and not FOOTER_TEXT_RE.search(sentence)
        ]
        return clean_body(" ".join(kept), max_length)

    @staticmethod
    def _is_noise_candidate(title: str, context: str) -> bool:
        normalized_title = clean_title(title).casefold()
        if NOISE_TEXT_RE.search(normalized_title):
            return True
        if PROMOTION_RE.search(normalized_title):
            return True
        cleaned_context = clean_body(context, 500)
        return (
            len(cleaned_context) < 40
            and normalized_title in GENERIC_LINK_TITLES
        )

    @classmethod
    def _message_bodies(
        cls,
        payload: dict[str, Any],
    ) -> tuple[list[str], list[str]]:
        plain_parts: list[str] = []
        html_parts: list[str] = []

        def visit(part: dict[str, Any]) -> None:
            mime_type = str(part.get("mimeType") or "").lower()
            data = (part.get("body") or {}).get("data")
            if data and mime_type in {"text/plain", "text/html"}:
                decoded = cls._decode_body(str(data))
                if mime_type == "text/plain":
                    plain_parts.append(decoded)
                else:
                    html_parts.append(decoded)
            for child in part.get("parts") or []:
                visit(child)

        visit(payload)
        return plain_parts, html_parts

    @staticmethod
    def _decode_body(data: str) -> str:
        try:
            padding = "=" * (-len(data) % 4)
            return base64.urlsafe_b64decode(data + padding).decode(
                "utf-8",
                errors="replace",
            )
        except (ValueError, TypeError):
            return ""

    @staticmethod
    def _received_at(
        message: dict[str, Any],
        headers: dict[str, str],
    ) -> datetime | None:
        internal_date = message.get("internalDate")
        try:
            if internal_date is not None:
                return datetime.fromtimestamp(
                    int(internal_date) / 1000,
                    tz=UTC,
                )
        except (TypeError, ValueError, OverflowError):
            pass
        return parse_date(headers.get("date"))

    @staticmethod
    def _email_url(gmail_id: str) -> str:
        return (
            "https://mail.google.com/mail/u/0/"
            f"?view=pt&search=all&th={gmail_id}"
        )

    @staticmethod
    def _deduplicate_items(items: list[RawItem]) -> list[RawItem]:
        unique: dict[str, RawItem] = {}
        for item in items:
            key = normalize_url(item.url)
            current = unique.get(key)
            if current is None or len(item.raw_text) > len(current.raw_text):
                unique[key] = item
        return list(unique.values())
