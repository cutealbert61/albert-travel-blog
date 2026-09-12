import importlib
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")

    class RequestException(Exception):
        pass

    requests_stub.exceptions = types.SimpleNamespace(RequestException=RequestException)
    sys.modules["requests"] = requests_stub

import generate_post
import supabase_store


class WeekPlanTests(unittest.TestCase):
    def setUp(self):
        self.locations = {
            "cities": [
                {
                    "city": "京都",
                    "city_en": "Kyoto",
                    "country": "日本",
                }
            ],
            "angles": [
                {
                    "key": "slow_travel",
                    "zh": "慢旅行",
                    "en": "Slow Travel",
                }
            ],
        }
        self.plan = [
            {
                "date": "2020-01-01",
                "city_en": "Kyoto",
                "angle_key": "slow_travel",
                "status": "pending",
            }
        ]

    @mock.patch.object(generate_post, "save_document")
    @mock.patch.object(generate_post, "load_document")
    def test_plan_is_not_marked_done_until_explicit_completion(self, load_document, save_document):
        load_document.return_value = self.plan

        city, angle, selection = generate_post.pick_from_week_plan(self.locations)

        self.assertEqual(city["city_en"], "Kyoto")
        self.assertEqual(angle["key"], "slow_travel")
        self.assertEqual(self.plan[0]["status"], "pending")
        save_document.assert_not_called()

        generate_post.mark_week_plan_done(selection)

        self.assertEqual(self.plan[0]["status"], "done")
        save_document.assert_called_once_with("week_plan", self.plan)


class ImageImportTests(unittest.TestCase):
    @mock.patch.object(supabase_store.time, "sleep")
    @mock.patch.object(supabase_store, "_call_admin")
    def test_transient_import_failure_retries_then_succeeds(self, call_admin, sleep):
        call_admin.side_effect = [
            supabase_store.AdminAPIError(503, "temporary"),
            {"public_url": "https://example.supabase.co/image.jpg"},
        ]

        result = supabase_store.import_image_url(
            "https://images.unsplash.com/photo.jpg",
            retry_delay=1,
        )

        self.assertEqual(result, "https://example.supabase.co/image.jpg")
        self.assertEqual(call_admin.call_count, 2)
        sleep.assert_called_once_with(1)

    @mock.patch.object(supabase_store.time, "sleep")
    @mock.patch.object(supabase_store, "_call_admin")
    def test_non_retryable_import_failure_stops_immediately(self, call_admin, sleep):
        call_admin.side_effect = supabase_store.AdminAPIError(401, "unauthorized")

        with self.assertRaises(supabase_store.AdminAPIError):
            supabase_store.import_image_url("https://images.unsplash.com/photo.jpg")

        call_admin.assert_called_once()
        sleep.assert_not_called()

    @mock.patch.object(generate_post, "import_image_url")
    @mock.patch.object(generate_post, "unsplash_search")
    def test_failed_import_uses_existing_supabase_fallback(self, search, import_image):
        search.return_value = {
            "id": "new-photo",
            "url": "https://images.unsplash.com/new-photo.jpg",
            "credit_name": "Photographer",
            "credit_link": "https://unsplash.com/photographer",
        }
        import_image.side_effect = RuntimeError("temporary import failure")
        used_ids = set()
        fallback = generate_post.FALLBACK_PHOTO["url"]

        result = generate_post.fetch_article_image(
            {"image_queries": {"cover_image_query": "Kyoto street"}},
            "cover_image_query",
            {"city_en": "Kyoto"},
            used_ids,
            fallback_url=fallback,
        )

        self.assertEqual(result["url"], fallback)
        self.assertEqual(result["source_url"], "https://images.unsplash.com/new-photo.jpg")
        self.assertEqual(used_ids, set())


class MainFlowTests(unittest.TestCase):
    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch.object(generate_post.os, "makedirs")
    @mock.patch.object(generate_post, "fetch_article_image")
    @mock.patch.object(generate_post, "call_claude_with_retry")
    @mock.patch.object(generate_post, "save_document")
    @mock.patch.object(generate_post, "load_document")
    def test_week_plan_is_completed_after_article_documents(
        self,
        load_document,
        save_document,
        call_claude,
        fetch_image,
        makedirs,
        opened_file,
    ):
        locations = {
            "cities": [
                {
                    "city": "京都",
                    "city_en": "Kyoto",
                    "country": "日本",
                    "country_en": "Japan",
                    "region": "Asia",
                }
            ],
            "angles": [
                {
                    "key": "slow_travel",
                    "zh": "慢旅行",
                    "en": "Slow Travel",
                    "prompt_hint": "slow",
                }
            ],
        }
        history = {
            "priority_queue": [],
            "used_combinations": [],
            "used_photos": {},
        }
        posts = []
        week_plan = [
            {
                "date": "2020-01-01",
                "city_en": "Kyoto",
                "angle_key": "slow_travel",
                "status": "pending",
            }
        ]
        documents = {
            "locations": locations,
            "history": history,
            "posts": posts,
            "week_plan": week_plan,
        }
        load_document.side_effect = lambda key: documents[key]
        call_claude.return_value = {
            "title_zh": "標題",
            "title_en": "Title",
            "excerpt_zh": "摘要",
            "excerpt_en": "Excerpt",
            "body_zh_html": "<p>[IMAGE_1]</p>",
            "body_en_html": "<p>English</p>",
            "image_queries": {
                "cover_image_query": "Kyoto cover",
                "image_1": "Kyoto one",
                "image_2": "Kyoto two",
                "image_3": "Kyoto three",
                "image_4": "Kyoto four",
                "image_5": "Kyoto five",
                "image_6": "Kyoto six",
            },
            "tags": ["京都"],
            "reading_time": 10,
        }
        fetch_image.return_value = dict(generate_post.FALLBACK_PHOTO)

        with mock.patch.object(generate_post, "ANTHROPIC_API_KEY", "test-key"):
            generate_post.main()

        self.assertEqual(
            [call.args[0] for call in save_document.call_args_list],
            ["posts", "history", "week_plan"],
        )
        self.assertEqual(week_plan[0]["status"], "done")
        self.assertEqual(len(posts), 1)


class WeeklyPlanModuleTests(unittest.TestCase):
    def test_weekly_plan_module_imports(self):
        module = importlib.import_module("plan_week")
        self.assertEqual(module.ROOT, str(ROOT))
        self.assertTrue(os.path.isabs(module.ROOT))


if __name__ == "__main__":
    unittest.main()
