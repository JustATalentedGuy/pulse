import base64
from datetime import UTC, datetime

import httpx

from app.ingestion.gmail import GmailIngestor, resolve_redirect_url


def encode_body(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def make_message(*, plain: str = "", html: str = "") -> dict:
    parts = []
    if plain:
        parts.append(
            {
                "mimeType": "text/plain",
                "body": {"data": encode_body(plain)},
            }
        )
    if html:
        parts.append(
            {
                "mimeType": "text/html",
                "body": {"data": encode_body(html)},
            }
        )
    return {
        "id": "gmail-message-1",
        "internalDate": "1781193600000",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Message-ID", "value": "<newsletter-1@example.com>"},
                {"name": "Subject", "value": "Daily AI Briefing"},
                {"name": "From", "value": "Briefing <news@newsletter.test>"},
            ],
            "parts": parts,
        },
    }


def make_ingestor(**kwargs) -> GmailIngestor:
    return GmailIngestor(
        client_id="client",
        client_secret="secret",  # pragma: allowlist secret
        refresh_token="refresh",
        newsletter_senders=["newsletter.test"],
        redirect_resolver=kwargs.pop("redirect_resolver", lambda url: url),
        **kwargs,
    )


async def test_redirect_resolution_stops_after_one_hop() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.host == "link.newsletter.test":
            return httpx.Response(
                302,
                headers={"Location": "https://second.example/redirect"},
            )
        return httpx.Response(
            302,
            headers={"Location": "https://article.example/final"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolved = await resolve_redirect_url(
            "https://link.newsletter.test/story",
            client=client,
        )

    assert resolved == "https://second.example/redirect"
    assert requests == ["https://link.newsletter.test/story"]


async def test_redirect_resolution_returns_none_on_timeout() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        resolved = await resolve_redirect_url(
            "https://link.newsletter.test/story",
            timeout_seconds=0.01,
            client=client,
        )

    assert resolved is None


async def test_redirect_resolution_retries_one_transient_failure() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("temporary failure", request=request)
        return httpx.Response(
            302,
            headers={"Location": "https://article.example/final"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        resolved = await resolve_redirect_url(
            "https://links.newsletter.test/story",
            client=client,
        )

    assert resolved == "https://article.example/final"
    assert calls == 2


async def test_unsubscribe_and_tracking_links_are_filtered() -> None:
    html = """
    <html><body>
      <h2>Useful model release</h2>
      <p>Details <a href="https://articles.example/model">Read more</a></p>
      <p><a href="https://example.com/unsubscribe?id=123">Unsubscribe</a></p>
      <p><a href="https://example.com/click/abc">Tracking link</a></p>
      <p><a href="mailto:editor@example.com">Contact</a></p>
    </body></html>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert [item.url for item in items] == ["https://articles.example/model"]
    assert items[0].title == "Useful model release"
    assert items[0].raw_text


async def test_sponsor_blocks_ads_and_footer_navigation_are_removed() -> None:
    html = """
    <html><body>
      <section>
        <h2>Durable agent execution</h2>
        <p>A new runtime persists agent state across failures and supports
        approval checkpoints, resumable tools, and detailed traces.</p>
        <p><a href="https://engineering.example/agents">Read full article</a></p>
      </section>
      <section class="sponsor-card">
        <h2>Sponsored by FastCloud</h2>
        <p>Save 40 percent on hosting with code NEWSLETTER.</p>
        <a href="https://fastcloud.example/deal">Claim the offer</a>
      </section>
      <p><a href="https://newsletter.test/jobs">Jobs</a></p>
      <footer>
        <a href="https://newsletter.test/unsubscribe">Unsubscribe</a>
        <a href="https://twitter.com/intent/tweet">Share</a>
      </footer>
    </body></html>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert [item.url for item in items] == [
        "https://engineering.example/agents"
    ]
    assert "FastCloud" not in items[0].raw_text
    assert "Save 40" not in items[0].raw_text
    assert "approval checkpoints" in items[0].raw_text


async def test_same_domain_article_and_substack_post_are_kept() -> None:
    html = """
    <h2>Architecture review</h2>
    <p>A detailed review of queues, idempotency, and failure recovery.
      <a href="https://newsletter.test/p/architecture-review">Read more</a>
    </p>
    <h2>Second review</h2>
    <p>A second detailed engineering article hosted by the publication.
      <a href="https://publication.substack.com/p/second-review">Read more</a>
    </p>
    <p><a href="https://newsletter.test/">Newsletter home</a></p>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert [item.url for item in items] == [
        "https://newsletter.test/p/architecture-review",
        "https://publication.substack.com/p/second-review",
    ]


async def test_gated_article_link_is_retained_with_newsletter_context() -> None:
    html = """
    <h2>Inside a production migration</h2>
    <p>The team describes its dual-write rollout, verification jobs,
    rollback controls, and the metrics used to retire the old path.</p>
    <p><a href="https://members.example.com/article/migration">
    Continue reading</a></p>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert len(items) == 1
    assert items[0].url == "https://members.example.com/article/migration"
    assert "dual-write rollout" in items[0].raw_text
    assert "rollback controls" in items[0].raw_text


async def test_failed_tracker_resolution_keeps_clickable_source() -> None:
    async def fail_resolution(url: str) -> None:
        return None

    html = """
    <h2>Useful systems article</h2>
    <p>This article explains load shedding and backpressure in detail.
      <a href="https://link.newsletter.test/redirect/story">Read more</a>
    </p>
    """

    items = await make_ingestor(
        redirect_resolver=fail_resolution
    ).extract_message(make_message(html=html), "newsletter.test")

    assert [item.url for item in items] == [
        "https://link.newsletter.test/redirect/story"
    ]


async def test_embedded_redirect_target_is_used_without_network_call() -> None:
    calls: list[str] = []

    async def resolver(url: str) -> str:
        calls.append(url)
        return url

    html = """
    <h2>Queue design</h2>
    <p>A detailed article about delivery guarantees and idempotent workers.
      <a href="https://click.example/redirect?url=https%3A%2F%2Fblog.example%2Fqueues">
      Read more</a>
    </p>
    """

    items = await make_ingestor(
        redirect_resolver=resolver
    ).extract_message(make_message(html=html), "newsletter.test")

    assert [item.url for item in items] == ["https://blog.example/queues"]
    assert calls == []


async def test_tldr_cl0_tracking_path_extracts_real_article() -> None:
    html = """
    <h2>Backpressure in production</h2>
    <p>A detailed article about queue limits and overload control.
      <a href="https://tracking.tldrnewsletter.com/CL0/https:%2F%2Fblog.example%2Fbackpressure%3Futm_source=tldr/1/message/signature">
      Read more</a>
    </p>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "tldrnewsletter.com",
    )

    assert [item.url for item in items] == [
        "https://blog.example/backpressure"
    ]


async def test_social_hiring_referral_and_advertising_links_are_removed() -> None:
    html = """
    <h2>Useful article</h2>
    <p>Technical details about a new storage engine.
      <a href="https://blog.example/storage">Read more</a>
    </p>
    <p><a href="https://linkedin.com/in/editor">Editor</a></p>
    <p><a href="https://jobs.example.com/company">Apply here</a></p>
    <p><a href="https://refer.example.com/code">Track your referrals</a></p>
    <p><a href="https://advertise.example.com/">Advertise</a></p>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert [item.url for item in items] == ["https://blog.example/storage"]


async def test_sign_in_gateway_with_article_target_is_retained() -> None:
    html = """
    <h2>Members-only architecture analysis</h2>
    <p>The analysis covers cache invalidation, request coalescing, and
    overload protection in a large production service.
      <a href="https://members.example/signin?next=%2Farticle%2Fcaches">
      Continue reading</a>
    </p>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert [item.url for item in items] == [
        "https://members.example/signin?next=%2Farticle%2Fcaches"
    ]


async def test_hidden_preheader_and_tracking_dom_are_removed() -> None:
    body = " ".join(
        [
            "The article explains backpressure, queue limits, retry budgets, "
            "and overload behavior in production distributed systems."
        ]
        * 10
    )
    html = f"""
    <div class="preheader" style="display:none">Secret promotion preview</div>
    <h2>Production backpressure</h2>
    <p>{body}</p>
    <div aria-hidden="true">Tracking-only hidden text</div>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert items
    assert all("backpressure" in item.raw_text for item in items)
    assert all("Secret promotion preview" not in item.raw_text for item in items)
    assert all("Tracking-only hidden text" not in item.raw_text for item in items)


async def test_html_mislabeled_as_plain_text_does_not_leak_css() -> None:
    mislabeled = """
    <!DOCTYPE html>
    <html><head><style>body { color: red; }</style></head>
    <body><h2>Database queues</h2>
    <p>A useful article about queue ownership, retry budgets, dead-letter
    handling, backpressure, worker leases, and overload recovery in a
    production distributed system.</p>
    </body></html>
    """

    items = await make_ingestor().extract_message(
        make_message(plain=mislabeled),
        "newsletter.test",
    )

    assert items
    assert all("color: red" not in item.raw_text for item in items)
    assert all("@media" not in item.raw_text for item in items)


async def test_tracker_on_newsletter_domain_resolves_before_filtering() -> None:
    async def resolve(url: str) -> str:
        assert url == "https://link.newsletter.test/story"
        return "https://articles.example/resolved"

    html = """
    <h2>Tracked story</h2>
    <p><a href="https://link.newsletter.test/story">Read more</a></p>
    """
    items = await make_ingestor(redirect_resolver=resolve).extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert [item.url for item in items] == [
        "https://articles.example/resolved"
    ]


async def test_plain_text_fallback_extracts_article() -> None:
    plain = (
        "A practical guide to inference optimization\n"
        "https://articles.example/inference\n"
        "This guide compares batching, quantization, and caching."
    )

    items = await make_ingestor().extract_message(
        make_message(plain=plain),
        "newsletter.test",
    )

    assert len(items) == 1
    assert items[0].url == "https://articles.example/inference"
    assert items[0].raw_text


async def test_inline_sections_are_extracted_without_links() -> None:
    html = """
    <h2>Agent frameworks</h2>
    <p>Agent frameworks now emphasize durable execution, state recovery,
    human approval checkpoints, observability, and bounded tool access for
    production systems. This section contains enough detail to be useful.</p>
    <h3>Inference systems</h3>
    <p>Inference systems are improving continuous batching, prefix caching,
    speculative decoding, and quantization support across common hardware.
    This section also contains enough detail to be useful.</p>
    """

    items = await make_ingestor().extract_message(
        make_message(html=html),
        "newsletter.test",
    )

    assert [item.title for item in items] == [
        "Agent frameworks",
        "Inference systems",
    ]
    assert all(item.source_id and "::section::" in item.source_id for item in items)


async def test_promotional_subject_is_skipped() -> None:
    message = make_message(
        html="<h2>Product deal</h2><p>Buy this service today.</p>"
    )
    for header in message["payload"]["headers"]:
        if header["name"] == "Subject":
            header["value"] = "Sponsored: Cloud credits"

    items = await make_ingestor().extract_message(
        message,
        "newsletter.test",
    )

    assert items == []


async def test_full_email_item_uses_cleaned_body() -> None:
    body = " ".join(
        [
            "Today we examine a database migration that uses dual writes, "
            "shadow reads, reconciliation jobs, and explicit rollback gates."
        ]
        * 12
    )
    plain = (
        f"{body}\n\n"
        "Sponsored by FastCloud. Save 40 percent with code NEWSLETTER.\n\n"
        "Unsubscribe from these emails."
    )

    items = await make_ingestor().extract_message(
        make_message(plain=plain),
        "newsletter.test",
    )

    assert len(items) == 1
    assert items[0].url.startswith("https://mail.google.com/")
    assert "dual writes" in items[0].raw_text
    assert "FastCloud" not in items[0].raw_text
    assert "Unsubscribe" not in items[0].raw_text


class FakeRequest:
    def __init__(self, response: dict):
        self.response = response

    def execute(self) -> dict:
        return self.response


class FakeMessages:
    def __init__(self, message: dict):
        self.message = message
        self.list_calls: list[dict] = []

    def list(self, **kwargs) -> FakeRequest:
        self.list_calls.append(kwargs)
        return FakeRequest({"messages": [{"id": self.message["id"]}]})

    def get(self, **kwargs) -> FakeRequest:
        assert kwargs["format"] == "full"
        return FakeRequest(self.message)


class FakeUsers:
    def __init__(self, messages: FakeMessages):
        self._messages = messages

    def messages(self) -> FakeMessages:
        return self._messages


class FakeService:
    def __init__(self, messages: FakeMessages):
        self._users = FakeUsers(messages)

    def users(self) -> FakeUsers:
        return self._users


class MultiMessageFakeMessages:
    def __init__(self, messages: dict[str, dict]):
        self.messages = messages

    def list(self, **kwargs) -> FakeRequest:
        return FakeRequest(
            {"messages": [{"id": message_id} for message_id in self.messages]}
        )

    def get(self, **kwargs) -> FakeRequest:
        return FakeRequest(self.messages[kwargs["id"]])


async def test_fetch_uses_sender_epoch_and_unread_query() -> None:
    message = make_message(
        plain="Story\nhttps://articles.example/story\nUseful context."
    )
    messages = FakeMessages(message)
    now = datetime(2026, 6, 11, 12, tzinfo=UTC)
    ingestor = make_ingestor(
        service_factory=lambda: FakeService(messages),
        now_factory=lambda: now,
    )

    items = await ingestor.fetch()

    expected_epoch = int(datetime(2026, 6, 9, 12, tzinfo=UTC).timestamp())
    assert items
    assert messages.list_calls == [
        {
            "userId": "me",
            "q": (
                "from:newsletter.test "
                f"after:{expected_epoch} is:unread"
            ),
            "maxResults": 100,
            "pageToken": None,
        }
    ]


async def test_one_malformed_message_does_not_fail_other_messages(
    monkeypatch,
) -> None:
    good = make_message(
        plain="Story\nhttps://articles.example/story\nUseful context."
    )
    good["id"] = "good"
    malformed = make_message(plain="Malformed")
    malformed["id"] = "bad"
    messages = MultiMessageFakeMessages({"bad": malformed, "good": good})
    ingestor = make_ingestor(
        service_factory=lambda: FakeService(messages),
    )
    original = ingestor.extract_message

    async def extract(message, sender):
        if message["id"] == "bad":
            raise ValueError("bad newsletter")
        return await original(message, sender)

    monkeypatch.setattr(ingestor, "extract_message", extract)
    items = await ingestor.fetch()

    assert [item.url for item in items] == ["https://articles.example/story"]
