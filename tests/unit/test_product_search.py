from types import SimpleNamespace

import pytest

from integrations.product_search import (
    OpenAIProductSearch,
    ProductFact,
    ProductResearch,
    ResearchedProduct,
    canonical_product_url,
    public_url,
)


def test_source_urls_preserve_evidence_queries_and_identity_normalization_is_separate() -> None:
    url = "http://www.example.com/document?id=123#retention"
    assert public_url(url) == url
    assert (
        canonical_product_url("https://www.example.com/product/?tracking=123")
        == "https://example.com/product"
    )


@pytest.mark.parametrize(
    "url",
    [
        "file:///secret",
        "http://127.0.0.1/",
        "http://169.254.169.254/",
        "https://localhost/",
        "https://user:" + "pass" + "word@example.com/",
        "https://example.com:8443/",
    ],
)
def test_product_identity_rejects_nonpublic_urls(url: str) -> None:
    with pytest.raises(ValueError):
        public_url(url)


async def test_search_rejects_unconsulted_sources_and_unknown_product_hosts() -> None:
    class Responses:
        async def create(self, **kwargs: object) -> object:
            assert kwargs["store"] is False
            return SimpleNamespace(
                output_text="Source research",
                status="completed",
                model_dump=lambda: {
                    "output": [
                        {
                            "type": "web_search_call",
                            "action": {"sources": [{"url": "https://example.com/pricing"}]},
                        }
                    ]
                },
            )

        async def parse(self, **kwargs: object) -> object:
            return SimpleNamespace(
                output_parsed=ProductResearch(
                    products=[
                        ResearchedProduct(
                            name="Calendar",
                            seller="Example",
                            website="https://example.com",
                            edition="",
                            category="scheduling",
                            summary="Scheduling",
                            facts=[
                                ProductFact(
                                    field="price",
                                    value="USD 10/month",
                                    source_urls=["https://example.com/pricing"],
                                ),
                                ProductFact(
                                    field="compliance",
                                    value="Unsupported assertion",
                                    source_urls=["https://unknown.example.org/"],
                                ),
                            ],
                        )
                    ]
                )
            )

    search = OpenAIProductSearch(SimpleNamespace(responses=Responses()), "test-model")  # type: ignore[arg-type]
    research, sources = await search.search("calendar", limit=1)
    assert len(sources) == 1
    assert [f.field for f in research.products[0].facts] == ["price"]
