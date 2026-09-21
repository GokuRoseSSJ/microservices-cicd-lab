import unittest
from app import app

class ProductServiceTest(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_home(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_metrics(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)

if __name__ == "__main__":
    unittest.main()
