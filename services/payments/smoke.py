from repo import PaymentsRepo
if __name__ == "__main__":
    repo = PaymentsRepo()
    tid = repo.create_tx(1000, "EUR", True)
    print("Created tx:", tid)
