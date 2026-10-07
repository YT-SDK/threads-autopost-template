import unittest
import urllib.parse

from threads_auto import auth


class AuthTests(unittest.TestCase):
    def test_authorize_url(self):
        url = auth.authorize_url("123", "https://localhost/")
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        self.assertTrue(url.startswith("https://threads.com/oauth/authorize?"))
        self.assertEqual(q["client_id"], "123")
        self.assertEqual(q["redirect_uri"], "https://localhost/")
        self.assertEqual(q["response_type"], "code")
        self.assertIn("threads_content_publish", q["scope"])
        self.assertIn("threads_manage_insights", q["scope"])

    def test_extract_code_variants(self):
        self.assertEqual(auth.extract_code("https://localhost/?code=AbC123#_"), "AbC123")
        self.assertEqual(auth.extract_code("https://localhost/?state=x&code=AbC123"), "AbC123")
        self.assertEqual(auth.extract_code("  AbC123#_ \n"), "AbC123")
        with self.assertRaises(ValueError):
            auth.extract_code("https://localhost/?error=access_denied")

    def test_exchange_flow(self):
        calls = []

        def fake(method, url, body, headers):
            calls.append((method, url, body))
            if url.endswith("/oauth/access_token"):
                return 200, {"access_token": "short", "user_id": 42}
            return 200, {"access_token": "long", "token_type": "bearer", "expires_in": 5183944}

        short = auth.exchange_code("123", "sec", "AbC", "https://localhost/", transport=fake)
        self.assertEqual(short["access_token"], "short")
        method, _, body = calls[0]
        form = dict(urllib.parse.parse_qsl(body.decode()))
        self.assertEqual(method, "POST")
        self.assertEqual(form["grant_type"], "authorization_code")
        self.assertEqual(form["code"], "AbC")

        long_lived = auth.exchange_long_lived("sec", "short", transport=fake)
        self.assertEqual(long_lived["access_token"], "long")
        method, url, _ = calls[1]
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        self.assertEqual((method, q["grant_type"], q["access_token"]), ("GET", "th_exchange_token", "short"))

    def test_error_is_not_retried(self):
        calls = []

        def fake(method, url, body, headers):
            calls.append(url)
            return 500, {"error": {"message": "server"}}

        with self.assertRaises(Exception):
            auth.exchange_code("1", "s", "c", "https://localhost/", transport=fake)
        self.assertEqual(len(calls), 1)  # 認可コードは1回限りなので再試行しない


if __name__ == "__main__":
    unittest.main()
