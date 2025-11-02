from repo import InventoryRepo
if __name__ == "__main__":
    repo = InventoryRepo()
    repo.upsert("SKU1", 10)
    repo.upsert("SKU2", 5)
    print("Seeded inventory")
