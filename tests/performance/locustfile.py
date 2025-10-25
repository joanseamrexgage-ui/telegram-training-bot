"""
Locust load testing scenarios for telegram-training-bot.

This file defines realistic user behaviors for load testing the bot infrastructure.

Usage:
    # Run with web UI:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000

    # Run headless:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 \
           --users 100 --spawn-rate 10 --run-time 5m --headless

    # With specific test:
    locust -f tests/performance/locustfile.py TelegramBotUser --host=http://localhost:8000
"""

from locust import HttpUser, task, between, events
import random
import time
import json
from datetime import datetime


class TelegramBotUser(HttpUser):
    """
    Simulates a typical Telegram bot user behavior.

    Weight distribution:
    - 30% new users (registration flow)
    - 50% content access (returning users)
    - 15% menu navigation
    - 5% admin operations
    """

    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks

    def on_start(self):
        """Initialize user session"""
        self.user_id = random.randint(10000, 999999)
        self.is_registered = random.random() > 0.3  # 70% are registered users
        self.is_admin = random.random() < 0.05  # 5% are admins

    def create_update(self, update_type="message", text="/start", callback_data=None):
        """Create a Telegram update object"""
        update_id = int(time.time() * 1000) + random.randint(0, 1000)

        if update_type == "message":
            return {
                "update_id": update_id,
                "message": {
                    "message_id": random.randint(1, 10000),
                    "from": {
                        "id": self.user_id,
                        "first_name": f"User{self.user_id}",
                        "username": f"user{self.user_id}"
                    },
                    "chat": {
                        "id": self.user_id,
                        "type": "private"
                    },
                    "date": int(time.time()),
                    "text": text
                }
            }
        elif update_type == "callback":
            return {
                "update_id": update_id,
                "callback_query": {
                    "id": f"cb_{update_id}",
                    "from": {
                        "id": self.user_id,
                        "first_name": f"User{self.user_id}",
                        "username": f"user{self.user_id}"
                    },
                    "message": {
                        "message_id": random.randint(1, 10000),
                        "chat": {
                            "id": self.user_id,
                            "type": "private"
                        },
                        "date": int(time.time() - 1)
                    },
                    "data": callback_data
                }
            }

    @task(3)
    def user_registration_flow(self):
        """
        Simulate new user registration (30% weight).

        Steps:
        1. Send /start command
        2. Provide full name
        3. Select department
        4. Select position
        5. Select park location
        """
        if self.is_registered:
            return  # Skip if already registered

        # Step 1: Start command
        with self.client.post(
            "/webhook",
            json=self.create_update("message", "/start"),
            catch_response=True,
            name="User Registration: /start"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")

        self.wait()

        # Step 2: Full name
        with self.client.post(
            "/webhook",
            json=self.create_update("message", "Иван Иванов"),
            catch_response=True,
            name="User Registration: Full Name"
        ) as response:
            if response.status_code == 200:
                response.success()

        self.wait()

        # Step 3: Department
        departments = ["sales", "sport", "administration"]
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data=f"department_{random.choice(departments)}"),
            catch_response=True,
            name="User Registration: Department"
        ) as response:
            if response.status_code == 200:
                response.success()

        self.wait()

        # Step 4: Position
        positions = ["manager", "specialist", "administrator"]
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data=f"position_{random.choice(positions)}"),
            catch_response=True,
            name="User Registration: Position"
        ) as response:
            if response.status_code == 200:
                response.success()

        self.wait()

        # Step 5: Park location
        parks = ["moscow", "spb", "kazan"]
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data=f"park_{random.choice(parks)}"),
            catch_response=True,
            name="User Registration: Park"
        ) as response:
            if response.status_code == 200:
                response.success()
                self.is_registered = True

    @task(5)
    def content_access_flow(self):
        """
        Simulate content access by existing user (50% weight).

        Steps:
        1. Open main menu
        2. Navigate to section
        3. Access specific content
        """
        if not self.is_registered:
            return  # Only registered users can access content

        # Step 1: Main menu
        with self.client.post(
            "/webhook",
            json=self.create_update("message", "/start"),
            catch_response=True,
            name="Content Access: Main Menu"
        ) as response:
            if response.status_code == 200:
                response.success()

        self.wait()

        # Step 2: Navigate to section
        sections = ["menu_general_info", "menu_sales", "menu_sport"]
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data=random.choice(sections)),
            catch_response=True,
            name="Content Access: Section"
        ) as response:
            if response.status_code == 200:
                response.success()

        self.wait()

        # Step 3: Access specific content
        content_items = [
            "general_info_addresses",
            "general_info_phones",
            "sales_cash_register",
            "sales_crm",
            "sport_equipment",
            "sport_safety"
        ]
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data=random.choice(content_items)),
            catch_response=True,
            name="Content Access: Item"
        ) as response:
            if response.status_code == 200:
                response.success()

    @task(2)
    def menu_navigation(self):
        """
        Simulate menu navigation (20% weight).

        Steps:
        1. Open menu
        2. Navigate through submenus
        3. Go back to main menu
        """
        if not self.is_registered:
            return

        # Navigate to submenu
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data="menu_general_info"),
            catch_response=True,
            name="Menu Navigation: Submenu"
        ) as response:
            if response.status_code == 200:
                response.success()

        self.wait()

        # Go back
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data="back_to_main"),
            catch_response=True,
            name="Menu Navigation: Back"
        ) as response:
            if response.status_code == 200:
                response.success()

    @task(1)
    def admin_operations(self):
        """
        Simulate admin operations (10% weight).

        Steps:
        1. Access admin panel
        2. View statistics
        """
        if not self.is_admin:
            return  # Only admins

        # Access admin panel
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data="admin_panel"),
            catch_response=True,
            name="Admin: Panel Access"
        ) as response:
            if response.status_code == 200:
                response.success()

        self.wait()

        # View statistics
        with self.client.post(
            "/webhook",
            json=self.create_update("callback", callback_data="admin_statistics"),
            catch_response=True,
            name="Admin: Statistics"
        ) as response:
            if response.status_code == 200:
                response.success()


class HeavyLoadUser(HttpUser):
    """
    Simulates heavy load user for stress testing.
    Makes rapid requests to test system limits.
    """

    wait_time = between(0.1, 0.5)  # Very short wait time

    def on_start(self):
        """Initialize stress test user"""
        self.user_id = random.randint(100000, 999999)

    @task
    def rapid_requests(self):
        """Make rapid requests to stress test the system"""
        update = {
            "update_id": int(time.time() * 1000),
            "message": {
                "message_id": random.randint(1, 10000),
                "from": {"id": self.user_id, "first_name": "StressUser"},
                "chat": {"id": self.user_id, "type": "private"},
                "date": int(time.time()),
                "text": "/start"
            }
        }

        with self.client.post("/webhook", json=update, catch_response=True, name="Stress Test") as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                # Rate limited - expected behavior
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class RealisticUserMix(HttpUser):
    """
    Mix of realistic user behaviors with weighted tasks.
    This provides the most realistic load testing scenario.
    """

    wait_time = between(2, 5)  # More realistic wait times

    def on_start(self):
        """Initialize realistic user"""
        self.user_id = random.randint(10000, 999999)
        self.session_duration = 0
        self.max_session_duration = random.randint(60, 300)  # 1-5 minutes

    @task(3)
    def browse_content(self):
        """Browse through content like a real user"""
        sections = ["general_info", "sales", "sport"]
        chosen_section = random.choice(sections)

        # Send start
        self.client.post("/webhook", json=self._create_message("/start"), name="Browse: Start")

        # Wait like a real user reading
        time.sleep(random.uniform(1, 3))

        # Navigate to section
        self.client.post(
            "/webhook",
            json=self._create_callback(f"menu_{chosen_section}"),
            name="Browse: Section"
        )

        # Read content
        time.sleep(random.uniform(2, 5))

        # Maybe go back
        if random.random() > 0.5:
            self.client.post("/webhook", json=self._create_callback("back_to_main"), name="Browse: Back")

    @task(1)
    def search_behavior(self):
        """Simulate search-like behavior"""
        # Multiple rapid taps through menus
        for _ in range(random.randint(2, 5)):
            callback_data = random.choice([
                "menu_general_info",
                "menu_sales",
                "general_info_addresses",
                "back_to_main"
            ])
            self.client.post("/webhook", json=self._create_callback(callback_data), name="Search Behavior")
            time.sleep(random.uniform(0.5, 1.5))

    @task(1)
    def idle_check(self):
        """Simulate user being idle"""
        time.sleep(random.uniform(10, 30))
        self.client.post("/webhook", json=self._create_message("/start"), name="Idle Check")

    def _create_message(self, text):
        """Helper to create message update"""
        return {
            "update_id": int(time.time() * 1000),
            "message": {
                "message_id": random.randint(1, 10000),
                "from": {"id": self.user_id, "first_name": f"User{self.user_id}"},
                "chat": {"id": self.user_id, "type": "private"},
                "date": int(time.time()),
                "text": text
            }
        }

    def _create_callback(self, callback_data):
        """Helper to create callback update"""
        return {
            "update_id": int(time.time() * 1000),
            "callback_query": {
                "id": f"cb_{time.time()}",
                "from": {"id": self.user_id, "first_name": f"User{self.user_id}"},
                "message": {
                    "message_id": random.randint(1, 10000),
                    "chat": {"id": self.user_id, "type": "private"},
                    "date": int(time.time() - 1)
                },
                "data": callback_data
            }
        }


# Event hooks for custom reporting
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts"""
    print("🚀 Load test starting...")
    print(f"Target host: {environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops"""
    print("\n📊 Load test completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Total failures: {environment.stats.total.num_failures}")
    print(f"Average response time: {environment.stats.total.avg_response_time:.2f}ms")
    print(f"RPS: {environment.stats.total.total_rps:.2f}")


@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    """Called on every request for custom metrics"""
    if exception:
        print(f"❌ Request failed: {name} - {exception}")


# Performance thresholds for assertions
class PerformanceThresholds:
    """Define performance thresholds for the bot"""

    MAX_RESPONSE_TIME_MS = 2000  # 2 seconds
    MAX_FAILURE_RATE = 0.05  # 5%
    MIN_RPS = 10  # Minimum requests per second
