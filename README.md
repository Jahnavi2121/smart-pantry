# Smart Pantry

Smart Pantry is a multi-user household inventory management application developed as a Software Engineering capstone project at Rochester Institute of Technology.

The application allows household members to manage shared pantry items, track quantities and expiration dates, identify low-stock items, scan product barcodes, and view inventory change history.

The research component of the project focuses on maintaining consistent inventory when multiple household members update the same item concurrently.

## Features

- User authentication using JWT
- Multi-user household support
- Household membership and owner permissions
- Add and manage pantry products
- Add products using barcode lookup
- Camera-based barcode scanning
- Open Food Facts integration
- Track product quantities
- Consume and restock inventory items
- Remove inventory items
- Track expiration dates
- Display items expiring soon
- Configure low-stock thresholds
- Display low-stock items
- Maintain inventory change history
- Record which user performed an inventory action
- Protect shared inventory updates using PostgreSQL row-level locking
- Automated backend testing
- Concurrency consistency experiments

## Technology Stack

### Backend

- Python
- FastAPI
- PostgreSQL
- psycopg2
- PyJWT
- PyTest

### Frontend

- Next.js
- TypeScript
- React
- Tailwind CSS
- ZXing barcode scanning library

### External API

- Open Food Facts

## Project Structure

```text
smart-pantry/
│
├── backend/
│   ├── config/
│   ├── experiments/
│   │   ├── results/
│   │   ├── concurrency_experiment.py
│   │   └── locking_comparison.py
│   ├── src/
│   │   ├── api/
│   │   ├── db/
│   │   └── server.py
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│   ├── app/
│   ├── public/
│   ├── package.json
│   └── package-lock.json
│
└── README.md
```

## Database

Smart Pantry uses PostgreSQL.

The main database tables are:

- `users`
- `households`
- `household_members`
- `products`
- `inventory_items`
- `inventory_history`

The database schema is located at:

```text
backend/src/db/schema.sql
```

Database connection information is stored locally in:

```text
backend/config/db.yml
```

The database configuration file is excluded from Git and should not be committed because it contains local database credentials.

## Backend Setup

### 1. Navigate to the backend directory

```powershell
cd backend
```

### 2. Create a Python virtual environment

```powershell
python -m venv venv
```

### 3. Activate the virtual environment

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

### 5. Configure PostgreSQL

Create a PostgreSQL database for the application.

The development database used for this project is:

```text
smart_pantry
```

Create:

```text
backend/config/db.yml
```

with the following structure:

```yaml
database:
  host: localhost
  port: 5432
  name: smart_pantry
  user: YOUR_POSTGRES_USER
  password: YOUR_POSTGRES_PASSWORD
```

Replace the username and password with the PostgreSQL credentials for the local environment.

### 6. Create the database tables

Run the SQL contained in:

```text
backend/src/db/schema.sql
```

against the `smart_pantry` PostgreSQL database.

### 7. Start the backend

From the `backend` directory:

```powershell
python -m uvicorn src.server:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

FastAPI documentation is available at:

```text
http://127.0.0.1:8000/docs
```

The health endpoint is:

```text
http://127.0.0.1:8000/health
```

## Frontend Setup

Open another terminal and navigate to the frontend:

```powershell
cd frontend
```

Install the frontend dependencies:

```powershell
npm install
```

Start the development server:

```powershell
npm run dev
```

Open:

```text
http://localhost:3000
```

Using `localhost` is recommended when testing camera-based barcode scanning because browser camera access requires a secure context.

## Authentication

Smart Pantry uses JWT-based authentication.

After successful login, the backend returns an access token. Protected API requests send the token using the HTTP `Authorization` header.

Example:

```text
Authorization: Bearer <token>
```

Household and inventory operations use the authenticated user's identity rather than accepting a user ID directly from the client.

## Inventory Management

Authenticated household members can:

- View their household inventory
- Add products to inventory
- Restock items
- Consume items
- Remove items
- View inventory history
- View low-stock items
- View items that are expiring soon

Inventory quantity cannot be reduced below zero.

Removing an inventory item uses a soft-delete approach so that historical inventory activity can still be retained.

## Barcode Support

Smart Pantry supports both manual and camera-based barcode entry.

### Manual Barcode Lookup

A user can enter a barcode through the frontend. The backend first checks whether the product already exists in the local product database.

If the barcode is not stored locally, Smart Pantry queries the Open Food Facts API.

Products returned from Open Food Facts can then be stored in the local Smart Pantry database.

### Camera Barcode Scanning

The frontend uses ZXing to access the device camera and scan product barcodes.

After a barcode is detected, it is automatically passed to the barcode lookup process.

## Low Stock and Expiration Tracking

Each inventory item can have a configurable low-stock threshold.

An item is considered low stock when:

```text
quantity <= low_stock_threshold
```

The application also provides an expiring-soon view based on the item's expiration date.

The dashboard displays both low-stock and upcoming-expiration information.

## Inventory History

Inventory changes are recorded in the `inventory_history` table.

Tracked actions include:

- `ADD`
- `CONSUME`
- `RESTOCK`
- `REMOVE`

History records include:

- Inventory item
- User who performed the action
- Previous quantity
- New quantity
- Action type
- Timestamp

## Automated Testing

The backend uses PyTest for automated testing.

The test suite currently covers:

- Health endpoint
- Authentication
- Invalid authentication
- Protected endpoints
- Inventory access
- Inventory validation
- Household access
- Household membership
- Product endpoints
- Barcode validation and lookup

Run all backend tests from the `backend` directory:

```powershell
python -m pytest tests -v
```

The implemented test suite contains 20 automated backend tests.

## Research Focus

The research question investigated in this project is:

> How can a multi-user Smart Pantry maintain consistent inventory when multiple household members update shared items?

The primary consistency problem examined was the lost-update problem.

If multiple users read the same inventory quantity at approximately the same time and then independently write updated values, one transaction can overwrite another transaction's change.

The implemented Smart Pantry quantity update uses PostgreSQL row-level locking:

```sql
SELECT ...
FOR UPDATE
```

The selected inventory row remains locked while the quantity update transaction is being completed.

## Concurrency Experiment

Two forms of concurrency testing were performed.

### Smart Pantry API Experiment

The actual FastAPI inventory endpoint was tested using two authenticated household users.

The experiment used concurrency levels of:

```text
2
5
10
20
```

Each concurrency level was tested 10 times.

This resulted in:

```text
40 total API concurrency trials
```

The implemented Smart Pantry endpoint produced the expected final quantity in all 40 trials.

```text
Consistent trials:   40
Inconsistent trials:  0
Consistency rate:   100%
```

## Row-Locking Comparison

A controlled experiment compared two database update approaches:

1. Normal `SELECT` without row locking
2. `SELECT ... FOR UPDATE`

Both conditions used the same starting quantity, same database structure, same concurrency levels, and the same number of trials.

A short controlled delay was inserted between reading and updating the inventory quantity to create overlapping transactions.

### Consistency Results

| Concurrent Updates | No Lock | SELECT FOR UPDATE |
|---:|---:|---:|
| 2 | 0/10 consistent | 10/10 consistent |
| 5 | 0/10 consistent | 10/10 consistent |
| 10 | 0/10 consistent | 10/10 consistent |
| 20 | 0/10 consistent | 10/10 consistent |

Overall results:

| Condition | Consistent Trials | Inconsistent Trials | Consistency Rate |
|---|---:|---:|---:|
| No row locking | 0 | 40 | 0% |
| `SELECT ... FOR UPDATE` | 40 | 0 | 100% |

Without row locking, concurrent transactions read the same quantity and overwrote each other's changes.

With row-level locking, each transaction obtained exclusive access to the inventory row before calculating and writing the new quantity. Under the tested workloads, this prevented lost updates.

## Performance Results

Row locking improved consistency but introduced additional latency because concurrent transactions modifying the same row had to wait for one another.

| Concurrent Updates | No-Lock Avg. Trial Time | Locked Avg. Trial Time |
|---:|---:|---:|
| 2 | 183.19 ms | 224.89 ms |
| 5 | 283.28 ms | 456.10 ms |
| 10 | 407.13 ms | 852.09 ms |
| 20 | 696.24 ms | 1611.44 ms |

The results demonstrate a trade-off between consistency and performance. As contention for the same inventory row increased, row locking increased execution time but preserved the correct final inventory quantity.

These experimental results apply to the tested local environment and workloads and should not be interpreted as proof that every possible concurrent workload will behave identically.

## Experiment Files

The concurrency experiments are located in:

```text
backend/experiments/
```

The Smart Pantry API concurrency experiment is:

```text
backend/experiments/concurrency_experiment.py
```

The controlled locking comparison is:

```text
backend/experiments/locking_comparison.py
```

Experiment results are stored in:

```text
backend/experiments/results/concurrency_results.csv
```

and:

```text
backend/experiments/results/locking_comparison_results.csv
```

## Running the Concurrency Experiments

For the API-level concurrency experiment, first make sure the FastAPI backend is running.

Then, from the project root:

```powershell
python backend\experiments\concurrency_experiment.py
```

To run the controlled row-locking comparison:

```powershell
python backend\experiments\locking_comparison.py
```

The experiments create temporary inventory data for testing and clean up their temporary inventory items after execution.

## Production Build Check

The frontend production build can be checked with:

```powershell
cd frontend
npm run build
```

This verifies that the Next.js application compiles successfully and passes its TypeScript build checks.

## Security Notes

- Database credentials are stored locally and excluded from Git.
- Passwords are stored as password hashes rather than plain-text passwords.
- Protected endpoints require JWT authentication.
- Household access is checked before inventory operations.
- Inventory requests derive the current user from the authentication token rather than trusting a client-provided user ID.
- Development configuration should be replaced with environment-specific secrets before production deployment.

## Future Improvements

Possible future improvements include:

- Deployment to a production environment
- Additional frontend automated testing
- Additional concurrency workloads
- Testing with larger numbers of simultaneous users
- Performance testing on distributed infrastructure
- Notifications for expiring products
- Notifications for low-stock products
- Improved household invitation workflows
- Additional product information from barcode services
- Pantry usage analytics

## Author

**Jahnavi Kaja**

Master of Science in Software Engineering  
Rochester Institute of Technology
