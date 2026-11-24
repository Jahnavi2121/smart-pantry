"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://127.0.0.1:8000";

type User = {
  id: number;
  name: string;
  email: string;
};

type Household = {
  id: number;
  name: string;
  role: string;
};

type Product = {
  id: number;
  name: string;
  brand: string | null;
  barcode: string | null;
};

type InventoryItem = {
  id: number;
  household_id: number;
  product_id: number;
  product_name: string;
  brand: string | null;
  barcode: string | null;
  quantity: number;
  expiration_date: string | null;
  low_stock_threshold: number;
};

export default function DashboardPage() {
  const router = useRouter();

  const [user, setUser] = useState<User | null>(null);
  const [household, setHousehold] = useState<Household | null>(null);

  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);

  const [lowStockItems, setLowStockItems] = useState<InventoryItem[]>([]);
  const [expiringItems, setExpiringItems] = useState<InventoryItem[]>([]);

  const [selectedProductId, setSelectedProductId] = useState("");
  const [quantity, setQuantity] = useState(1);
  const [expirationDate, setExpirationDate] = useState("");
  const [lowStockThreshold, setLowStockThreshold] = useState(1);

  const [loading, setLoading] = useState(true);
  const [addingItem, setAddingItem] = useState(false);

  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    const token = localStorage.getItem("access_token");

    if (!token) {
      router.push("/");
      return;
    }

    try {
      setError("");

      const authHeaders = {
        Authorization: `Bearer ${token}`,
      };

      // Load logged-in user
      const userResponse = await fetch(`${API_URL}/auth/me`, {
        headers: authHeaders,
      });

      if (!userResponse.ok) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("user_name");
        router.push("/");
        return;
      }

      const userData = await userResponse.json();
      setUser(userData);

      // Load user's households
      const householdResponse = await fetch(`${API_URL}/households`, {
        headers: authHeaders,
      });

      if (!householdResponse.ok) {
        throw new Error("Could not load household.");
      }

      const households = await householdResponse.json();

      if (households.length === 0) {
        setError("No household found.");
        return;
      }

      const firstHousehold = households[0];

      setHousehold(firstHousehold);

      // Load household inventory
      const inventoryResponse = await fetch(
        `${API_URL}/inventory/${firstHousehold.id}`,
        {
          headers: authHeaders,
        }
      );

      if (!inventoryResponse.ok) {
        throw new Error("Could not load inventory.");
      }

      const inventoryData = await inventoryResponse.json();
      setInventory(inventoryData);

      // Load low-stock items
      const lowStockResponse = await fetch(
        `${API_URL}/inventory/${firstHousehold.id}/low-stock`,
        {
          headers: authHeaders,
        }
      );

      if (!lowStockResponse.ok) {
        throw new Error("Could not load low-stock items.");
      }

      const lowStockData = await lowStockResponse.json();
      setLowStockItems(lowStockData);

      // Load items expiring within 14 days
      const expiringResponse = await fetch(
        `${API_URL}/inventory/${firstHousehold.id}/expiring-soon?days=14`,
        {
          headers: authHeaders,
        }
      );

      if (!expiringResponse.ok) {
        throw new Error("Could not load expiring items.");
      }

      const expiringData = await expiringResponse.json();
      setExpiringItems(expiringData);

      // Load available products
      const productsResponse = await fetch(`${API_URL}/products`);

      if (!productsResponse.ok) {
        throw new Error("Could not load products.");
      }

      const productData = await productsResponse.json();
      setProducts(productData);

      if (productData.length > 0 && !selectedProductId) {
        setSelectedProductId(String(productData[0].id));
      }
    } catch (error) {
      if (error instanceof Error) {
        setError(error.message);
      } else {
        setError("Something went wrong.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function changeQuantity(
    inventoryItemId: number,
    change: number
  ) {
    const token = localStorage.getItem("access_token");

    if (!token) {
      router.push("/");
      return;
    }

    try {
      setError("");
      setMessage("");

      const response = await fetch(
        `${API_URL}/inventory/${inventoryItemId}/quantity`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({
            change,
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json();

        throw new Error(
          data.detail || "Could not update quantity."
        );
      }

      await loadDashboard();
    } catch (error) {
      if (error instanceof Error) {
        setError(error.message);
      } else {
        setError("Could not update quantity.");
      }
    }
  }

  async function handleAddItem(
    event: FormEvent<HTMLFormElement>
  ) {
    event.preventDefault();

    const token = localStorage.getItem("access_token");

    if (!token) {
      router.push("/");
      return;
    }

    if (!household) {
      setError("No household selected.");
      return;
    }

    if (!selectedProductId) {
      setError("Please select a product.");
      return;
    }

    try {
      setAddingItem(true);
      setError("");
      setMessage("");

      const response = await fetch(`${API_URL}/inventory`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          household_id: household.id,
          product_id: Number(selectedProductId),
          quantity: quantity,
          expiration_date:
            expirationDate === "" ? null : expirationDate,
          low_stock_threshold: lowStockThreshold,
        }),
      });

      if (!response.ok) {
        const data = await response.json();

        throw new Error(
          data.detail || "Could not add item."
        );
      }

      setMessage("Item added to pantry successfully.");

      setQuantity(1);
      setExpirationDate("");
      setLowStockThreshold(1);

      await loadDashboard();
    } catch (error) {
      if (error instanceof Error) {
        setError(error.message);
      } else {
        setError("Could not add item.");
      }
    } finally {
      setAddingItem(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_name");
    router.push("/");
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-gray-100">
        <p className="text-gray-700">
          Loading pantry...
        </p>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-green-700 text-white px-8 py-5 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold">
            Smart Pantry
          </h1>

          <p className="text-green-100 text-sm">
            {user ? `Welcome, ${user.name}` : ""}
          </p>
        </div>

        <button
          onClick={handleLogout}
          className="bg-white text-green-700 px-4 py-2 rounded-lg font-medium hover:bg-gray-100"
        >
          Logout
        </button>
      </header>

      <div className="max-w-6xl mx-auto p-8">
        {/* Error message */}
        {error && (
          <div className="bg-red-100 text-red-700 p-4 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Success message */}
        {message && (
          <div className="bg-green-100 text-green-700 p-4 rounded-lg mb-6">
            {message}
          </div>
        )}

        {/* Household information */}
        {household && (
          <>
            <h2 className="text-2xl font-semibold text-gray-900">
              {household.name}
            </h2>

            <p className="text-gray-500 mb-6">
              Household Pantry
            </p>
          </>
        )}

        {/* Low Stock and Expiring Soon */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Low Stock */}
          <div className="bg-white rounded-xl shadow p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              Low Stock
            </h3>

            {lowStockItems.length === 0 ? (
              <p className="text-gray-500">
                No low-stock items.
              </p>
            ) : (
              <div className="space-y-3">
                {lowStockItems.map((item) => (
                  <div
                    key={item.id}
                    className="border border-gray-200 rounded-lg p-3"
                  >
                    <p className="font-medium text-gray-900">
                      {item.product_name}
                    </p>

                    {item.brand && (
                      <p className="text-sm text-gray-500">
                        {item.brand}
                      </p>
                    )}

                    <p className="text-sm text-gray-700 mt-1">
                      Quantity: {item.quantity}
                    </p>

                    <p className="text-sm text-gray-500">
                      Low stock threshold:{" "}
                      {item.low_stock_threshold}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Expiring Soon */}
          <div className="bg-white rounded-xl shadow p-6">
            <h3 className="text-xl font-semibold text-gray-900 mb-4">
              Expiring Soon
            </h3>

            {expiringItems.length === 0 ? (
              <p className="text-gray-500">
                No items expiring in the next 14 days.
              </p>
            ) : (
              <div className="space-y-3">
                {expiringItems.map((item) => (
                  <div
                    key={item.id}
                    className="border border-gray-200 rounded-lg p-3"
                  >
                    <p className="font-medium text-gray-900">
                      {item.product_name}
                    </p>

                    {item.brand && (
                      <p className="text-sm text-gray-500">
                        {item.brand}
                      </p>
                    )}

                    <p className="text-sm text-gray-700 mt-1">
                      Quantity: {item.quantity}
                    </p>

                    <p className="text-sm text-gray-500">
                      Expires: {item.expiration_date}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Add Item */}
        <div className="bg-white rounded-xl shadow p-6 mb-8">
          <h3 className="text-xl font-semibold text-gray-900 mb-5">
            Add Item
          </h3>

          <form
            onSubmit={handleAddItem}
            className="grid grid-cols-1 md:grid-cols-2 gap-4"
          >
            {/* Product */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Product
              </label>

              <select
                value={selectedProductId}
                onChange={(event) =>
                  setSelectedProductId(event.target.value)
                }
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-gray-900"
              >
                {products.length === 0 && (
                  <option value="">
                    No products available
                  </option>
                )}

                {products.map((product) => (
                  <option
                    key={product.id}
                    value={product.id}
                  >
                    {product.name}
                    {product.brand
                      ? ` - ${product.brand}`
                      : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Quantity */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Quantity
              </label>

              <input
                type="number"
                min="0"
                value={quantity}
                onChange={(event) =>
                  setQuantity(Number(event.target.value))
                }
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-gray-900"
              />
            </div>

            {/* Expiration Date */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Expiration Date
              </label>

              <input
                type="date"
                value={expirationDate}
                onChange={(event) =>
                  setExpirationDate(event.target.value)
                }
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-gray-900"
              />
            </div>

            {/* Low Stock Threshold */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Low Stock Threshold
              </label>

              <input
                type="number"
                min="0"
                value={lowStockThreshold}
                onChange={(event) =>
                  setLowStockThreshold(
                    Number(event.target.value)
                  )
                }
                required
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-gray-900"
              />
            </div>

            {/* Submit */}
            <div className="md:col-span-2">
              <button
                type="submit"
                disabled={
                  addingItem ||
                  products.length === 0
                }
                className="bg-green-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-green-800 disabled:opacity-50"
              >
                {addingItem
                  ? "Adding..."
                  : "Add to Pantry"}
              </button>
            </div>
          </form>
        </div>

        {/* My Pantry */}
        <div className="bg-white rounded-xl shadow p-6">
          <h3 className="text-xl font-semibold text-gray-900 mb-4">
            My Pantry
          </h3>

          {inventory.length === 0 ? (
            <p className="text-gray-500">
              Your pantry is currently empty.
            </p>
          ) : (
            <div className="space-y-4">
              {inventory.map((item) => (
                <div
                  key={item.id}
                  className="border border-gray-200 rounded-lg p-4"
                >
                  <h4 className="font-semibold text-gray-900">
                    {item.product_name}
                  </h4>

                  {item.brand && (
                    <p className="text-sm text-gray-500">
                      {item.brand}
                    </p>
                  )}

                  <p className="text-sm text-gray-700 mt-2">
                    Quantity: {item.quantity}
                  </p>

                  <div className="flex flex-wrap gap-3 mt-4">
                    <button
                      onClick={() =>
                        changeQuantity(item.id, -1)
                      }
                      disabled={item.quantity === 0}
                      className="bg-red-100 text-red-700 px-4 py-2 rounded-lg font-medium hover:bg-red-200 disabled:opacity-50"
                    >
                      - Consume
                    </button>

                    <button
                      onClick={() =>
                        changeQuantity(item.id, 1)
                      }
                      className="bg-green-100 text-green-700 px-4 py-2 rounded-lg font-medium hover:bg-green-200"
                    >
                      + Restock
                    </button>
                  </div>

                  {item.expiration_date && (
                    <p className="text-sm text-gray-700 mt-3">
                      Expires: {item.expiration_date}
                    </p>
                  )}

                  <p className="text-sm text-gray-500 mt-1">
                    Low stock at:{" "}
                    {item.low_stock_threshold}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}