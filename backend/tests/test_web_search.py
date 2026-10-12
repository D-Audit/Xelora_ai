"""Web search provider chain, caching and the desktop agent's cloud hook (tools/web.py)."""
import unittest
from unittest.mock import MagicMock, patch

import requests

import config
from tools import web

DDG_PAGE = (b'<a class="result__a" href="https://duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fddg">'
            b'From DuckDuckGo</a><div class="result__snippet">snippet</div>')


def _json_response(payload):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


class SearchCase(unittest.TestCase):
    def setUp(self):
        web._cache.clear()
        patches = [patch.object(config, name, "") for name in
                   ("TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY", "SERPER_API_KEY", "SEARCH_PROVIDER")]
        patches.append(patch.object(web, "_remote", None))
        for item in patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(web._cache.clear)


class ProviderChainTests(SearchCase):
    def test_without_keys_only_duckduckgo_is_used(self):
        self.assertEqual(["duckduckgo"], web.search_providers())
        with patch("tools.web.get_public_content", return_value=(DDG_PAGE, "u", "text/html")):
            result = web.web_search("rate")
        self.assertTrue(result["verified"])
        self.assertEqual("duckduckgo", result["provider"])
        self.assertEqual("https://example.com/ddg", result["results"][0]["url"])

    def test_keyed_provider_is_preferred_and_parsed(self):
        payload = {"results": [{"title": "Central bank", "url": "https://bank.example/rate", "content": "The rate is 5%"}]}
        with patch.object(config, "TAVILY_API_KEY", "tv-key"), \
                patch("tools.web.requests.post", return_value=_json_response(payload)) as post:
            result = web.web_search("policy rate", 3)
        self.assertEqual("tavily", result["provider"])
        self.assertEqual([{"title": "Central bank", "url": "https://bank.example/rate", "snippet": "The rate is 5%"}],
                         result["results"])
        self.assertEqual("Bearer tv-key", post.call_args.kwargs["headers"]["Authorization"])
        self.assertEqual(3, post.call_args.kwargs["json"]["max_results"])

    def test_brave_and_serper_shapes(self):
        brave = {"web": {"results": [{"title": "B", "url": "https://b.example", "description": "d"}]}}
        with patch.object(config, "BRAVE_SEARCH_API_KEY", "bk"), \
                patch("tools.web.requests.get", return_value=_json_response(brave)):
            self.assertEqual("https://b.example", web.web_search("q1")["results"][0]["url"])
        serper = {"organic": [{"title": "S", "link": "https://s.example", "snippet": "x"}]}
        with patch.object(config, "SERPER_API_KEY", "sk"), \
                patch("tools.web.requests.post", return_value=_json_response(serper)):
            self.assertEqual("https://s.example", web.web_search("q2")["results"][0]["url"])

    def test_failing_provider_falls_through_to_the_next(self):
        with patch.object(config, "TAVILY_API_KEY", "tv-key"), \
                patch("tools.web.requests.post", side_effect=requests.ConnectionError("down")), \
                patch("tools.web.get_public_content", return_value=(DDG_PAGE, "u", "text/html")):
            result = web.web_search("rate")
        self.assertEqual("duckduckgo", result["provider"])

    def test_all_providers_failing_is_an_honest_error(self):
        with patch("tools.web.get_public_content", return_value=(b"<html>challenge</html>", "u", "text/html")):
            result = web.web_search("rate")
        self.assertFalse(result["verified"])
        self.assertEqual([], result["results"])
        self.assertIn("duckduckgo: no results", result["error"])

    def test_unsafe_and_duplicate_urls_are_dropped(self):
        payload = {"results": [
            {"title": "ok", "url": "https://a.example"}, {"title": "dup", "url": "https://a.example"},
            {"title": "js", "url": "javascript:alert(1)"}, {"title": "", "url": "https://untitled.example"},
        ]}
        with patch.object(config, "TAVILY_API_KEY", "k"), \
                patch("tools.web.requests.post", return_value=_json_response(payload)):
            result = web.web_search("q")
        self.assertEqual(["https://a.example"], [item["url"] for item in result["results"]])

    def test_pinned_provider_is_the_only_one_tried(self):
        with patch.object(config, "TAVILY_API_KEY", "k"), patch.object(config, "SEARCH_PROVIDER", "duckduckgo"):
            self.assertEqual(["duckduckgo"], web.search_providers())


class CacheAndRemoteTests(SearchCase):
    def test_repeated_query_is_served_from_cache(self):
        with patch("tools.web.get_public_content", return_value=(DDG_PAGE, "u", "text/html")) as fetch:
            web.web_search("Same  Query")
            web.web_search("same query")
        self.assertEqual(1, fetch.call_count)

    def test_failures_are_not_cached(self):
        with patch("tools.web.get_public_content", return_value=(b"", "u", "text/html")) as fetch:
            web.web_search("q")
            web.web_search("q")
        self.assertEqual(2, fetch.call_count)

    def test_remote_result_is_used_when_verified(self):
        remote = MagicMock(return_value={"verified": True, "provider": "tavily", "results": [{"url": "https://r"}]})
        with patch.object(web, "_remote", remote), patch("tools.web.get_public_content") as fetch:
            result = web.web_search("q", 4)
        remote.assert_called_once_with("q", 4)
        fetch.assert_not_called()
        self.assertEqual("tavily", result["provider"])

    def test_remote_failure_falls_back_to_this_machine(self):
        remote = MagicMock(side_effect=requests.ConnectionError("offline"))
        with patch.object(web, "_remote", remote), \
                patch("tools.web.get_public_content", return_value=(DDG_PAGE, "u", "text/html")):
            result = web.web_search("q")
        self.assertEqual("duckduckgo", result["provider"])


if __name__ == "__main__":
    unittest.main()
