import asyncio
import tempfile
import unittest
from pathlib import Path

import database


class DatabaseOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database.DB_PATH = Path(self.temp_dir.name) / "test.db"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_initialization_and_spending(self):
        async def run():
            await database.init_db()
            user = await database.get_or_create_user(101, "tester", "Tester")
            self.assertEqual(user["balance"], database.START_BALANCE)
            self.assertTrue(await database.spend_balance(101, 10))
            changed = await database.get_user(101)
            self.assertEqual(changed["balance"], database.START_BALANCE - 10)
            self.assertFalse(await database.spend_balance(101, changed["balance"] + 1))

        asyncio.run(run())

    def test_duel_result_is_recorded_only_once(self):
        async def run():
            await database.init_db()
            await database.get_or_create_user(201, "one", "One")
            await database.get_or_create_user(202, "two", "Two")
            await database.set_account_balance(201, 100)
            await database.set_account_balance(202, 100)
            duel_id = await database.create_duel(1, 201, "One", "dice", 25, 10)
            self.assertTrue(await database.accept_duel(duel_id, 202, "Two"))

            first = await database.record_duel_result(
                duel_id, 201, False, 201, 202, 25
            )
            second = await database.record_duel_result(
                duel_id, 201, False, 201, 202, 25
            )
            self.assertTrue(first)
            self.assertFalse(second)
            winner = await database.get_user(201)
            self.assertEqual(winner["balance"], 125)

        asyncio.run(run())

    def test_roulette_finish_is_recorded_only_once(self):
        async def run():
            await database.init_db()
            await database.get_or_create_user(301, "winner", "Winner")
            roulette_id = await database.create_roulette(1, 301, "dice", "100", 1)
            await database.join_roulette(roulette_id, 301, "winner", "Winner")
            await database.start_roulette(roulette_id)

            first = await database.finish_roulette(roulette_id, 301, "Winner")
            second = await database.finish_roulette(roulette_id, 301, "Winner")
            self.assertTrue(first)
            self.assertFalse(second)

        asyncio.run(run())

    def test_hemp_economy_cycle(self):
        async def run():
            await database.init_db()
            await database.get_or_create_user(401, "farmer", "Farmer")
            await database.set_account_balance(401, 500)

            collected = await database.collect_hemp(401)
            self.assertTrue(collected[0])
            hemp = await database.get_or_create_hemp(401)
            self.assertGreater(hemp["leaves"], 0)

            planted = await database.plant_hemp(401)
            self.assertTrue(planted[0])
            harvest = await database.harvest_hemp(401)
            self.assertFalse(harvest[0])

            sold = await database.sell_hemp(401)
            self.assertTrue(sold[0])
            after_sale = await database.get_user(401)
            self.assertGreater(after_sale["balance"], 500)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
