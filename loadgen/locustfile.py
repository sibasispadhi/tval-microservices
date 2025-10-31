from locust import HttpUser, task, between
import random, uuid

class PaymentsUser(HttpUser):
    wait_time = between(0.01, 0.2)

    @task
    def pay(self):
        payload = {
            "amount": round(random.uniform(5, 250), 2),
            "currency": "USD",
            "merchant_id": "m-"+str(random.randint(1,50)),
            "user_id": "u-"+str(uuid.uuid4())[:8],
            "txn_type": random.choice(["POS","REFUND"])
        }
        self.client.post("/pay", json=payload)
