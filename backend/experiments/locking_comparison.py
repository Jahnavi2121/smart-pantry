import csv
import sys
import threading
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.db.db import get_connection


HOUSEHOLD_NAME = "Concurrency Experiment Household"
PRODUCT_BARCODE = "9999999999991"

STARTING_QUANTITY = 1000

CONCURRENCY_LEVELS = [2, 5, 10, 20]
TRIALS_PER_LEVEL = 10

# Gives concurrent transactions time to overlap between
# reading the quantity and writing the new quantity.
READ_UPDATE_DELAY_SECONDS = 0.05

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_FILE = RESULTS_DIR / "locking_comparison_results.csv"


def create_experiment_inventory_item():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM households
                WHERE name = %s
                ORDER BY id
                LIMIT 1
                """,
                (HOUSEHOLD_NAME,),
            )

            household = cursor.fetchone()

            if household is None:
                raise RuntimeError(
                    "Concurrency experiment household was not found. "
                    "Run concurrency_experiment.py first."
                )

            household_id = household[0]

            cursor.execute(
                """
                SELECT id
                FROM products
                WHERE barcode = %s
                LIMIT 1
                """,
                (PRODUCT_BARCODE,),
            )

            product = cursor.fetchone()

            if product is None:
                raise RuntimeError(
                    "Concurrency experiment product was not found. "
                    "Run concurrency_experiment.py first."
                )

            product_id = product[0]

            cursor.execute(
                """
                INSERT INTO inventory_items (
                    household_id,
                    product_id,
                    quantity,
                    expiration_date,
                    low_stock_threshold
                )
                VALUES (%s, %s, %s, NULL, 1)
                RETURNING id
                """,
                (
                    household_id,
                    product_id,
                    STARTING_QUANTITY,
                ),
            )

            inventory_item_id = cursor.fetchone()[0]

        connection.commit()

        return inventory_item_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def reset_quantity(inventory_item_id):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE inventory_items
                SET quantity = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    STARTING_QUANTITY,
                    inventory_item_id,
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_quantity(inventory_item_id):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT quantity
                FROM inventory_items
                WHERE id = %s
                """,
                (inventory_item_id,),
            )

            row = cursor.fetchone()

            if row is None:
                raise RuntimeError(
                    "Experiment inventory item was not found."
                )

            return row[0]

    finally:
        connection.close()


def delete_inventory_item(inventory_item_id):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM inventory_items
                WHERE id = %s
                """,
                (inventory_item_id,),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def perform_update(
    inventory_item_id,
    use_row_lock,
    start_barrier,
):
    connection = get_connection()
    connection.autocommit = False

    try:
        with connection.cursor() as cursor:
            start_barrier.wait()

            started = time.perf_counter()

            if use_row_lock:
                cursor.execute(
                    """
                    SELECT quantity
                    FROM inventory_items
                    WHERE id = %s
                    FOR UPDATE
                    """,
                    (inventory_item_id,),
                )
            else:
                cursor.execute(
                    """
                    SELECT quantity
                    FROM inventory_items
                    WHERE id = %s
                    """,
                    (inventory_item_id,),
                )

            row = cursor.fetchone()

            if row is None:
                raise RuntimeError(
                    "Experiment inventory item was not found."
                )

            old_quantity = row[0]

            # Simulate application work between reading
            # and writing the shared inventory value.
            time.sleep(READ_UPDATE_DELAY_SECONDS)

            new_quantity = old_quantity + 1

            cursor.execute(
                """
                UPDATE inventory_items
                SET quantity = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    new_quantity,
                    inventory_item_id,
                ),
            )

            connection.commit()

            elapsed_ms = (
                time.perf_counter() - started
            ) * 1000

            return elapsed_ms

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def run_trial(
    inventory_item_id,
    mode,
    use_row_lock,
    concurrency,
    trial_number,
):
    reset_quantity(inventory_item_id)

    expected_quantity = (
        STARTING_QUANTITY + concurrency
    )

    start_barrier = threading.Barrier(concurrency)

    successful_updates = 0
    failed_updates = 0
    request_times = []

    trial_started = time.perf_counter()

    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:
        futures = [
            executor.submit(
                perform_update,
                inventory_item_id,
                use_row_lock,
                start_barrier,
            )
            for _ in range(concurrency)
        ]

        for future in as_completed(futures):
            try:
                elapsed_ms = future.result()

                request_times.append(elapsed_ms)
                successful_updates += 1

            except Exception as exc:
                failed_updates += 1

                print(
                    f"Update failure: {exc}"
                )

    trial_elapsed_ms = (
        time.perf_counter() - trial_started
    ) * 1000

    actual_quantity = get_quantity(
        inventory_item_id
    )

    consistent = (
        failed_updates == 0
        and actual_quantity == expected_quantity
    )

    average_update_ms = (
        sum(request_times) / len(request_times)
        if request_times
        else 0
    )

    maximum_update_ms = (
        max(request_times)
        if request_times
        else 0
    )

    result = {
        "mode": mode,
        "concurrency": concurrency,
        "trial": trial_number,
        "starting_quantity": STARTING_QUANTITY,
        "expected_quantity": expected_quantity,
        "actual_quantity": actual_quantity,
        "successful_updates": successful_updates,
        "failed_updates": failed_updates,
        "consistent": consistent,
        "trial_elapsed_ms": round(
            trial_elapsed_ms,
            3,
        ),
        "average_update_ms": round(
            average_update_ms,
            3,
        ),
        "maximum_update_ms": round(
            maximum_update_ms,
            3,
        ),
    }

    print(
        f"{mode:<10} | "
        f"Concurrency={concurrency:>2} | "
        f"Trial={trial_number:>2} | "
        f"Expected={expected_quantity} | "
        f"Actual={actual_quantity} | "
        f"Consistent={consistent}"
    )

    return result


def save_results(results):
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "mode",
        "concurrency",
        "trial",
        "starting_quantity",
        "expected_quantity",
        "actual_quantity",
        "successful_updates",
        "failed_updates",
        "consistent",
        "trial_elapsed_ms",
        "average_update_ms",
        "maximum_update_ms",
    ]

    with RESULTS_FILE.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(results)


def print_summary(results):
    print()
    print("=" * 70)
    print("ROW LOCKING COMPARISON SUMMARY")
    print("=" * 70)

    for mode in ["NO_LOCK", "FOR_UPDATE"]:
        mode_results = [
            result
            for result in results
            if result["mode"] == mode
        ]

        consistent_trials = sum(
            1
            for result in mode_results
            if result["consistent"]
        )

        total_trials = len(mode_results)

        consistency_rate = (
            consistent_trials
            / total_trials
            * 100
            if total_trials
            else 0
        )

        print()
        print(mode)
        print("-" * 30)
        print(
            f"Total trials: {total_trials}"
        )
        print(
            f"Consistent trials: "
            f"{consistent_trials}"
        )
        print(
            f"Inconsistent trials: "
            f"{total_trials - consistent_trials}"
        )
        print(
            f"Consistency rate: "
            f"{consistency_rate:.2f}%"
        )

        for concurrency in CONCURRENCY_LEVELS:
            matching = [
                result
                for result in mode_results
                if result["concurrency"]
                == concurrency
            ]

            passed = sum(
                1
                for result in matching
                if result["consistent"]
            )

            print(
                f"  {concurrency:>2} concurrent updates: "
                f"{passed}/{len(matching)} consistent"
            )

    print()
    print(
        f"CSV saved to: {RESULTS_FILE}"
    )
    print("=" * 70)


def main():
    print("=" * 70)
    print("SMART PANTRY ROW LOCKING COMPARISON")
    print("=" * 70)
    print()
    print(
        "Condition 1: ordinary SELECT without row locking"
    )
    print(
        "Condition 2: SELECT ... FOR UPDATE"
    )
    print()

    inventory_item_id = None
    results = []

    try:
        inventory_item_id = (
            create_experiment_inventory_item()
        )

        print(
            "Created temporary experiment "
            f"inventory item ID {inventory_item_id}."
        )
        print()

        conditions = [
            (
                "NO_LOCK",
                False,
            ),
            (
                "FOR_UPDATE",
                True,
            ),
        ]

        for mode, use_row_lock in conditions:
            print()
            print("=" * 70)
            print(
                f"Running condition: {mode}"
            )
            print("=" * 70)

            for concurrency in CONCURRENCY_LEVELS:
                for trial_number in range(
                    1,
                    TRIALS_PER_LEVEL + 1,
                ):
                    result = run_trial(
                        inventory_item_id,
                        mode,
                        use_row_lock,
                        concurrency,
                        trial_number,
                    )

                    results.append(result)

        save_results(results)
        print_summary(results)

    finally:
        if inventory_item_id is not None:
            try:
                delete_inventory_item(
                    inventory_item_id
                )

                print(
                    "Temporary experiment inventory "
                    "item was deleted."
                )

            except Exception as cleanup_error:
                print(
                    "Warning: experiment cleanup "
                    f"failed: {cleanup_error}"
                )


if __name__ == "__main__":
    main()