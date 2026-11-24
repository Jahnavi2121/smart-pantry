import csv
import json
import threading
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request


BASE_URL = "http://127.0.0.1:8000"

OWNER_EMAIL = "jahnavi@example.com"
OWNER_PASSWORD = "TestPassword123"

MEMBER_NAME = "Concurrency Test Member"
MEMBER_EMAIL = "concurrency.member@example.com"
MEMBER_PASSWORD = "ConcurrencyTest123!"

HOUSEHOLD_NAME = "Concurrency Experiment Household"

PRODUCT_NAME = "Concurrency Test Product"
PRODUCT_BRAND = "Smart Pantry Research"
PRODUCT_BARCODE = "9999999999991"

STARTING_QUANTITY = 1000

CONCURRENCY_LEVELS = [2, 5, 10, 20]
TRIALS_PER_LEVEL = 10

RESULTS_DIR = Path(__file__).resolve().parent / "results"
RESULTS_FILE = RESULTS_DIR / "concurrency_results.csv"


def api_request(
    method,
    path,
    token=None,
    payload=None,
    allowed_statuses=(200,),
):
    url = f"{BASE_URL}{path}"

    headers = {
        "Content-Type": "application/json",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = None

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    req = request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with request.urlopen(req, timeout=30) as response:
            response_body = response.read().decode("utf-8")

            data = (
                json.loads(response_body)
                if response_body
                else None
            )

            if response.status not in allowed_statuses:
                raise RuntimeError(
                    f"{method} {path} returned "
                    f"{response.status}: {data}"
                )

            return response.status, data

    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8")

        try:
            data = json.loads(response_body)
        except json.JSONDecodeError:
            data = response_body

        if exc.code in allowed_statuses:
            return exc.code, data

        raise RuntimeError(
            f"{method} {path} returned "
            f"{exc.code}: {data}"
        ) from exc

    except error.URLError as exc:
        raise RuntimeError(
            "Could not connect to the Smart Pantry backend."
        ) from exc


def login(email, password):
    _, data = api_request(
        "POST",
        "/auth/login",
        payload={
            "email": email,
            "password": password,
        },
    )

    return data["access_token"]


def get_current_user(token):
    _, data = api_request(
        "GET",
        "/auth/me",
        token=token,
    )

    return data


def ensure_member_user():
    status, data = api_request(
        "POST",
        "/users",
        payload={
            "name": MEMBER_NAME,
            "email": MEMBER_EMAIL,
            "password": MEMBER_PASSWORD,
        },
        allowed_statuses=(201, 409),
    )

    if status == 201:
        print(
            f"Created experiment user: "
            f"{data['email']}"
        )
    else:
        print(
            "Experiment user already exists."
        )

    member_token = login(
        MEMBER_EMAIL,
        MEMBER_PASSWORD,
    )

    member = get_current_user(member_token)

    return member, member_token


def ensure_experiment_household(owner_token):
    _, households = api_request(
        "GET",
        "/households",
        token=owner_token,
    )

    for household in households:
        if household["name"] == HOUSEHOLD_NAME:
            print(
                "Using existing experiment household "
                f"(ID {household['id']})."
            )
            return household["id"]

    _, household = api_request(
        "POST",
        "/households",
        token=owner_token,
        payload={
            "name": HOUSEHOLD_NAME,
        },
        allowed_statuses=(201,),
    )

    print(
        "Created experiment household "
        f"(ID {household['id']})."
    )

    return household["id"]


def ensure_household_member(
    household_id,
    member_id,
    owner_token,
):
    _, members = api_request(
        "GET",
        f"/households/{household_id}/members",
        token=owner_token,
    )

    if any(
        member["id"] == member_id
        for member in members
    ):
        print(
            "Experiment member already belongs "
            "to the household."
        )
        return

    api_request(
        "POST",
        f"/households/{household_id}/members",
        token=owner_token,
        payload={
            "user_id": member_id,
        },
    )

    print(
        "Added experiment member to household."
    )


def ensure_product():
    _, products = api_request(
        "GET",
        "/products",
    )

    for product in products:
        if product.get("barcode") == PRODUCT_BARCODE:
            print(
                "Using existing experiment product "
                f"(ID {product['id']})."
            )
            return product["id"]

    _, product = api_request(
        "POST",
        "/products",
        payload={
            "name": PRODUCT_NAME,
            "brand": PRODUCT_BRAND,
            "barcode": PRODUCT_BARCODE,
        },
        allowed_statuses=(201,),
    )

    print(
        "Created experiment product "
        f"(ID {product['id']})."
    )

    return product["id"]


def create_inventory_item(
    household_id,
    product_id,
    owner_token,
):
    _, item = api_request(
        "POST",
        "/inventory",
        token=owner_token,
        payload={
            "household_id": household_id,
            "product_id": product_id,
            "quantity": STARTING_QUANTITY,
            "expiration_date": None,
            "low_stock_threshold": 1,
        },
        allowed_statuses=(201,),
    )

    print(
        "Created experiment inventory item "
        f"(ID {item['id']})."
    )

    return item["id"]


def get_quantity(
    household_id,
    inventory_item_id,
    token,
):
    _, inventory = api_request(
        "GET",
        f"/inventory/{household_id}",
        token=token,
    )

    for item in inventory:
        if item["id"] == inventory_item_id:
            return item["quantity"]

    raise RuntimeError(
        "Experiment inventory item could not be found."
    )


def reset_quantity(
    household_id,
    inventory_item_id,
    token,
):
    current_quantity = get_quantity(
        household_id,
        inventory_item_id,
        token,
    )

    change = STARTING_QUANTITY - current_quantity

    if change == 0:
        return

    api_request(
        "PATCH",
        f"/inventory/{inventory_item_id}/quantity",
        token=token,
        payload={
            "change": change,
        },
    )


def perform_update(
    inventory_item_id,
    token,
    change,
    barrier,
):
    barrier.wait()

    start_time = time.perf_counter()

    status, _ = api_request(
        "PATCH",
        f"/inventory/{inventory_item_id}/quantity",
        token=token,
        payload={
            "change": change,
        },
    )

    elapsed_ms = (
        time.perf_counter() - start_time
    ) * 1000

    return {
        "status": status,
        "change": change,
        "elapsed_ms": elapsed_ms,
    }


def run_trial(
    household_id,
    inventory_item_id,
    owner_token,
    member_token,
    concurrency,
    trial_number,
):
    reset_quantity(
        household_id,
        inventory_item_id,
        owner_token,
    )

    changes = [
        1 if index % 2 == 0 else -1
        for index in range(concurrency)
    ]

    expected_quantity = (
        STARTING_QUANTITY + sum(changes)
    )

    tokens = [
        owner_token
        if index % 2 == 0
        else member_token
        for index in range(concurrency)
    ]

    barrier = threading.Barrier(concurrency)

    trial_start = time.perf_counter()

    results = []

    with ThreadPoolExecutor(
        max_workers=concurrency
    ) as executor:
        futures = [
            executor.submit(
                perform_update,
                inventory_item_id,
                tokens[index],
                changes[index],
                barrier,
            )
            for index in range(concurrency)
        ]

        for future in as_completed(futures):
            results.append(future.result())

    trial_elapsed_ms = (
        time.perf_counter() - trial_start
    ) * 1000

    actual_quantity = get_quantity(
        household_id,
        inventory_item_id,
        owner_token,
    )

    successful_requests = sum(
        1
        for result in results
        if result["status"] == 200
    )

    average_request_ms = (
        sum(
            result["elapsed_ms"]
            for result in results
        )
        / len(results)
    )

    maximum_request_ms = max(
        result["elapsed_ms"]
        for result in results
    )

    consistent = (
        successful_requests == concurrency
        and actual_quantity == expected_quantity
    )

    result = {
        "timestamp_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "concurrency": concurrency,
        "trial": trial_number,
        "starting_quantity": STARTING_QUANTITY,
        "total_requested_change": sum(changes),
        "expected_quantity": expected_quantity,
        "actual_quantity": actual_quantity,
        "successful_requests": successful_requests,
        "failed_requests": (
            concurrency - successful_requests
        ),
        "consistent": consistent,
        "trial_elapsed_ms": round(
            trial_elapsed_ms,
            3,
        ),
        "average_request_ms": round(
            average_request_ms,
            3,
        ),
        "maximum_request_ms": round(
            maximum_request_ms,
            3,
        ),
    }

    print(
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
        "timestamp_utc",
        "concurrency",
        "trial",
        "starting_quantity",
        "total_requested_change",
        "expected_quantity",
        "actual_quantity",
        "successful_requests",
        "failed_requests",
        "consistent",
        "trial_elapsed_ms",
        "average_request_ms",
        "maximum_request_ms",
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
    total_trials = len(results)

    consistent_trials = sum(
        1
        for result in results
        if result["consistent"]
    )

    inconsistent_trials = (
        total_trials - consistent_trials
    )

    print()
    print("=" * 60)
    print("CONCURRENCY EXPERIMENT SUMMARY")
    print("=" * 60)
    print(
        f"Total trials: {total_trials}"
    )
    print(
        f"Consistent trials: {consistent_trials}"
    )
    print(
        f"Inconsistent trials: {inconsistent_trials}"
    )

    if total_trials > 0:
        consistency_rate = (
            consistent_trials
            / total_trials
            * 100
        )

        print(
            "Consistency rate: "
            f"{consistency_rate:.2f}%"
        )

    print()
    print("Results by concurrency level:")

    for concurrency in CONCURRENCY_LEVELS:
        matching_results = [
            result
            for result in results
            if result["concurrency"] == concurrency
        ]

        passed = sum(
            1
            for result in matching_results
            if result["consistent"]
        )

        print(
            f"  {concurrency:>2} concurrent requests: "
            f"{passed}/{len(matching_results)} "
            "consistent"
        )

    print()
    print(
        f"CSV saved to: {RESULTS_FILE}"
    )
    print("=" * 60)


def main():
    print("=" * 60)
    print("SMART PANTRY CONCURRENCY EXPERIMENT")
    print("=" * 60)

    owner_token = login(
        OWNER_EMAIL,
        OWNER_PASSWORD,
    )

    owner = get_current_user(owner_token)

    print(
        f"Owner authenticated: {owner['email']}"
    )

    member, member_token = ensure_member_user()

    print(
        f"Member authenticated: {member['email']}"
    )

    household_id = ensure_experiment_household(
        owner_token
    )

    ensure_household_member(
        household_id,
        member["id"],
        owner_token,
    )

    product_id = ensure_product()

    inventory_item_id = None
    results = []

    try:
        inventory_item_id = create_inventory_item(
            household_id,
            product_id,
            owner_token,
        )

        print()
        print(
            "Running concurrent quantity updates..."
        )
        print()

        for concurrency in CONCURRENCY_LEVELS:
            for trial_number in range(
                1,
                TRIALS_PER_LEVEL + 1,
            ):
                result = run_trial(
                    household_id,
                    inventory_item_id,
                    owner_token,
                    member_token,
                    concurrency,
                    trial_number,
                )

                results.append(result)

        save_results(results)
        print_summary(results)

    finally:
        if inventory_item_id is not None:
            try:
                api_request(
                    "DELETE",
                    f"/inventory/{inventory_item_id}",
                    token=owner_token,
                )

                print(
                    "Experiment inventory item "
                    "was cleaned up."
                )

            except Exception as cleanup_error:
                print(
                    "Warning: cleanup failed: "
                    f"{cleanup_error}"
                )


if __name__ == "__main__":
    main()